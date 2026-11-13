"""The one way FLS writes a date and a time for a person to read: "3 Nov 2026" and
"3 Nov 2026, 07:37", on a 24-hour clock. Templates reach these through <c-date> and
<c-datetime>; Python formats through the functions below."""

from datetime import date, datetime

from django.utils import formats, timezone

DATE_DISPLAY_FORMAT = "j M Y"
SHORT_DATE_DISPLAY_FORMAT = "j M"
TIME_DISPLAY_FORMAT = "H:i"
DATETIME_DISPLAY_FORMAT = f"{DATE_DISPLAY_FORMAT}, {TIME_DISPLAY_FORMAT}"


def _in_current_zone(value: datetime) -> datetime:
    return timezone.localtime(value) if timezone.is_aware(value) else value


def display_date(value: date) -> str:
    """A date, or a datetime's date in the current time zone."""
    if isinstance(value, datetime):
        value = _in_current_zone(value)
    return formats.date_format(value, DATE_DISPLAY_FORMAT)


def display_short_date(value: date) -> str:
    """A date as a day and month, "3 Nov", keeping the year when it is not this year."""
    if value.year == timezone.localdate().year:
        return formats.date_format(value, SHORT_DATE_DISPLAY_FORMAT)
    return formats.date_format(value, DATE_DISPLAY_FORMAT)


def display_time(value: datetime) -> str:
    return formats.time_format(_in_current_zone(value), TIME_DISPLAY_FORMAT)


def display_datetime(value: datetime) -> str:
    return formats.date_format(_in_current_zone(value), DATETIME_DISPLAY_FORMAT)
