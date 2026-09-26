"""relative_time() and day_heading() at fixed instants, in the active timezone."""

from __future__ import annotations

from datetime import UTC, date, datetime

from django.utils import timezone as django_timezone

from freedom_ls.comms.relative_time import day_heading, relative_time

NOW = datetime(2025, 9, 21, 15, 30, tzinfo=UTC)


class TestRelativeTime:
    def test_under_a_minute_is_just_now(self) -> None:
        value = NOW - django_timezone.timedelta(seconds=30)

        assert relative_time(value, NOW) == "Just now"

    def test_under_an_hour_is_minutes_ago(self) -> None:
        value = NOW - django_timezone.timedelta(minutes=5)

        assert relative_time(value, NOW) == "5 min ago"

    def test_same_local_day_is_hours_ago(self) -> None:
        value = NOW - django_timezone.timedelta(hours=3)

        assert relative_time(value, NOW) == "3 hours ago"

    def test_yesterday_shows_the_time(self) -> None:
        value = datetime(2025, 9, 20, 16, 20, tzinfo=UTC)

        assert relative_time(value, NOW) == "Yesterday, 16:20"

    def test_earlier_this_year_omits_the_year(self) -> None:
        value = datetime(2025, 9, 10, 9, 0, tzinfo=UTC)

        assert relative_time(value, NOW) == "10 Sep"

    def test_last_year_includes_the_year(self) -> None:
        value = datetime(2024, 9, 21, 9, 0, tzinfo=UTC)

        assert relative_time(value, NOW) == "21 Sep 2024"

    def test_uses_the_active_timezone_not_utc(self) -> None:
        # In UTC these two instants straddle midnight, so a UTC-only
        # comparison would call this "Yesterday, 22:00". Africa/Johannesburg
        # (UTC+2) puts both on the same local day, so it reads as hours ago.
        now_utc = datetime(2025, 9, 21, 0, 30, tzinfo=UTC)
        value_utc = datetime(2025, 9, 20, 22, 0, tzinfo=UTC)

        assert relative_time(value_utc, now_utc) == "Yesterday, 22:00"
        with django_timezone.override("Africa/Johannesburg"):
            assert relative_time(value_utc, now_utc) == "2 hours ago"


class TestDayHeading:
    TODAY = date(2025, 9, 21)

    def test_today(self) -> None:
        assert day_heading(self.TODAY, self.TODAY) == "Today"

    def test_yesterday(self) -> None:
        assert day_heading(date(2025, 9, 20), self.TODAY) == "Yesterday"

    def test_earlier_this_year_names_the_weekday_and_omits_the_year(self) -> None:
        assert day_heading(date(2025, 9, 15), self.TODAY) == "Monday 15 September"

    def test_last_year_includes_the_year(self) -> None:
        assert (
            day_heading(date(2024, 9, 21), self.TODAY) == "Saturday 21 September 2024"
        )

    def test_the_year_boundary_includes_last_years_date(self) -> None:
        assert (
            day_heading(date(2024, 12, 20), date(2025, 1, 5))
            == "Friday 20 December 2024"
        )
