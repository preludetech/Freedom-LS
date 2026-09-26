from __future__ import annotations

from datetime import datetime

from django import template
from django.utils import timezone

from freedom_ls.comms.relative_time import relative_time as _relative_time

register = template.Library()


@register.filter(name="relative_time")
def relative_time_filter(value: datetime) -> str:
    return _relative_time(value, timezone.now())
