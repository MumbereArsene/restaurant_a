from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .helpers import make_user


class AnalyticsPermissionTests(TestCase):
    def setUp(self):
        self.url = reverse("analytics:dashboard")
        self.xlsx = reverse("analytics:export_xlsx")
        self.pdf = reverse("analytics:export_pdf")

    def _login(self, role, username=None):
        user = make_user(username or role, role)
        if role == User.Role.ADMIN:
            user.is_superuser = True
            user.is_staff = True
            user.save()
        self.client.force_login(user)
        return user

    def test_admin_and_manager_can_view(self):
        for role in (User.Role.ADMIN, User.Role.MANAGER):
            self.client.logout()
            self._login(role, f"{role}-ok")
            self.assertEqual(self.client.get(self.url).status_code, 200)
            self.assertEqual(self.client.get(self.xlsx).status_code, 200)
            self.assertEqual(self.client.get(self.pdf).status_code, 200)

    def test_other_roles_forbidden(self):
        for role in (User.Role.SERVEUR, User.Role.CAISSIER, User.Role.CUISINE):
            self.client.logout()
            self._login(role, f"{role}-no")
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.get(self.xlsx).status_code, 403)
            self.assertEqual(self.client.get(self.pdf).status_code, 403)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/staff/login/", response.url)

    def test_nav_hidden_for_serveur(self):
        self._login(User.Role.SERVEUR, "srv-nav")
        # serveur lands on serveur home; fetch a page they can actually see
        from django.urls import reverse as r

        response = self.client.get(r("tables:serveur_home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("analytics:dashboard"))

    def test_english_label_on_dashboard(self):
        from django.utils.translation import gettext, override

        self._login(User.Role.ADMIN, "i18n-admin")
        with override("en"):
            self.assertEqual(str(gettext("Analyse")), "Analytics")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analyse")
