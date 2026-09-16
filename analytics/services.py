"""Aggregated analytics report — SQL-side, no invented metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.translation import gettext as _

from cash.models import CashClosure, CashEntry
from core.models import AuditLog
from menu.models import Dish
from orders.models import Order, OrderItem
from reservations.models import Reservation
from tables.models import Table

from .periods import PeriodWindow, resolve_period

ZERO = Decimal("0")


def _with_line(qs):
    return qs.annotate(_line=F("unit_price") * F("quantity"))


def _sum_line_field():
    return Sum("_line", output_field=DecimalField(max_digits=14, decimal_places=2))


OPEN_STATUSES = (
    Order.Status.EN_ATTENTE,
    Order.Status.ACCEPTEE,
    Order.Status.EN_PREPARATION,
    Order.Status.PRETE,
    Order.Status.SERVIE,
)


@dataclass
class ReportFilters:
    period: PeriodWindow
    category_id: int | None = None
    dish_id: int | None = None
    table_id: int | None = None
    status: str = ""

    @property
    def has_item_scope(self) -> bool:
        return bool(self.category_id or self.dish_id)


@dataclass
class Delta:
    current: Decimal
    previous: Decimal

    @property
    def difference(self) -> Decimal:
        return self.current - self.previous

    @property
    def pct(self) -> Decimal | None:
        if self.previous == 0:
            return None
        return ((self.current - self.previous) / self.previous) * Decimal("100")


@dataclass
class DishRow:
    dish_id: int
    name: str
    quantity: int
    revenue: Decimal
    share_pct: Decimal | None


@dataclass
class CategoryRow:
    category_id: int
    name: str
    quantity: int
    revenue: Decimal
    share_pct: Decimal | None


@dataclass
class TableRow:
    table_id: int
    number: int
    orders: int
    revenue: Decimal


@dataclass
class StaffRow:
    user_id: int | None
    name: str
    count: int
    amount: Decimal = ZERO


@dataclass
class ReservationStats:
    total: int = 0
    pending: int = 0
    confirmed: int = 0
    refused: int = 0
    cancelled: int = 0
    guests: int = 0
    confirm_rate: Decimal | None = None
    cancel_rate: Decimal | None = None
    by_weekday: list[tuple[int, int]] = field(default_factory=list)
    by_hour: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class CashStats:
    total_in: Decimal = ZERO
    total_out: Decimal = ZERO
    balance: Decimal = ZERO
    manual_in: Decimal = ZERO
    order_in: Decimal = ZERO
    closures: int = 0
    closure_gap_sum: Decimal = ZERO
    vs_revenue_gap: Decimal = ZERO


@dataclass
class AnalyticsReport:
    filters: ReportFilters
    currency: str
    restaurant_name: str
    generated_at: datetime
    revenue: Delta
    orders_total: Delta
    orders_paid: Delta
    orders_cancelled: Delta
    orders_open: int
    avg_ticket: Delta
    cancel_rate: Delta
    discount_count: int
    discount_approved_count: int
    discount_rejected_count: int
    discount_pending_count: int
    discount_approved_amount: Decimal
    discount_rejected_amount: Decimal
    gross_revenue: Decimal
    net_revenue: Decimal
    status_counts: dict[str, int]
    revenue_series: list[tuple[str, Decimal]]
    revenue_series_prev: list[tuple[str, Decimal]]
    hourly: list[tuple[int, int]]
    peak_hour: int | None
    top_dishes: list[DishRow]
    bottom_dishes: list[DishRow]
    categories: list[CategoryRow]
    tables: list[TableRow]
    table_count: int
    reservations: ReservationStats
    cash: CashStats
    discounts_by_requester: list[StaffRow]
    cash_in_by_staff: list[StaffRow]
    cancellations_by_staff: list[StaffRow]
    insights: list[str] = field(default_factory=list)


def _dec(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole == 0:
        return None
    return (part / whole) * Decimal("100")


def _rate(num: int, den: int) -> Decimal | None:
    if den == 0:
        return None
    return (Decimal(num) / Decimal(den)) * Decimal("100")


def _int(value) -> int:
    return int(value or 0)


def parse_filters(request, *, now: datetime | None = None) -> ReportFilters:
    preset = (request.GET.get("period") or "today").strip()
    raw_from = request.GET.get("from") or ""
    raw_to = request.GET.get("to") or ""
    date_from = _parse_date(raw_from)
    date_to = _parse_date(raw_to)
    period = resolve_period(preset, date_from, date_to, now=now)

    def _int_or_none(key: str) -> int | None:
        raw = (request.GET.get(key) or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    status = (request.GET.get("status") or "").strip()
    valid = {c.value for c in Order.Status}
    if status not in valid:
        status = ""

    return ReportFilters(
        period=period,
        category_id=_int_or_none("category"),
        dish_id=_int_or_none("dish"),
        table_id=_int_or_none("table"),
        status=status,
    )


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _apply_order_filters(qs, filters: ReportFilters):
    if filters.table_id:
        qs = qs.filter(table_id=filters.table_id)
    if filters.status:
        qs = qs.filter(status=filters.status)
    if filters.dish_id:
        qs = qs.filter(items__dish_id=filters.dish_id)
    elif filters.category_id:
        qs = qs.filter(items__dish__category_id=filters.category_id)
    if filters.dish_id or filters.category_id:
        qs = qs.distinct()
    return qs


def _apply_item_filters(qs, filters: ReportFilters):
    if filters.table_id:
        qs = qs.filter(order__table_id=filters.table_id)
    if filters.status:
        qs = qs.filter(order__status=filters.status)
    if filters.dish_id:
        qs = qs.filter(dish_id=filters.dish_id)
    elif filters.category_id:
        qs = qs.filter(dish__category_id=filters.category_id)
    return qs


def _created_qs(filters: ReportFilters, start: datetime, end: datetime):
    return _apply_order_filters(
        Order.objects.filter(created_at__gte=start, created_at__lt=end),
        filters,
    )


def _paid_qs(filters: ReportFilters, start: datetime, end: datetime):
    return _apply_order_filters(
        Order.objects.filter(
            status=Order.Status.PAYEE,
            paid_at__gte=start,
            paid_at__lt=end,
        ),
        filters,
    )


def _paid_items(filters: ReportFilters, start: datetime, end: datetime):
    return _apply_item_filters(
        OrderItem.objects.filter(
            order__status=Order.Status.PAYEE,
            order__paid_at__gte=start,
            order__paid_at__lt=end,
        ),
        filters,
    )


def _sum_paid_revenue(filters: ReportFilters, start: datetime, end: datetime) -> Decimal:
    if filters.has_item_scope:
        return _dec(_with_line(_paid_items(filters, start, end)).aggregate(s=_sum_line_field())["s"])
    return _dec(_paid_qs(filters, start, end).aggregate(s=Sum("total"))["s"])


def _count_created(filters: ReportFilters, start: datetime, end: datetime) -> int:
    return _created_qs(filters, start, end).count()


def _count_paid(filters: ReportFilters, start: datetime, end: datetime) -> int:
    return _paid_qs(filters, start, end).count()


def _count_cancelled(filters: ReportFilters, start: datetime, end: datetime) -> int:
    return _created_qs(filters, start, end).filter(status=Order.Status.ANNULEE).count()


def _trunc(field: str, granularity: str):
    tz = timezone.get_current_timezone()
    if granularity == "week":
        return TruncWeek(field, tzinfo=tz)
    if granularity == "month":
        return TruncMonth(field, tzinfo=tz)
    return TruncDate(field, tzinfo=tz)


def _format_bucket(value, granularity: str) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value)
        if granularity == "month":
            return value.strftime("%Y-%m")
        if granularity == "week":
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        if granularity == "month":
            return value.strftime("%Y-%m")
        return value.strftime("%Y-%m-%d")
    return str(value)


def _revenue_series(filters: ReportFilters, start: datetime, end: datetime) -> list[tuple[str, Decimal]]:
    granularity = filters.period.granularity
    if filters.has_item_scope:
        rows = (
            _with_line(_paid_items(filters, start, end))
            .annotate(bucket=_trunc("order__paid_at", granularity))
            .values("bucket")
            .annotate(total=_sum_line_field())
            .order_by("bucket")
        )
    else:
        rows = (
            _paid_qs(filters, start, end)
            .annotate(bucket=_trunc("paid_at", granularity))
            .values("bucket")
            .annotate(total=Sum("total"))
            .order_by("bucket")
        )
    return [(_format_bucket(row["bucket"], granularity), _dec(row["total"])) for row in rows]


def _dish_rows(filters: ReportFilters, start: datetime, end: datetime, net: Decimal) -> list[DishRow]:
    rows = (
        _with_line(_paid_items(filters, start, end))
        .values("dish_id", "dish__name_fr")
        .annotate(quantity=Sum("quantity"), revenue=_sum_line_field())
        .order_by("-quantity", "-revenue")
    )
    return [
        DishRow(
            dish_id=row["dish_id"],
            name=row["dish__name_fr"],
            quantity=_int(row["quantity"]),
            revenue=_dec(row["revenue"]),
            share_pct=_pct(_dec(row["revenue"]), net),
        )
        for row in rows
    ]


def _bottom_dishes(sold: list[DishRow], filters: ReportFilters, net: Decimal) -> list[DishRow]:
    """Least sold among paid items, plus active dishes with zero sales (real zero, not invented)."""
    sold_ids = {row.dish_id for row in sold}
    extras: list[DishRow] = []
    active = Dish.objects.filter(is_active=True)
    if filters.category_id:
        active = active.filter(category_id=filters.category_id)
    if filters.dish_id:
        active = active.filter(pk=filters.dish_id)
    for dish in active.exclude(pk__in=sold_ids).only("id", "name_fr"):
        extras.append(
            DishRow(
                dish_id=dish.pk,
                name=dish.name_fr,
                quantity=0,
                revenue=ZERO,
                share_pct=_pct(ZERO, net),
            )
        )
    combined = extras + sorted(sold, key=lambda r: (r.quantity, r.revenue))
    return combined[:10]


def _category_rows(filters: ReportFilters, start: datetime, end: datetime, net: Decimal) -> list[CategoryRow]:
    rows = (
        _with_line(_paid_items(filters, start, end))
        .values("dish__category_id", "dish__category__name_fr")
        .annotate(quantity=Sum("quantity"), revenue=_sum_line_field())
        .order_by("-revenue")
    )
    return [
        CategoryRow(
            category_id=row["dish__category_id"],
            name=row["dish__category__name_fr"] or "",
            quantity=_int(row["quantity"]),
            revenue=_dec(row["revenue"]),
            share_pct=_pct(_dec(row["revenue"]), net),
        )
        for row in rows
    ]


def _table_rows(filters: ReportFilters, start: datetime, end: datetime) -> list[TableRow]:
    volume = {
        row["table_id"]: _int(row["n"])
        for row in _created_qs(filters, start, end)
        .values("table_id")
        .annotate(n=Count("id", distinct=True))
    }
    if filters.has_item_scope:
        revenue_rows = (
            _with_line(_paid_items(filters, start, end))
            .values("order__table_id")
            .annotate(revenue=_sum_line_field())
        )
        revenue = {row["order__table_id"]: _dec(row["revenue"]) for row in revenue_rows}
    else:
        revenue_rows = _paid_qs(filters, start, end).values("table_id").annotate(revenue=Sum("total"))
        revenue = {row["table_id"]: _dec(row["revenue"]) for row in revenue_rows}

    table_ids = set(volume) | set(revenue)
    numbers = {
        t.pk: t.number
        for t in Table.objects.filter(pk__in=table_ids).only("id", "number")
    }
    rows = [
        TableRow(
            table_id=pk,
            number=numbers.get(pk, 0),
            orders=volume.get(pk, 0),
            revenue=revenue.get(pk, ZERO),
        )
        for pk in table_ids
    ]
    rows.sort(key=lambda r: (-r.orders, -r.revenue, r.number))
    return rows


def _reservation_stats(period: PeriodWindow) -> ReservationStats:
    start_d, end_d = period.start_date, period.end_date
    qs = Reservation.objects.filter(date__gte=start_d, date__lte=end_d)
    total = qs.count()
    pending = qs.filter(status=Reservation.Status.EN_ATTENTE).count()
    confirmed = qs.filter(status=Reservation.Status.CONFIRMEE).count()
    refused = qs.filter(status=Reservation.Status.REFUSEE).count()
    cancelled = qs.filter(status=Reservation.Status.ANNULEE).count()
    guests = _int(qs.aggregate(s=Sum("guests"))["s"])
    by_weekday = [
        (_int(row["dow"]), _int(row["n"]))
        for row in qs.annotate(dow=ExtractIsoWeekDay("date")).values("dow").annotate(n=Count("id")).order_by("dow")
    ]
    by_hour = [
        (_int(row["hour"]), _int(row["n"]))
        for row in qs.annotate(hour=ExtractHour("time")).values("hour").annotate(n=Count("id")).order_by("hour")
    ]
    return ReservationStats(
        total=total,
        pending=pending,
        confirmed=confirmed,
        refused=refused,
        cancelled=cancelled,
        guests=guests,
        confirm_rate=_rate(confirmed, total),
        cancel_rate=_rate(cancelled, total),
        by_weekday=by_weekday,
        by_hour=by_hour,
    )


def _cash_stats(period: PeriodWindow, paid_revenue: Decimal) -> CashStats:
    entries = CashEntry.objects.filter(created_at__gte=period.start, created_at__lt=period.end)
    total_in = _dec(entries.filter(type=CashEntry.Type.IN).aggregate(s=Sum("amount"))["s"])
    total_out = _dec(entries.filter(type=CashEntry.Type.OUT).aggregate(s=Sum("amount"))["s"])
    order_in = _dec(
        entries.filter(type=CashEntry.Type.IN, order__isnull=False).aggregate(s=Sum("amount"))["s"]
    )
    manual_in = _dec(
        entries.filter(type=CashEntry.Type.IN, order__isnull=True).aggregate(s=Sum("amount"))["s"]
    )
    closures = CashClosure.objects.filter(closed_at__gte=period.start, closed_at__lt=period.end)
    return CashStats(
        total_in=total_in,
        total_out=total_out,
        balance=total_in - total_out,
        manual_in=manual_in,
        order_in=order_in,
        closures=closures.count(),
        closure_gap_sum=_dec(closures.aggregate(s=Sum("difference"))["s"]),
        vs_revenue_gap=order_in - paid_revenue,
    )


def _staff_name(user_id, username, first, last) -> str:
    full = f"{first or ''} {last or ''}".strip()
    if full:
        return full
    return username or _("Compte supprimé")


def _discounts_by_requester(filters: ReportFilters) -> list[StaffRow]:
    p = filters.period
    qs = _created_qs(filters, p.start, p.end).exclude(discount_status="none")
    rows = (
        qs.values(
            "discount_requested_by",
            "discount_requested_by__username",
            "discount_requested_by__first_name",
            "discount_requested_by__last_name",
        )
        .annotate(count=Count("id"), amount=Sum("discount_amount"))
        .order_by("-amount")
    )
    return [
        StaffRow(
            user_id=row["discount_requested_by"],
            name=_staff_name(
                row["discount_requested_by"],
                row["discount_requested_by__username"],
                row["discount_requested_by__first_name"],
                row["discount_requested_by__last_name"],
            ),
            count=_int(row["count"]),
            amount=_dec(row["amount"]),
        )
        for row in rows
    ]


def _cash_in_by_staff(period: PeriodWindow) -> list[StaffRow]:
    rows = (
        CashEntry.objects.filter(
            type=CashEntry.Type.IN,
            created_at__gte=period.start,
            created_at__lt=period.end,
        )
        .values("created_by", "created_by__username", "created_by__first_name", "created_by__last_name")
        .annotate(count=Count("id"), amount=Sum("amount"))
        .order_by("-amount")
    )
    return [
        StaffRow(
            user_id=row["created_by"],
            name=_staff_name(
                row["created_by"],
                row["created_by__username"],
                row["created_by__first_name"],
                row["created_by__last_name"],
            ),
            count=_int(row["count"]),
            amount=_dec(row["amount"]),
        )
        for row in rows
    ]


def _cancellations_by_staff(period: PeriodWindow) -> list[StaffRow]:
    rows = (
        AuditLog.objects.filter(
            action="order.cancel",
            created_at__gte=period.start,
            created_at__lt=period.end,
        )
        .values("actor", "actor__username", "actor__first_name", "actor__last_name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return [
        StaffRow(
            user_id=row["actor"],
            name=_staff_name(
                row["actor"],
                row["actor__username"],
                row["actor__first_name"],
                row["actor__last_name"],
            ),
            count=_int(row["count"]),
        )
        for row in rows
    ]


def build_report(filters: ReportFilters) -> AnalyticsReport:
    from core.models import Restaurant

    from .insights import build_insights

    p = filters.period
    currency = getattr(settings, "CURRENCY", "$")
    restaurant_name = Restaurant.get_solo().name

    rev_now = _sum_paid_revenue(filters, p.start, p.end)
    rev_prev = _sum_paid_revenue(filters, p.prev_start, p.prev_end)
    total_now = _count_created(filters, p.start, p.end)
    total_prev = _count_created(filters, p.prev_start, p.prev_end)
    paid_now = _count_paid(filters, p.start, p.end)
    paid_prev = _count_paid(filters, p.prev_start, p.prev_end)
    cancel_now = _count_cancelled(filters, p.start, p.end)
    cancel_prev = _count_cancelled(filters, p.prev_start, p.prev_end)
    open_now = _created_qs(filters, p.start, p.end).filter(status__in=OPEN_STATUSES).count()

    avg_now = (rev_now / paid_now) if paid_now else ZERO
    avg_prev = (rev_prev / paid_prev) if paid_prev else ZERO
    rate_now = _rate(cancel_now, total_now) or ZERO
    rate_prev = _rate(cancel_prev, total_prev) or ZERO

    created = _created_qs(filters, p.start, p.end)
    status_counts = {value: 0 for value, _label in Order.Status.choices}
    for row in created.values("status").annotate(n=Count("id", distinct=True)):
        status_counts[row["status"]] = _int(row["n"])

    discount_qs = created.exclude(discount_status="none")
    discount_agg = discount_qs.aggregate(
        count=Count("id", distinct=True),
        approved=Count("id", filter=Q(discount_status="approved"), distinct=True),
        rejected=Count("id", filter=Q(discount_status="rejected"), distinct=True),
        pending=Count("id", filter=Q(discount_status="pending"), distinct=True),
        approved_amt=Sum("discount_amount", filter=Q(discount_status="approved")),
        rejected_amt=Sum("discount_amount", filter=Q(discount_status="rejected")),
    )

    paid_for_gross = _paid_qs(filters, p.start, p.end)
    approved_on_paid = _dec(
        paid_for_gross.filter(discount_status="approved").aggregate(s=Sum("discount_amount"))["s"]
    )
    if filters.has_item_scope:
        net = rev_now
        gross = net  # item-scoped CA has no reliable order-level discount allocation
    else:
        net = rev_now
        gross = net + approved_on_paid

    tz = timezone.get_current_timezone()
    hourly_map = {h: 0 for h in range(24)}
    for row in (
        created.annotate(hour=ExtractHour("created_at", tzinfo=tz))
        .values("hour")
        .annotate(n=Count("id", distinct=True))
    ):
        hour = row["hour"]
        if hour is not None:
            hourly_map[int(hour)] = _int(row["n"])
    hourly = [(h, hourly_map[h]) for h in range(24)]
    peak_hour = max(hourly, key=lambda x: x[1])[0] if any(c for _h, c in hourly) else None

    sold = _dish_rows(filters, p.start, p.end, net)
    top_dishes = sold[:10]
    bottom = _bottom_dishes(sold, filters, net)
    categories = _category_rows(filters, p.start, p.end, net)
    tables = _table_rows(filters, p.start, p.end)

    # Unscoped paid revenue for cash comparison (cash is not item-filtered)
    unscoped = ReportFilters(period=p)
    cash_paid_ca = _sum_paid_revenue(unscoped, p.start, p.end)

    report = AnalyticsReport(
        filters=filters,
        currency=currency,
        restaurant_name=restaurant_name,
        generated_at=timezone.localtime(),
        revenue=Delta(rev_now, rev_prev),
        orders_total=Delta(Decimal(total_now), Decimal(total_prev)),
        orders_paid=Delta(Decimal(paid_now), Decimal(paid_prev)),
        orders_cancelled=Delta(Decimal(cancel_now), Decimal(cancel_prev)),
        orders_open=open_now,
        avg_ticket=Delta(avg_now, avg_prev),
        cancel_rate=Delta(rate_now, rate_prev),
        discount_count=_int(discount_agg["count"]),
        discount_approved_count=_int(discount_agg["approved"]),
        discount_rejected_count=_int(discount_agg["rejected"]),
        discount_pending_count=_int(discount_agg["pending"]),
        discount_approved_amount=_dec(discount_agg["approved_amt"]),
        discount_rejected_amount=_dec(discount_agg["rejected_amt"]),
        gross_revenue=gross,
        net_revenue=net,
        status_counts=status_counts,
        revenue_series=_revenue_series(filters, p.start, p.end),
        revenue_series_prev=_revenue_series(filters, p.prev_start, p.prev_end),
        hourly=hourly,
        peak_hour=peak_hour,
        top_dishes=top_dishes,
        bottom_dishes=bottom,
        categories=categories,
        tables=tables,
        table_count=Table.objects.count(),
        reservations=_reservation_stats(p),
        cash=_cash_stats(p, cash_paid_ca),
        discounts_by_requester=_discounts_by_requester(filters),
        cash_in_by_staff=_cash_in_by_staff(p),
        cancellations_by_staff=_cancellations_by_staff(p),
    )
    report.insights = build_insights(report)
    return report
