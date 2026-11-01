from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from django import template
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging import can_see_messages_button
from freedom_ls.comms.relative_time import day_heading as _day_heading
from freedom_ls.comms.relative_time import relative_time as _relative_time
from freedom_ls.comms.views import _unseen_count
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from django.contrib.sites.models import Site

    from freedom_ls.accounts.models import User

register = template.Library()


@register.filter(name="relative_time")
def relative_time_filter(value: datetime) -> str:
    return _relative_time(value, timezone.now())


@register.filter(name="day_heading")
def day_heading_filter(value: datetime) -> str:
    return _day_heading(timezone.localtime(value).date(), timezone.localdate())


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


@register.inclusion_tag("comms/partials/messages_button.html", takes_context=True)
def messages_button(context: template.Context) -> dict[str, object]:
    """The header Messages button, for a user who can message someone or
    already has a conversation.

    The unread count is not computed here: the badge loads itself after the
    page renders, so no page pays for that query. A user with no conversation
    pays for the configured policy's recipients queries on every page render.
    """
    if not config.MESSAGING_ENABLED:
        return {"enabled": False}
    request = cast("HttpRequest", context["request"])
    site = cast("Site", get_cached_site(request))
    if not can_see_messages_button(cast("User", request.user), site):
        return {"enabled": False}
    return {"enabled": True, "poll_seconds": config.MESSAGE_INBOX_POLL_SECONDS}
