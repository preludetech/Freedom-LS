"""Human-readable time for a notification: a relative time for a row, a day
heading for the group it sits under. Both take "now" (or "today") as an
argument rather than reading the clock themselves, so a caller can hold every
comparison to one instant and tests can pass a fixed one.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone


def relative_time(value: datetime, now: datetime) -> str:
    local_value = timezone.localtime(value)
    local_now = timezone.localtime(now)
    elapsed = local_now - local_value

    if elapsed < timedelta(minutes=1):
        return "Just now"
    if elapsed < timedelta(hours=1):
        minutes = int(elapsed.total_seconds() // 60)
        return f"{minutes} min ago"
    if local_value.date() == local_now.date():
        hours = int(elapsed.total_seconds() // 3600)
        return f"{hours} hours ago"
    if local_value.date() == local_now.date() - timedelta(days=1):
        return f"Yesterday, {local_value.strftime('%H:%M')}"
    if local_value.year == local_now.year:
        return _day_and_month(local_value)
    return f"{_day_and_month(local_value)} {local_value.year}"


def day_heading(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    if day.year == today.year:
        return f"{day.strftime('%A')} {day.day} {day.strftime('%B')}"
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B')} {day.year}"


def _day_and_month(value: datetime) -> str:
    return f"{value.day} {value.strftime('%b')}"
