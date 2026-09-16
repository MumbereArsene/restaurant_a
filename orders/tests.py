from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashEntry
from menu.models import Category, Dish
from tables.models import Table

from .models import Order, OrderItem


class OrderWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pass1234", role=User.Role.ADMIN
        )
        self.serveur = User.objects.create_user(
            username="serveur", password="pass1234", role=User.Role.SERVEUR
        )
        self.cuisine = User.objects.create_user(
            username="cuisine", password="pass1234", role=User.Role.CUISINE
        )
        self.table = Table.objects.create(number=7, capacity=4, status=Table.Status.OCCUPEE)
        cat = Category.objects.create(name_fr="Plats", position=1)
        self.dish = Dish.objects.create(
            category=cat, name_fr="Pizza", price=Decimal("10.00")
        )

    def _order(self, status=Order.Status.EN_ATTENTE):
        order = Order.objects.create(table=self.table, status=status)
        OrderItem.objects.create(
            order=order, dish=self.dish, quantity=2, unit_price=self.dish.price
        )
        order.refresh_total()
        return order

    def _login(self, user="admin"):
        self.client.login(username=user, password="pass1234")

    def test_accept_then_serve(self):
        order = self._order()
        self._login()
        r = self.client.post(reverse("orders:staff_advance", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ACCEPTEE)
        self.assertIsNotNone(order.accepted_at)
        self.assertRedirects(r, reverse("orders:staff_list"))

        r = self.client.post(reverse("orders:staff_advance", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SERVIE)
        self.assertIsNotNone(order.served_at)
        self.assertRedirects(r, reverse("orders:staff_invoice", args=[order.pk]))

    def test_legacy_prep_and_ready_serve_next(self):
        self._login()
        for status in (Order.Status.EN_PREPARATION, Order.Status.PRETE):
            order = self._order(status=status)
            self.assertTrue(order.is_accepted_like)
            self.assertEqual(order.next_status, Order.Status.SERVIE)
            r = self.client.post(reverse("orders:staff_advance", args=[order.pk]))
            order.refresh_from_db()
            self.assertEqual(order.status, Order.Status.SERVIE)
            self.assertRedirects(r, reverse("orders:staff_invoice", args=[order.pk]))

    def test_cannot_pay_before_served(self):
        order = self._order()
        self._login("serveur")
        r = self.client.get(reverse("orders:staff_pay", args=[order.pk]))
        self.assertRedirects(r, reverse("tables:serveur_home"))
        r = self.client.post(reverse("orders:staff_mark_paid", args=[order.pk]), {"release_table": "1"})
        self.assertRedirects(r, reverse("tables:serveur_home"))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EN_ATTENTE)
        self.assertFalse(CashEntry.objects.filter(order=order).exists())

        order.status = Order.Status.ACCEPTEE
        order.save(update_fields=["status"])
        r = self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"release_table": "1", "from_scan": "1"},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ACCEPTEE)

    def test_serve_opens_invoice(self):
        order = self._order(status=Order.Status.ACCEPTEE)
        self._login()
        self.client.post(reverse("orders:staff_advance", args=[order.pk]))
        order.refresh_from_db()
        r = self.client.get(reverse("orders:staff_invoice", args=[order.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Facture")
        self.assertContains(r, order.invoice_token)
        self.assertTrue(order.invoice_token)

        png = self.client.get(reverse("orders:invoice_qr_png", args=[order.invoice_token]))
        self.assertEqual(png.status_code, 200)
        self.assertEqual(png["Content-Type"], "image/png")

    def test_invoice_hidden_until_served(self):
        order = self._order()
        self._login()
        r = self.client.get(reverse("orders:staff_invoice", args=[order.pk]))
        self.assertRedirects(r, reverse("orders:staff_detail", args=[order.pk]))

    def test_scan_pay_and_release_table(self):
        order = self._order(status=Order.Status.SERVIE)
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self._login("serveur")

        scan = self.client.get(reverse("orders:invoice_scan", args=[order.invoice_token]))
        self.assertEqual(scan.status_code, 200)
        self.assertContains(scan, "Régler et libérer la table")
        self.assertContains(scan, "Régler seulement")

        r = self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {
                "release_table": "1",
                "from_scan": "1",
                "next": reverse("orders:staff_detail", args=[order.pk]),
            },
        )
        order.refresh_from_db()
        self.table.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYEE)
        self.assertEqual(self.table.status, Table.Status.LIBRE)
        self.assertTrue(CashEntry.objects.filter(order=order, type=CashEntry.Type.IN).exists())
        self.assertRedirects(r, reverse("orders:staff_detail", args=[order.pk]))

    def test_scan_pay_keep_table(self):
        order = self._order(status=Order.Status.SERVIE)
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self._login("serveur")
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"from_scan": "1", "release_table": "0"},
        )
        order.refresh_from_db()
        self.table.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYEE)
        self.assertEqual(self.table.status, Table.Status.OCCUPEE)

    def test_scan_requires_encaisser(self):
        order = self._order(status=Order.Status.SERVIE)
        self._login("cuisine")
        r = self.client.get(reverse("orders:invoice_scan", args=[order.invoice_token]))
        self.assertEqual(r.status_code, 302)

    def test_list_shows_accept_and_serve(self):
        waiting = self._order()
        accepted = self._order(status=Order.Status.ACCEPTEE)
        served = self._order(status=Order.Status.SERVIE)
        self._login()
        r = self.client.get(reverse("orders:staff_list"))
        self.assertContains(r, "Accepter")
        self.assertContains(r, "Servir")
        self.assertContains(r, "Facture réglée")
        self.assertNotContains(r, "Préparer")
        detail = self.client.get(reverse("orders:staff_detail", args=[served.pk]))
        self.assertContains(detail, "Pizza")
        self.assertContains(detail, "Ce que le client a commandé")
        self.assertContains(
            self.client.get(reverse("orders:staff_detail", args=[accepted.pk])),
            "Servir",
        )

    def _fill_cart(self):
        session = self.client.session
        session["cart"] = {"items": {str(self.dish.pk): 1}}
        session.save()

    def test_checkout_requires_contact(self):
        self._fill_cart()
        r = self.client.post(
            reverse("orders:checkout_submit"),
            {"token": self.table.qr_token},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_checkout_with_whatsapp(self):
        self._fill_cart()
        r = self.client.post(
            reverse("orders:checkout_submit"),
            {"token": self.table.qr_token, "guest_phone": "+243900000000"},
        )
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual(order.guest_phone, "+243900000000")
        self.assertRedirects(
            r, reverse("orders:confirmation", args=[self.table.qr_token, order.invoice_token])
        )

    def test_checkout_creates_client_account(self):
        self._fill_cart()
        self.client.post(
            reverse("orders:checkout_submit"),
            {
                "token": self.table.qr_token,
                "guest_email": "ada@example.com",
                "create_account": "1",
                "password": "secret1234",
            },
        )
        order = Order.objects.get()
        self.assertEqual(order.customer.role, User.Role.CLIENT)
        self.assertEqual(order.customer.email, "ada@example.com")
        page = self.client.get(reverse("orders:client_invoices"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f"#{order.pk}")

    def test_table_qr_does_not_free_for_waiter(self):
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self._login("serveur")
        r = self.client.get(reverse("orders:menu", args=[self.table.qr_token]))
        self.assertRedirects(r, reverse("menu:public"), fetch_redirect_response=False)
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.OCCUPEE)

    def test_serveur_hub_not_staff_orders(self):
        self._order()
        self._login("serveur")
        r = self.client.get(reverse("orders:staff_list"))
        self.assertRedirects(r, reverse("tables:serveur_home"))
        home = self.client.get(reverse("tables:serveur_home"))
        self.assertContains(home, "Accepter")
        self.assertContains(home, "scanner la facture")
        self.assertContains(home, "Régler et libérer la table")
        self.assertContains(home, "Régler seulement")
        self.assertContains(home, "Salle")
        self.assertNotContains(home, "Facture réglée")

    def test_public_invoice_after_serve(self):
        order = self._order(status=Order.Status.SERVIE)
        r = self.client.get(reverse("orders:public_invoice", args=[order.invoice_token]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Facture")
        self.assertContains(r, "Pizza")

    def test_confirmation_uses_invoice_token_not_pk(self):
        order = self._order()
        order.guest_phone = "+243900000000"
        order.guest_email = "secret@example.com"
        order.save(update_fields=["guest_phone", "guest_email"])
        ok = self.client.get(
            reverse("orders:confirmation", args=[self.table.qr_token, order.invoice_token])
        )
        self.assertEqual(ok.status_code, 200)
        self.assertContains(ok, f"N°{order.pk}")
        self.assertNotContains(ok, "+243900000000")
        self.assertNotContains(ok, "secret@example.com")
        self.assertNotContains(ok, "wa.me")
        guess = self.client.get(
            f"/order/{self.table.qr_token}/confirmation/{order.pk}/"
        )
        self.assertEqual(guess.status_code, 404)
        other = self.client.get(
            reverse("orders:confirmation", args=[self.table.qr_token, "0" * 32])
        )
        self.assertEqual(other.status_code, 404)

    def test_double_mark_paid_one_cash_entry(self):
        order = self._order(status=Order.Status.SERVIE)
        self._login()
        url = reverse("orders:staff_mark_paid", args=[order.pk])
        self.client.post(url, {"release_table": "1"})
        self.client.post(url, {"release_table": "1"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYEE)
        self.assertEqual(CashEntry.objects.filter(order=order).count(), 1)

    def test_mark_paid_idempotent_on_model(self):
        order = self._order(status=Order.Status.SERVIE)
        first = order.mark_paid(self.admin)
        second = order.mark_paid(self.admin)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(CashEntry.objects.filter(order=order).count(), 1)

    def test_cancel_releases_idle_table(self):
        order = self._order(status=Order.Status.EN_ATTENTE)
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self._login()
        self.client.post(reverse("orders:staff_cancel", args=[order.pk]))
        order.refresh_from_db()
        self.table.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ANNULEE)
        self.assertEqual(self.table.status, Table.Status.LIBRE)

    def test_cancel_keeps_table_if_other_open_order(self):
        first = self._order(status=Order.Status.EN_ATTENTE)
        self._order(status=Order.Status.ACCEPTEE)
        self.table.status = Table.Status.OCCUPEE
        self.table.save(update_fields=["status"])
        self._login()
        self.client.post(reverse("orders:staff_cancel", args=[first.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.OCCUPEE)

    def test_invoice_email_on_serve(self):
        from django.core import mail

        from core.models import Restaurant

        resto = Restaurant.get_solo()
        resto.email = "resto@example.com"
        resto.save(update_fields=["email"])
        order = self._order(status=Order.Status.ACCEPTEE)
        order.guest_email = "guest@example.com"
        order.save(update_fields=["guest_email"])
        self._login()
        self.client.post(reverse("orders:staff_advance", args=[order.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["guest@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "resto@example.com")
        self.assertIn(order.invoice_token, mail.outbox[0].body)

    def _edit(self, pk, action, dish_id, **extra):
        data = {"action": action, "dish_id": str(dish_id)}
        data.update(extra)
        return self.client.post(reverse("orders:staff_edit_item", args=[pk]), data)

    def test_edit_increases_quantity(self):
        order = self._order()
        self._login("serveur")
        self._edit(order.pk, "inc", self.dish.pk)
        order.refresh_from_db()
        item = order.items.get()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(order.total, Decimal("30.00"))

    def test_edit_adds_new_dish(self):
        cat = Category.objects.create(name_fr="Boissons", position=2)
        drink = Dish.objects.create(category=cat, name_fr="Jus", price=Decimal("5.00"))
        order = self._order()
        self._login("serveur")
        self._edit(order.pk, "set", drink.pk, quantity="2")
        order.refresh_from_db()
        self.assertEqual(order.items.filter(dish=drink).count(), 1)
        self.assertEqual(order.items.filter(dish=drink).get().quantity, 2)
        self.assertEqual(order.total, Decimal("30.00"))

    def test_edit_dec_removes_item_when_zero(self):
        order = self._order()
        self._login("serveur")
        self._edit(order.pk, "dec", self.dish.pk)
        self._edit(order.pk, "dec", self.dish.pk)
        order.refresh_from_db()
        self.assertFalse(order.items.exists())
        self.assertEqual(order.total, Decimal("0.00"))

    def test_edit_remove_item(self):
        order = self._order()
        self._login("serveur")
        self._edit(order.pk, "remove", self.dish.pk)
        order.refresh_from_db()
        self.assertFalse(order.items.exists())

    def test_edit_recomputes_total_with_discount_cap(self):
        order = self._order()
        order.apply_discount(Decimal("8.00"), "bon client", self.admin, auto_approve=True)
        order.refresh_from_db()
        self._login()
        self._edit(order.pk, "dec", self.dish.pk)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("2.00"))
        self.assertEqual(order.discount_amount, Decimal("8.00"))

    def test_edit_blocked_after_paid(self):
        order = self._order(status=Order.Status.SERVIE)
        order.mark_paid(self.admin)
        self._login()
        self._edit(order.pk, "inc", self.dish.pk)
        order.refresh_from_db()
        self.assertEqual(order.items.get().quantity, 2)

    def test_payment_method_cash_creates_cash_entry(self):
        order = self._order(status=Order.Status.SERVIE)
        self._login()
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"release_table": "1", "payment_method": Order.PaymentMethod.ESPECES},
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.ESPECES)
        self.assertTrue(CashEntry.objects.filter(order=order, type=CashEntry.Type.IN).exists())

    def test_mobile_payment_no_cash_entry(self):
        order = self._order(status=Order.Status.SERVIE)
        self._login()
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"release_table": "1", "payment_method": Order.PaymentMethod.ORANGE},
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.ORANGE)
        self.assertFalse(CashEntry.objects.filter(order=order).exists())

    def test_mobile_payment_invalid_method_falls_back_to_cash(self):
        order = self._order(status=Order.Status.SERVIE)
        self._login()
        self.client.post(
            reverse("orders:staff_mark_paid", args=[order.pk]),
            {"payment_method": "bitcoin"},
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.ESPECES)


class StaffEditTemplateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pass1234", role=User.Role.ADMIN
        )
        self.client.login(username="admin", password="pass1234")
        self.table = Table.objects.create(number=1, status=Table.Status.OCCUPEE)
        cat = Category.objects.create(name_fr="Plats", position=1)
        Dish.objects.create(category=cat, name_fr="Pizza", price="10.00")
        Dish.objects.create(category=cat, name_fr="Coca", price="2.00")

    def _order(self, status=Order.Status.EN_ATTENTE):
        order = Order.objects.create(table=self.table, status=status)
        order.refresh_total()
        return order

    def test_staff_order_detail_edit_section_renders(self):
        order = self._order()
        r = self.client.get(reverse("orders:staff_detail", args=[order.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Modifier la commande")
        self.assertContains(r, "staff/orders/%s/plats" % order.pk)
        self.assertContains(r, "Ajouter au plat")

    def test_staff_detail_hides_edit_when_paid(self):
        order = self._order()
        order.status = Order.Status.PAYEE
        order.save(update_fields=["status"])
        r = self.client.get(reverse("orders:staff_detail", args=[order.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "staff/orders/%s/plats" % order.pk)

    def test_pay_confirm_lists_payment_methods(self):
        order = self._order(status=Order.Status.SERVIE)
        r = self.client.get(reverse("orders:staff_pay", args=[order.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Espèces")
        self.assertContains(r, "Mobile Money")
        self.assertContains(r, "Orange")
        self.assertContains(r, "Airtel")

    def test_invoice_scan_lists_payment_methods(self):
        order = self._order(status=Order.Status.SERVIE)
        r = self.client.get(reverse("orders:invoice_scan", args=[order.invoice_token]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Espèces")
