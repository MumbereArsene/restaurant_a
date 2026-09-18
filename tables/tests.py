from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from menu.models import Category, Dish
from orders.models import Order, OrderItem
from tables.models import Table


class TableOccupationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pass1234", role=User.Role.ADMIN
        )
        self.serveur = User.objects.create_user(
            username="serveur", password="pass1234", role=User.Role.SERVEUR
        )
        self.table = Table.objects.create(
            number=3, capacity=4, status=Table.Status.OCCUPEE
        )
        cat = Category.objects.create(name_fr="Plats", position=1)
        self.dish = Dish.objects.create(
            category=cat, name_fr="Soup", price=Decimal("8.00")
        )

    def _order(self, status=Order.Status.EN_ATTENTE):
        order = Order.objects.create(table=self.table, status=status)
        OrderItem.objects.create(
            order=order, dish=self.dish, quantity=1, unit_price=self.dish.price
        )
        order.refresh_total()
        return order

    def test_cancel_frees_table(self):
        order = self._order()
        self.client.login(username="admin", password="pass1234")
        self.client.post(reverse("orders:staff_cancel", args=[order.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.LIBRE)

    def test_pay_keep_table_stays_occupied(self):
        order = self._order(status=Order.Status.SERVIE)
        self.client.login(username="serveur", password="pass1234")
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"from_scan": "1", "release_table": "0"},
        )
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.OCCUPEE)

    def test_pay_release_frees_table(self):
        order = self._order(status=Order.Status.SERVIE)
        self.client.login(username="serveur", password="pass1234")
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"from_scan": "1", "release_table": "1"},
        )
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.LIBRE)

    def test_manual_free_blocked_when_open_order(self):
        self._order()
        self.client.login(username="serveur", password="pass1234")
        r = self.client.post(reverse("tables:free_by_pk", args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.OCCUPEE)
        self.assertRedirects(r, reverse("tables:serveur_home"))

    def test_manual_free_after_paid_keep(self):
        order = self._order(status=Order.Status.SERVIE)
        order.mark_paid(self.admin)
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self.client.login(username="serveur", password="pass1234")
        self.client.post(reverse("tables:free_by_pk", args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.LIBRE)


class TablePublicCodeTests(TestCase):
    def setUp(self):
        self.serveur = User.objects.create_user(
            username="serveur", password="pass1234", role=User.Role.SERVEUR
        )
        self.table = Table.objects.create(number=12, capacity=4)

    def test_public_code_allocated_on_create(self):
        from tables.codes import CODE_ALPHABET

        self.assertEqual(len(self.table.public_code), 6)
        self.assertTrue(set(self.table.public_code) <= set(CODE_ALPHABET))
        other = Table.objects.create(number=13, capacity=2)
        self.assertNotEqual(self.table.public_code, other.public_code)

    def test_regenerate_changes_public_code_keeps_number(self):
        old = self.table.public_code
        self.table.regenerate_token()
        self.table.refresh_from_db()
        self.assertNotEqual(self.table.public_code, old)
        self.assertEqual(self.table.number, 12)

    def test_resolve_table_normalizes_input(self):
        from tables.codes import resolve_table

        code = self.table.public_code
        self.assertEqual(resolve_table(code.lower()).pk, self.table.pk)
        self.assertEqual(resolve_table(f" {code[:3]}-{code[3:]} ").pk, self.table.pk)
        self.assertEqual(resolve_table(self.table.qr_token).pk, self.table.pk)

    def test_free_by_public_code(self):
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self.client.login(username="serveur", password="pass1234")
        r = self.client.post(
            reverse("tables:free_by_token"), {"token": self.table.public_code}
        )
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.LIBRE)
        self.assertEqual(r.status_code, 302)
