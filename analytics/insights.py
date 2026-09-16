"""Deterministic observations from a computed report. Never invent figures."""

from __future__ import annotations

from decimal import Decimal

from django.utils.translation import gettext as _

from .services import AnalyticsReport, ZERO


def _fmt_pct(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _fmt_money(value: Decimal, currency: str) -> str:
    return f"{value.quantize(Decimal('0.01'))} {currency}"


def build_insights(report: AnalyticsReport) -> list[str]:
    notes: list[str] = []
    currency = report.currency

    pct = report.revenue.pct
    if pct is not None:
        if pct > 0:
            notes.append(
                _("Le chiffre d'affaires a augmenté de %(pct)s %% par rapport à la période précédente.")
                % {"pct": _fmt_pct(pct)}
            )
        elif pct < 0:
            notes.append(
                _("Le chiffre d'affaires a diminué de %(pct)s %% par rapport à la période précédente.")
                % {"pct": _fmt_pct(abs(pct))}
            )
        else:
            notes.append(_("Le chiffre d'affaires est identique à la période précédente."))

    if report.top_dishes and report.net_revenue > ZERO:
        top = report.top_dishes[0]
        if top.share_pct is not None:
            notes.append(
                _("« %(name)s » représente %(pct)s %% du chiffre d'affaires.")
                % {"name": top.name, "pct": _fmt_pct(top.share_pct)}
            )

    if report.peak_hour is not None and any(c for _h, c in report.hourly):
        hour = report.peak_hour
        count = dict(report.hourly).get(hour, 0)
        notes.append(
            _("La tranche %(start)02dh–%(end)02dh est la plus active (%(n)s commande(s)).")
            % {"start": hour, "end": (hour + 1) % 24, "n": count}
        )

    if report.orders_cancelled.current > report.orders_cancelled.previous:
        notes.append(
            _("Les annulations sont supérieures à la période précédente (%(now)s contre %(prev)s).")
            % {
                "now": int(report.orders_cancelled.current),
                "prev": int(report.orders_cancelled.previous),
            }
        )

    if report.gross_revenue > ZERO and report.discount_approved_amount > ZERO and not report.filters.has_item_scope:
        share = (report.discount_approved_amount / report.gross_revenue) * Decimal("100")
        notes.append(
            _("Les remises représentent %(pct)s %% du chiffre d'affaires brut (%(amt)s).")
            % {
                "pct": _fmt_pct(share),
                "amt": _fmt_money(report.discount_approved_amount, currency),
            }
        )

    gap = report.cash.vs_revenue_gap
    if gap != ZERO:
        notes.append(
            _(
                "Écart entre le CA des commandes payées et les encaissements liés aux commandes : %(amt)s."
            )
            % {"amt": _fmt_money(gap, currency)}
        )

    return notes
