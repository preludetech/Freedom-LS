from __future__ import annotations

from datetime import datetime
from typing import cast

from django import template
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.comms.config import config
from freedom_ls.comms.relative_time import relative_time as _relative_time
from freedom_ls.comms.views import _unseen_count

register = template.Library()


@register.filter(name="relative_time")
def relative_time_filter(value: datetime) -> str:
    return _relative_time(value, timezone.now())


@register.filter
def badge_count(value: int) -> str:
    return "99+" if value > 99 else str(value)


@register.inclusion_tag("comms/partials/notification_bell.html", takes_context=True)
def notification_bell(context: template.Context) -> dict[str, object]:
    if not config.NOTIFICATIONS_ENABLED:
        return {"enabled": False}
    request = cast("HttpRequest", context["request"])
    return {
        "enabled": True,
        "unseen_count": _unseen_count(request),
        "poll_seconds": config.NOTIFICATION_BADGE_POLL_SECONDS,
    }
