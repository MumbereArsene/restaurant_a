"""Staff-only analytics dashboard and exports."""

from __future__ import annotations

import json
from decimal import Decimal

from django.shortcuts import render
from django.utils.translation import gettext as _

from accounts.permissions import analytics_required
from menu.models import Category, Dish
from orders.models import Order
from tables.models import Table

from .exports import pdf_response, xlsx_response
from .periods import PRESETS
from .services import build_report, parse_filters


def _decimal_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(type(value))


def _chart_payload(report) -> str:
    status_labels = dict(Order.Status.choices)
    payload = {
        "revenueLabels": [label for label, _v in report.revenue_series],
        "revenueCurrent": [float(v) for _l, v in report.revenue_series],
        "revenuePrevLabels": [label for label, _v in report.revenue_series_prev],
        "revenuePrev": [float(v) for _l, v in report.revenue_series_prev],
        "statusLabels": [str(status_labels[key]) for key in report.status_counts],
        "statusValues": [report.status_counts[key] for key in report.status_counts],
        "hourlyLabels": [f"{h:02d}h" for h, _n in report.hourly],
        "hourlyValues": [n for _h, n in report.hourly],
        "dishLabels": [row.name for row in report.top_dishes[:5]],
        "dishValues": [float(row.revenue) for row in report.top_dishes[:5]],
        "categoryLabels": [row.name for row in report.categories],
        "categoryValues": [float(row.revenue) for row in report.categories],
        "currency": report.currency,
        "revenueLabel": str(_("CA")),
        "previousLabel": str(_("Période précédente")),
        "ordersLabel": str(_("Commandes")),
    }
    return json.dumps(payload, default=_decimal_default)


def _context(request):
    filters = parse_filters(request)
    report = build_report(filters)
    query = request.GET.copy()
    query.pop("page", None)
    return {
        "report": report,
        "filters": filters,
        "period": filters.period,
        "presets": PRESETS,
        "categories": Category.objects.filter(is_active=True),
        "dishes": Dish.objects.filter(is_active=True).select_related("category"),
        "tables": Table.objects.all(),
        "order_statuses": Order.Status.choices,
        "chart_json": _chart_payload(report),
        "export_query": query.urlencode(),
    }


@analytics_required
def dashboard(request):
    context = _context(request)
    if request.headers.get("HX-Request"):
        return render(request, "analytics/partials/body.html", context)
    return render(request, "analytics/dashboard.html", context)


@analytics_required
def export_xlsx(request):
    report = build_report(parse_filters(request))
    return xlsx_response(report)


@analytics_required
def export_pdf(request):
    report = build_report(parse_filters(request))
    return pdf_response(report)
