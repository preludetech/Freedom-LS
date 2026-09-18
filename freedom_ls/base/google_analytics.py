"""One-shot session flags for GA4 events.

GA4's enhanced measurement covers page views on its own, but the four events
recorded here (`sign_up`, `generate_lead`, `tutorial_begin`, `tutorial_complete`
- GA4's own names) happen inside a view, not a page render. `tutorial_begin`
and `tutorial_complete` are GA4's vocabulary for "started a course" and
"finished a course"; the pair name has nothing to do with FLS's own use of
"tutorial" elsewhere.

A view records a flag the moment the underlying event happens; the next full
page render pops it and emits the matching `gtag('event', ...)` call. See
`freedom_ls/deployment/context_processors.py:google_analytics_config` and
`freedom_ls/base/templates/partials/google_analytics_events.html`.
"""

from enum import StrEnum
from typing import cast

from django.http import HttpRequest

GOOGLE_ANALYTICS_FLAGS_SESSION_KEY = "google_analytics_flags"


class GoogleAnalyticsEvent(StrEnum):
    SIGN_UP = "sign_up"
    GENERATE_LEAD = "generate_lead"
    TUTORIAL_BEGIN = "tutorial_begin"
    TUTORIAL_COMPLETE = "tutorial_complete"


def record_google_analytics_flag(
    request: HttpRequest, event: GoogleAnalyticsEvent
) -> None:
    """Record a one-shot flag; the next page render emits the GA4 event."""
    flags = request.session.get(GOOGLE_ANALYTICS_FLAGS_SESSION_KEY, [])
    if event.value not in flags:
        # A new list, not an in-place append, so the session middleware's
        # dirty check (identity/equality on the stored value) sees the change.
        request.session[GOOGLE_ANALYTICS_FLAGS_SESSION_KEY] = [*flags, event.value]


def pop_google_analytics_flags(request: HttpRequest) -> list[str]:
    # The context processor calls this for every template render, including
    # ones built from a bare request that never passed through
    # SessionMiddleware (a template unit test rendering _base.html directly).
    # Such a request carries no flags, so there is nothing to pop.
    session = getattr(request, "session", None)
    if session is None:
        return []
    return cast(list[str], session.pop(GOOGLE_ANALYTICS_FLAGS_SESSION_KEY, []))
