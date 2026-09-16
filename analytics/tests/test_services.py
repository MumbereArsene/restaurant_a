from datetime import datetime
from decimal import Decimal

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from analytics.periods import resolve_period
from analytics.services import ReportFilters, build_report, parse_filters
from cash.models import CashEntry
from orders.models import Order

from .helpers import (
    aware,
    make_cash,
    make_menu,
    make_order,
    make_reservation,
    make_table,
    make_user,
)


class AnalyticsServiceTests(TestCase):
    def setUp(self):
        self.now = aware(datetime(2026, 8, 30, 15, 0))
        self.period = resolve_period("today", now=self.now)
        self.starters, self.mains, self.salad, self.pizza = make_menu()
        self.table = make_table(1)
        self.table2 = make_table(2)
        self.admin = make_user("admin", "admin")

    def _report(self, **kwargs):
        filters = ReportFilters(period=self.period, **kwargs)
        return build_report(filters)

    def test_empty_period(self):
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("0"))
        self.assertEqual(report.orders_total.current, 0)
        self.assertEqual(report.avg_ticket.current, Decimal("0"))
        self.assertEqual(report.cancel_rate.current, Decimal("0"))
        self.assertEqual(report.cash.total_in, Decimal("0"))

    def test_single_paid_order_revenue(self):
        make_order(table=self.table, dish=self.pizza, qty=2, when=self.now)
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("20.00"))
        self.assertEqual(report.orders_paid.current, 1)
        self.assertEqual(report.avg_ticket.current, Decimal("20.00"))
        self.assertEqual(report.top_dishes[0].name, "Pizza")
        self.assertEqual(report.top_dishes[0].quantity, 2)
        self.assertEqual(report.top_dishes[0].revenue, Decimal("20.00"))

    def test_unpaid_order_is_not_revenue(self):
        make_order(
            table=self.table,
            dish=self.pizza,
            status=Order.Status.EN_ATTENTE,
            when=self.now,
        )
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("0"))
        self.assertEqual(report.orders_total.current, 1)
        self.assertEqual(report.orders_open, 1)
        self.assertEqual(report.orders_paid.current, 0)
        self.assertEqual(report.top_dishes, [])

    def test_cancelled_order_excluded_from_revenue(self):
        make_order(
            table=self.table,
            dish=self.pizza,
            status=Order.Status.ANNULEE,
            when=self.now,
        )
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("0"))
        self.assertEqual(report.orders_cancelled.current, 1)
        self.assertEqual(report.cancel_rate.current, Decimal("100"))

    def test_all_cancelled(self):
        make_order(table=self.table, dish=self.pizza, status=Order.Status.ANNULEE, when=self.now)
        make_order(table=self.table, dish=self.salad, status=Order.Status.ANNULEE, when=self.now)
        report = self._report()
        self.assertEqual(report.orders_total.current, 2)
        self.assertEqual(report.orders_cancelled.current, 2)
        self.assertEqual(report.revenue.current, Decimal("0"))
        self.assertEqual(report.avg_ticket.current, Decimal("0"))

    def test_approved_discount_net_and_gross(self):
        make_order(
            table=self.table,
            dish=self.pizza,
            qty=1,
            when=self.now,
            discount_amount=Decimal("2.00"),
            discount_status="approved",
            discount_requested_by=self.admin,
        )
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("8.00"))
        self.assertEqual(report.gross_revenue, Decimal("10.00"))
        self.assertEqual(report.net_revenue, Decimal("8.00"))
        self.assertEqual(report.discount_approved_count, 1)
        self.assertEqual(report.discount_approved_amount, Decimal("2.00"))

    def test_rejected_discount_keeps_amount(self):
        order = make_order(
            table=self.table,
            dish=self.pizza,
            when=self.now,
            discount_amount=Decimal("3.00"),
            discount_status="pending",
            discount_requested_by=self.admin,
        )
        self.assertTrue(order.reject_discount(self.admin))
        order.refresh_from_db()
        self.assertEqual(order.discount_status, "rejected")
        self.assertEqual(order.discount_amount, Decimal("3.00"))
        report = self._report()
        self.assertEqual(report.discount_rejected_count, 1)
        self.assertEqual(report.discount_rejected_amount, Decimal("3.00"))
        self.assertEqual(report.revenue.current, Decimal("10.00"))

    def test_category_and_dish_filters_use_line_totals(self):
        make_order(table=self.table, dish=self.pizza, qty=1, when=self.now)
        make_order(table=self.table, dish=self.salad, qty=1, when=self.now)
        pizza_only = self._report(dish_id=self.pizza.pk)
        self.assertEqual(pizza_only.revenue.current, Decimal("10.00"))
        self.assertEqual(pizza_only.orders_paid.current, 1)
        starters = self._report(category_id=self.starters.pk)
        self.assertEqual(starters.revenue.current, Decimal("5.00"))

    def test_table_stats(self):
        make_order(table=self.table, dish=self.pizza, when=self.now)
        make_order(table=self.table2, dish=self.salad, when=self.now)
        report = self._report()
        by_number = {row.number: row for row in report.tables}
        self.assertEqual(by_number[1].orders, 1)
        self.assertEqual(by_number[1].revenue, Decimal("10.00"))
        self.assertEqual(by_number[2].revenue, Decimal("5.00"))
        self.assertEqual(report.table_count, 2)

    def test_hourly_and_peak(self):
        make_order(table=self.table, dish=self.pizza, when=self.now)
        report = self._report()
        self.assertEqual(report.peak_hour, 15)
        self.assertEqual(dict(report.hourly)[15], 1)

    def test_reservations(self):
        day = self.now.date()
        make_reservation(on_date=day, status="confirmee", guests=4)
        make_reservation(name="Bob", on_date=day, status="annulee", guests=2)
        report = self._report()
        self.assertEqual(report.reservations.total, 2)
        self.assertEqual(report.reservations.confirmed, 1)
        self.assertEqual(report.reservations.cancelled, 1)
        self.assertEqual(report.reservations.guests, 6)
        self.assertEqual(report.reservations.confirm_rate, Decimal("50"))

    def test_cash_vs_revenue_gap(self):
        order = make_order(table=self.table, dish=self.pizza, when=self.now)
        make_cash(amount=Decimal("10.00"), order=order, when=self.now, user=self.admin)
        make_cash(amount=Decimal("3.00"), order=None, when=self.now, user=self.admin)
        make_cash(amount=Decimal("1.00"), entry_type=CashEntry.Type.OUT, when=self.now)
        report = self._report()
        self.assertEqual(report.cash.order_in, Decimal("10.00"))
        self.assertEqual(report.cash.manual_in, Decimal("3.00"))
        self.assertEqual(report.cash.total_out, Decimal("1.00"))
        self.assertEqual(report.cash.vs_revenue_gap, Decimal("0.00"))
        self.assertEqual(report.cash.balance, Decimal("12.00"))

    def test_period_comparison(self):
        yesterday = aware(datetime(2026, 8, 29, 15, 0))
        make_order(table=self.table, dish=self.pizza, qty=1, when=yesterday, paid_at=yesterday)
        make_order(table=self.table, dish=self.pizza, qty=2, when=self.now)
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("20.00"))
        self.assertEqual(report.revenue.previous, Decimal("10.00"))
        self.assertEqual(report.revenue.pct, Decimal("100"))

    def test_paid_outside_period_ignored(self):
        old = aware(datetime(2026, 8, 1, 12, 0))
        make_order(table=self.table, dish=self.pizza, when=old, paid_at=old)
        report = self._report()
        self.assertEqual(report.revenue.current, Decimal("0"))

    def test_currency_from_settings(self):
        with override_settings(CURRENCY="FC"):
            report = self._report()
        self.assertEqual(report.currency, "FC")

    def test_parse_filters_from_request(self):
        rf = RequestFactory()
        request = rf.get(
            "/staff/analytics/",
            {"period": "custom", "from": "2026-08-01", "to": "2026-08-15", "status": "payee"},
        )
        filters = parse_filters(request, now=self.now)
        self.assertEqual(filters.period.preset, "custom")
        self.assertEqual(filters.status, "payee")
        self.assertEqual(filters.period.start_date.isoformat(), "2026-08-01")

    def test_category_rows(self):
        make_order(table=self.table, dish=self.pizza, qty=3, when=self.now)
        make_order(table=self.table, dish=self.salad, qty=1, when=self.now)
        report = self._report()
        names = {row.name: row for row in report.categories}
        self.assertEqual(names["Plats"].quantity, 3)
        self.assertEqual(names["Entrées"].revenue, Decimal("5.00"))

    def test_exports_do_not_raise(self):
        make_order(table=self.table, dish=self.pizza, when=self.now)
        report = self._report()
        from analytics.exports import build_pdf, build_xlsx

        xlsx = build_xlsx(report)
        pdf = build_pdf(report)
        self.assertGreater(len(xlsx), 100)
        self.assertGreater(len(pdf), 100)
        self.assertTrue(xlsx[:2] == b"PK")
        self.assertTrue(pdf.startswith(b"%PDF"))
