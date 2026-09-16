"""Period presets and previous-period math (timezone-aware, exclusive end)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _


PRESETS = (
    ("today", _("Aujourd'hui")),
    ("yesterday", _("Hier")),
    ("last_7", _("7 derniers jours")),
    ("last_30", _("30 derniers jours")),
    ("this_month", _("Ce mois")),
    ("last_month", _("Mois précédent")),
    ("this_year", _("Cette année")),
    ("custom", _("Période personnalisée")),
)

PRESET_KEYS = {key for key, _label in PRESETS}


@dataclass(frozen=True)
class PeriodWindow:
    preset: str
    start: datetime
    end: datetime  # exclusive
    prev_start: datetime
    prev_end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def start_date(self) -> date:
        return timezone.localtime(self.start).date()

    @property
    def end_date(self) -> date:
        """Inclusive last calendar day of the window."""
        return timezone.localtime(self.end - timedelta(microseconds=1)).date()

    @property
    def days(self) -> int:
        return max(1, (self.end_date - self.start_date).days + 1)

    @property
    def granularity(self) -> str:
        if self.days <= 90:
            return "day"
        if self.days <= 400:
            return "week"
        return "month"

    def label(self) -> str:
        labels = dict(PRESETS)
        if self.preset == "custom":
            return f"{self.start_date:%d/%m/%Y} – {self.end_date:%d/%m/%Y}"
        return str(labels.get(self.preset, self.preset))


def _aware(d: date) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, time.min), tz)


def resolve_period(
    preset: str,
    date_from: date | None = None,
    date_to: date | None = None,
    *,
    now: datetime | None = None,
) -> PeriodWindow:
    now = now or timezone.localtime()
    today = now.date()
    preset = preset if preset in PRESET_KEYS else "today"

    if preset == "today":
        start, end = _aware(today), _aware(today + timedelta(days=1))
    elif preset == "yesterday":
        start, end = _aware(today - timedelta(days=1)), _aware(today)
    elif preset == "last_7":
        start, end = _aware(today - timedelta(days=6)), _aware(today + timedelta(days=1))
    elif preset == "last_30":
        start, end = _aware(today - timedelta(days=29)), _aware(today + timedelta(days=1))
    elif preset == "this_month":
        start, end = _aware(today.replace(day=1)), _aware(today + timedelta(days=1))
    elif preset == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start, end = _aware(last_prev.replace(day=1)), _aware(first_this)
    elif preset == "this_year":
        start, end = _aware(date(today.year, 1, 1)), _aware(today + timedelta(days=1))
    else:
        if not date_from or not date_to:
            start, end = _aware(today), _aware(today + timedelta(days=1))
            preset = "today"
        else:
            if date_to < date_from:
                date_from, date_to = date_to, date_from
            start, end = _aware(date_from), _aware(date_to + timedelta(days=1))

    duration = end - start
    return PeriodWindow(
        preset=preset,
        start=start,
        end=end,
        prev_start=start - duration,
        prev_end=start,
    )
