from collections.abc import Callable
from functools import partial

from django.http import HttpRequest

from freedom_ls.base.google_analytics import (
    GoogleAnalyticsEventPayload,
    pop_google_analytics_events,
)
from freedom_ls.deployment.config import config as deployment_config

# allauth's own URL names (allauth/account/urls.py). Each carries a one-time
# token in the path, so caching or replaying the page must never be assumed
# safe the way an ordinary page's is.
TOKEN_BEARING_URL_NAMES = frozenset(
    {"account_confirm_email", "account_reset_password_from_key"}
)


def analytics_enabled(request: HttpRequest) -> dict[str, bool]:
    """The one place that decides whether any analytics snippet loads.

    A downstream deployment that needs consent gating adds its own context
    processor here in place of this one, returning `analytics_enabled` from
    whatever consent state it tracks.
    """
    match = request.resolver_match
    url_name = match.url_name if match is not None else None
    return {"analytics_enabled": url_name not in TOKEN_BEARING_URL_NAMES}


def posthog_config(_request: HttpRequest) -> dict[str, str | None]:
    """
    Context processor that provides PostHog configuration.

    Args:
        _request: The current HttpRequest (required by Django context processors)

    Returns:
        dict: posthog_api_key, posthog_api_host, and posthog_ui_host resolved
        through freedom_ls.deployment.config.
    """
    return {
        "posthog_api_key": deployment_config.POSTHOG_API_KEY,
        "posthog_api_host": deployment_config.POSTHOG_API_HOST,
        "posthog_ui_host": deployment_config.POSTHOG_UI_HOST,
    }


def google_analytics_config(
    request: HttpRequest,
) -> dict[str, str | None | Callable[[], list[GoogleAnalyticsEventPayload]]]:
    """
    Context processor that provides Google Analytics 4 configuration.

    `google_analytics_events` is a callable rather than a resolved list: Django
    calls it only when a template first reads the variable, so the events are
    popped from the session only by a template that goes on to emit them. A
    render that never reaches `partials/google_analytics_events.html` (most
    HTMX partials, an email, a token-bearing page) leaves the events for the
    next page to pop.

    Args:
        request: The current HttpRequest.

    Returns:
        dict: google_analytics_measurement_id resolved through
        freedom_ls.deployment.config, and google_analytics_events, a callable
        returning this request's pending one-shot GA4 events.
    """
    measurement_id = deployment_config.GOOGLE_ANALYTICS_MEASUREMENT_ID
    if measurement_id is None:
        # Nothing will ever emit these, so they are discarded now instead of
        # waiting in the session for a measurement ID that may arrive weeks
        # later, or never.
        pop_google_analytics_events(request)
    return {
        "google_analytics_measurement_id": measurement_id,
        "google_analytics_events": partial(pop_google_analytics_events, request),
    }
