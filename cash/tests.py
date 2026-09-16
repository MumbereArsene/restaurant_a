from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashClosure, CashEntry
from menu.models import Category, Dish
from orders.models import Order, OrderItem
from tables.models import Table


class CashIntegrityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pass1234", role=User.Role.ADMIN
        )
        self.table = Table.objects.create(number=1, capacity=2)
        cat = Category.objects.create(name_fr="Plats", position=1)
        self.dish = Dish.objects.create(category=cat, name_fr="Riz", price=Decimal("5.00"))

    def _paid_order(self):
        order = Order.objects.create(table=self.table, status=Order.Status.SERVIE)
        OrderItem.objects.create(
            order=order, dish=self.dish, quantity=1, unit_price=self.dish.price
        )
        order.refresh_total()
        order.mark_paid(self.admin)
        return order

    def test_payment_creates_single_cash_in(self):
        order = self._paid_order()
        entry = CashEntry.objects.get(order=order)
        self.assertEqual(entry.type, CashEntry.Type.IN)
        self.assertEqual(entry.amount, Decimal("5.00"))

    def test_negative_amount_rejected(self):
        entry = CashEntry(
            type=CashEntry.Type.OUT,
            amount=Decimal("-1.00"),
            reason="invalid",
            created_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_manual_entry_rejects_negative_post(self):
        self.client.login(username="admin", password="pass1234")
        r = self.client.post(
            reverse("cash:create"),
            {"type": "out", "amount": "-10", "reason": "hack"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CashEntry.objects.filter(reason="hack").exists())

    def test_closure_snapshot(self):
        self._paid_order()
        self.client.login(username="admin", password="pass1234")
        r = self.client.post(
            reverse("cash:close"),
            {"counted_amount": "5.00", "notes": "ok"},
        )
        self.assertEqual(CashClosure.objects.count(), 1)
        closure = CashClosure.objects.get()
        self.assertEqual(closure.expected_amount, Decimal("5.00"))
        self.assertEqual(closure.counted_amount, Decimal("5.00"))
        self.assertEqual(closure.difference, Decimal("0.00"))
        self.assertRedirects(r, reverse("cash:closure_detail", args=[closure.pk]))
