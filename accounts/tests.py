from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import User
from core.models import AuditLog

STAFF_PASSWORD = "StaffPassw0rd!"


class PersonnelPrivilegeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password=STAFF_PASSWORD,
            role=User.Role.ADMIN,
            email="admin@example.com",
        )
        self.manager = User.objects.create_user(
            username="manager",
            password=STAFF_PASSWORD,
            role=User.Role.MANAGER,
            email="manager@example.com",
        )
        self.caissier = User.objects.create_user(
            username="caissier",
            password=STAFF_PASSWORD,
            role=User.Role.CAISSIER,
        )
        self.client_user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password=STAFF_PASSWORD,
            role=User.Role.CLIENT,
        )

    def _staff_payload(self, **overrides):
        data = {
            "username": "newstaff",
            "first_name": "New",
            "last_name": "Staff",
            "email": "newstaff@example.com",
            "phone": "",
            "role": User.Role.SERVEUR,
            "is_active": "on",
            "password1": STAFF_PASSWORD,
            "password2": STAFF_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_manager_cannot_create_admin(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_create"),
            self._staff_payload(username="evil-admin", role=User.Role.ADMIN),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="evil-admin").exists())

    def test_manager_cannot_create_manager(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_create"),
            self._staff_payload(username="peer", role=User.Role.MANAGER),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="peer").exists())

    def test_manager_can_create_serveur(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_create"),
            self._staff_payload(),
        )
        self.assertRedirects(r, reverse("accounts:personnel_list"))
        created = User.objects.get(username="newstaff")
        self.assertEqual(created.role, User.Role.SERVEUR)
        self.assertTrue(
            AuditLog.objects.filter(action="personnel.create", object_id=str(created.pk)).exists()
        )

    def test_admin_can_create_admin(self):
        self.client.login(username="admin", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_create"),
            self._staff_payload(username="admin2", role=User.Role.ADMIN, email="a2@example.com"),
        )
        self.assertRedirects(r, reverse("accounts:personnel_list"))
        self.assertEqual(User.objects.get(username="admin2").role, User.Role.ADMIN)

    def test_manager_cannot_edit_admin(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.get(reverse("accounts:personnel_update", args=[self.admin.pk]))
        self.assertEqual(r.status_code, 403)
        r = self.client.post(
            reverse("accounts:personnel_update", args=[self.admin.pk]),
            {
                "username": "admin",
                "first_name": "",
                "last_name": "",
                "email": "admin@example.com",
                "phone": "",
                "role": User.Role.SERVEUR,
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 403)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_manager_cannot_promote_self(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_update", args=[self.manager.pk]),
            {
                "username": "manager",
                "email": "manager@example.com",
                "role": User.Role.ADMIN,
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 403)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.role, User.Role.MANAGER)

    def test_manager_cannot_convert_client(self):
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.get(reverse("accounts:personnel_update", args=[self.client_user.pk]))
        self.assertEqual(r.status_code, 404)
        r = self.client.post(
            reverse("accounts:personnel_update", args=[self.client_user.pk]),
            {
                "username": "client@example.com",
                "email": "client@example.com",
                "role": User.Role.SERVEUR,
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 404)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, User.Role.CLIENT)

    def test_cannot_deactivate_last_admin(self):
        self.client.login(username="admin", password=STAFF_PASSWORD)
        r = self.client.post(
            reverse("accounts:personnel_update", args=[self.admin.pk]),
            {
                "username": "admin",
                "email": "admin@example.com",
                "role": User.Role.ADMIN,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_cannot_delete_last_admin(self):
        other_admin = User.objects.create_user(
            username="admin2", password=STAFF_PASSWORD, role=User.Role.ADMIN
        )
        self.client.login(username="admin", password=STAFF_PASSWORD)
        self.client.post(reverse("accounts:personnel_delete", args=[other_admin.pk]))
        self.assertFalse(User.objects.filter(username="admin2").exists())
        r = self.client.post(reverse("accounts:personnel_delete", args=[self.admin.pk]))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertRedirects(r, reverse("accounts:personnel_list"))

    def test_manager_cannot_delete_admin(self):
        extra = User.objects.create_user(
            username="admin2", password=STAFF_PASSWORD, role=User.Role.ADMIN
        )
        self.client.login(username="manager", password=STAFF_PASSWORD)
        r = self.client.post(reverse("accounts:personnel_delete", args=[extra.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk=extra.pk).exists())

    def test_caissier_cannot_access_personnel(self):
        self.client.login(username="caissier", password=STAFF_PASSWORD)
        r = self.client.get(reverse("accounts:personnel_list"))
        self.assertEqual(r.status_code, 302)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="cook",
            password=STAFF_PASSWORD,
            role=User.Role.CUISINE,
            email="cook@example.com",
        )
        self.customer = User.objects.create_user(
            username="diner@example.com",
            email="diner@example.com",
            password=STAFF_PASSWORD,
            role=User.Role.CLIENT,
        )

    def test_staff_reset_sends_email(self):
        r = self.client.post(
            reverse("accounts:password_reset"), {"email": "cook@example.com"}
        )
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset/", mail.outbox[0].body)

    def test_client_reset_sends_email(self):
        r = self.client.post(
            reverse("accounts:client_password_reset"), {"email": "diner@example.com"}
        )
        self.assertRedirects(r, reverse("accounts:client_password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.customer.pk))
        token = default_token_generator.make_token(self.customer)
        url = reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        confirm = r.url
        new_password = "NewClientPassw0rd!"
        r = self.client.post(
            confirm,
            {"new_password1": new_password, "new_password2": new_password},
        )
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(new_password))
