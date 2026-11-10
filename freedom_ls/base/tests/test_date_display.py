from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

from freedom_ls.base.date_display import display_date, display_datetime, display_time

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")


def test_a_date_reads_day_short_month_year() -> None:
    assert display_date(date(2026, 11, 3)) == "3 Nov 2026"


def test_a_datetime_reads_date_then_24_hour_time() -> None:
    instant = datetime(2026, 11, 3, 7, 37, tzinfo=JOHANNESBURG)

    with timezone.override(JOHANNESBURG):
        assert display_datetime(instant) == "3 Nov 2026, 07:37"


def test_a_datetime_is_shown_in_the_current_time_zone() -> None:
    instant = datetime(2026, 11, 3, 23, 30, tzinfo=ZoneInfo("UTC"))

    with timezone.override(JOHANNESBURG):
        assert display_date(instant) == "4 Nov 2026"
        assert display_time(instant) == "01:30"
