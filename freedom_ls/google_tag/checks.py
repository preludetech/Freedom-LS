"""Django system checks for the google_tag app.

Check IDs follow Django's convention: ``app_label.severity + number``.
W = Warning. Neither check breaks the running app; the operator just gets no
Ads data and nothing says why. Both are silenceable via SILENCED_SYSTEM_CHECKS.

W001 — GOOGLE_ADS_CONVERSION_ID is set but GOOGLE_ANALYTICS_MEASUREMENT_ID is
       not. The Ads tag rides on the GA4 loader, so it would never load.
W002 — GOOGLE_ADS_CONVERSION_LABELS is set but GOOGLE_ADS_CONVERSION_ID is
       not, so no conversion would ever be sent.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import Warning, register


@register()
def check_google_ads_rides_on_google_analytics(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Warning]:
    from freedom_ls.google_tag.config import config

    warnings: list[Warning] = []
    if config.GOOGLE_ADS_CONVERSION_ID and not config.GOOGLE_ANALYTICS_MEASUREMENT_ID:
        warnings.append(
            Warning(
                "GOOGLE_ADS_CONVERSION_ID is set but GOOGLE_ANALYTICS_MEASUREMENT_ID "
                "is not. The Google Ads tag loads through the GA4 tag, so it will "
                "never load.",
                hint=(
                    "Set GOOGLE_ANALYTICS_MEASUREMENT_ID as well, or unset "
                    "GOOGLE_ADS_CONVERSION_ID."
                ),
                id="freedom_ls_google_tag.W001",
            )
        )
    if config.GOOGLE_ADS_CONVERSION_LABELS and not config.GOOGLE_ADS_CONVERSION_ID:
        warnings.append(
            Warning(
                "GOOGLE_ADS_CONVERSION_LABELS is set but GOOGLE_ADS_CONVERSION_ID is "
                "not, so no Google Ads conversion will ever be sent.",
                hint=(
                    "Set GOOGLE_ADS_CONVERSION_ID to the AW- ID from the Google Ads "
                    "account the labels belong to, or unset the labels."
                ),
                id="freedom_ls_google_tag.W002",
            )
        )
    return warnings
