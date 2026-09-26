from collections.abc import Callable
from functools import partial

from django.http import HttpRequest

from freedom_ls.base.analytics_events import (
    EU_CONSENT_POLICY_COUNTRIES,
    AnalyticsEventPayload,
    pop_analytics_events,
)
from freedom_ls.google_tag.config import config
from freedom_ls.google_tag.google_ads import conversion_send_to


class PendingGoogleAnalyticsEvent(AnalyticsEventPayload):
    # The Google Ads conversion this event also reports, or None. Attached at
    # render time rather than stored with the event, so a label change in the
    # environment applies to events already waiting in a session.
    send_to: str | None


def _pop_pending_events(request: HttpRequest) -> list[PendingGoogleAnalyticsEvent]:
    conversion_id = config.GOOGLE_ADS_CONVERSION_ID
    labels = config.GOOGLE_ADS_CONVERSION_LABELS
    return [
        {
            "name": event["name"],
            "params": event["params"],
            "send_to": conversion_send_to(conversion_id, labels, event["name"]),
        }
        for event in pop_analytics_events(request)
    ]


def google_tag_config(
    request: HttpRequest,
) -> dict[
    str, str | None | list[str] | Callable[[], list[PendingGoogleAnalyticsEvent]]
]:
    """
    Context processor that provides Google Analytics 4 and Google Ads configuration.

    Whether the tag loads at all is `analytics_enabled`, from
    `freedom_ls.deployment.context_processors`, which PostHog shares.

    `google_analytics_events` is a callable rather than a resolved list: Django
    calls it only when a template first reads the variable, so the events are
    popped from the session only by a template that goes on to emit them. A
    render that never reaches `partials/google_analytics_events.html` (most
    HTMX partials, an email, a token-bearing page) leaves the events for the
    next page to pop.

    Args:
        request: The current HttpRequest.

    Returns:
        dict: google_analytics_measurement_id and google_ads_conversion_id
        resolved through freedom_ls.google_tag.config,
        consent_mode_denied_regions, and
        google_analytics_events, a callable returning this request's pending
        one-shot GA4 events, each with the Ads conversion it also reports.
    """
    measurement_id = config.GOOGLE_ANALYTICS_MEASUREMENT_ID
    if measurement_id is None:
        # Nothing will ever emit these, so they are discarded now instead of
        # waiting in the session for a measurement ID that may arrive weeks
        # later, or never.
        pop_analytics_events(request)
    return {
        "google_analytics_measurement_id": measurement_id,
        "google_ads_conversion_id": config.GOOGLE_ADS_CONVERSION_ID,
        "consent_mode_denied_regions": list(EU_CONSENT_POLICY_COUNTRIES),
        "google_analytics_events": partial(_pop_pending_events, request),
    }
