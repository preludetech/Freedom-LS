"""One-shot session events for GA4.

GA4's enhanced measurement covers page views on its own, but the events
recorded here happen inside a view, not a page render. A view records an event
the moment the underlying thing happens; the next render that reaches
`freedom_ls/base/templates/partials/google_analytics_events.html` pops it and
emits the matching `gtag('event', ...)` call. See
`freedom_ls/deployment/context_processors.py:google_analytics_config`.

Event names describe funnel moments every course access backend shares.
Whatever varies by backend travels as a parameter value, so a new backend adds
a value and leaves the event names, and any GA funnel built on them, alone.

This module is also the entry point for concrete projects. A downstream view
records its own events here, e.g. `generate_lead` from a marketing contact
form, with `lead_form` naming the form. Never pass anything a visitor typed.
"""

import re
from enum import StrEnum
from typing import TypedDict, cast

from django.http import HttpRequest

GOOGLE_ANALYTICS_EVENTS_SESSION_KEY = "google_analytics_events"

# Google's limits. A name outside them is dropped by GA without an error
# anywhere, so it is refused here, where the developer will see it.
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
_RESERVED_PREFIXES = ("ga_", "google_", "firebase_")
_RESERVED_PARAMETER_NAMES = frozenset(
    {"user_id", "session_id", "currency", "uid", "cid", "customer_id"}
)
_MAX_VALUE_LENGTH = 100


class GoogleAnalyticsEvent(StrEnum):
    SIGN_UP = "sign_up"
    COURSE_ACCESS_REQUESTED = "course_access_requested"
    COURSE_REGISTERED = "course_registered"
    COURSE_STARTED = "course_started"
    COURSE_COMPLETED = "course_completed"
    # FLS ships no lead form; the name is here for concrete projects to use.
    GENERATE_LEAD = "generate_lead"


class GoogleAnalyticsEventPayload(TypedDict):
    name: str
    params: dict[str, str]


def _is_valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.match(name)) and not name.startswith(_RESERVED_PREFIXES)


def record_google_analytics_event(
    request: HttpRequest, name: str, params: dict[str, str] | None = None
) -> None:
    """Record a one-shot event; the next page render emits it to GA4.

    `name` is a plain `str` so a concrete project can record events FLS has
    never heard of. Raises ValueError for an event or parameter name GA4 would
    reject. Values longer than GA4 accepts are cut to fit.
    """
    if not _is_valid_name(name):
        raise ValueError(f"Invalid GA4 event name: {name!r}")
    params = params or {}
    for param_name in params:
        if not _is_valid_name(param_name) or param_name in _RESERVED_PARAMETER_NAMES:
            raise ValueError(f"Invalid GA4 parameter name: {param_name!r}")

    event: GoogleAnalyticsEventPayload = {
        "name": str(name),
        "params": {key: value[:_MAX_VALUE_LENGTH] for key, value in params.items()},
    }
    events = request.session.get(GOOGLE_ANALYTICS_EVENTS_SESSION_KEY, [])
    # The whole payload is compared, so the same event for two courses in one
    # session reports both.
    if event not in events:
        # A new list, not an in-place append, so the session middleware's
        # dirty check (identity/equality on the stored value) sees the change.
        request.session[GOOGLE_ANALYTICS_EVENTS_SESSION_KEY] = [*events, event]


def record_sign_up(request: HttpRequest, method: str = "email") -> None:
    # Social login would send its provider name as the method instead.
    record_google_analytics_event(
        request, GoogleAnalyticsEvent.SIGN_UP, {"method": method}
    )


def pop_google_analytics_events(
    request: HttpRequest,
) -> list[GoogleAnalyticsEventPayload]:
    # The context processor calls this for every template render, including
    # ones built from a bare request that never passed through
    # SessionMiddleware (a template unit test rendering _base.html directly).
    # Such a request carries no events, so there is nothing to pop.
    session = getattr(request, "session", None)
    if session is None:
        return []
    return cast(
        list[GoogleAnalyticsEventPayload],
        session.pop(GOOGLE_ANALYTICS_EVENTS_SESSION_KEY, []),
    )
