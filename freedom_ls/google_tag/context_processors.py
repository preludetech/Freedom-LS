from django.http import HttpRequest

from freedom_ls.base.analytics_events import EU_CONSENT_POLICY_COUNTRIES
from freedom_ls.google_tag.config import config


def google_tag_config(
    _request: HttpRequest,
) -> dict[str, str | None | list[str]]:
    """
    Context processor that provides Google Analytics 4 and Google Ads configuration.

    Whether the tag loads at all is `analytics_enabled`, from
    `freedom_ls.deployment.context_processors`, which PostHog shares. The
    session's pending events are popped by
    `freedom_ls.base.context_processors.analytics_events`, shared by every
    platform app, not by this context processor.

    Args:
        _request: The current HttpRequest (required by Django context processors).

    Returns:
        dict: google_analytics_measurement_id and google_ads_conversion_id
        resolved through freedom_ls.google_tag.config, and
        consent_mode_denied_regions.
    """
    return {
        "google_analytics_measurement_id": config.GOOGLE_ANALYTICS_MEASUREMENT_ID,
        "google_ads_conversion_id": config.GOOGLE_ADS_CONVERSION_ID,
        "consent_mode_denied_regions": list(EU_CONSENT_POLICY_COUNTRIES),
    }
