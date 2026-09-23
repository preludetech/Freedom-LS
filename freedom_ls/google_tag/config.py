from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class GoogleTagSettings(AppSettings):
    GOOGLE_ANALYTICS_MEASUREMENT_ID: str | None
    GOOGLE_ADS_CONVERSION_ID: str | None
    GOOGLE_ADS_CONVERSION_LABELS: dict[str, str]

    declared_settings = {
        # Google Analytics 4: the client-side snippet (context processor +
        # partials/google_analytics.html) reads this. Unset means nothing loads.
        "GOOGLE_ANALYTICS_MEASUREMENT_ID": Setting(default=None),
        # Google Ads: rides on the GA4 loader, so it needs the measurement ID
        # too. Labels map an event name to the conversion action it reports;
        # an event with no label sends no conversion.
        "GOOGLE_ADS_CONVERSION_ID": Setting(default=None),
        "GOOGLE_ADS_CONVERSION_LABELS": Setting(default={}),
    }


config = GoogleTagSettings()
