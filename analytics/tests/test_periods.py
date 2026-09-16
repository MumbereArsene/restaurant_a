from datetime import date, datetime

from django.test import SimpleTestCase
from django.utils import timezone

from analytics.periods import resolve_period


class PeriodTests(SimpleTestCase):
    def test_today_previous_is_yesterday(self):
        now = timezone.make_aware(datetime(2026, 8, 30, 15, 0))
        window = resolve_period("today", now=now)
        self.assertEqual(window.start_date, date(2026, 8, 30))
        self.assertEqual(window.end_date, date(2026, 8, 30))
        self.assertEqual((window.prev_end - window.prev_start), window.end - window.start)

    def test_last_7_covers_seven_days(self):
        now = timezone.make_aware(datetime(2026, 8, 30, 10, 0))
        window = resolve_period("last_7", now=now)
        self.assertEqual(window.days, 7)
        self.assertEqual(window.start_date, date(2026, 8, 24))
        self.assertEqual(window.end_date, date(2026, 8, 30))

    def test_custom_swaps_inverted_dates(self):
        window = resolve_period("custom", date(2026, 8, 20), date(2026, 8, 10))
        self.assertEqual(window.start_date, date(2026, 8, 10))
        self.assertEqual(window.end_date, date(2026, 8, 20))
        self.assertEqual(window.days, 11)

    def test_last_month_is_calendar_month(self):
        now = timezone.make_aware(datetime(2026, 8, 30, 8, 0))
        window = resolve_period("last_month", now=now)
        self.assertEqual(window.start_date, date(2026, 7, 1))
        self.assertEqual(window.end_date, date(2026, 7, 31))

    def test_granularity_day_then_week(self):
        now = timezone.make_aware(datetime(2026, 8, 30, 8, 0))
        self.assertEqual(resolve_period("last_30", now=now).granularity, "day")
        year = resolve_period("this_year", now=now)
        self.assertIn(year.granularity, ("week", "month"))
        self.assertGreaterEqual(year.days, 200)
