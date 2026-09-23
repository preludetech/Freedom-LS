"""Tests for the google_tag app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.google_tag.config import config


class TestGoogleAnalyticsDefaults:
    def test_measurement_id_defaults_to_none(self) -> None:
        assert config.GOOGLE_ANALYTICS_MEASUREMENT_ID is None


class TestGoogleAdsDefaults:
    def test_conversion_id_defaults_to_none(self) -> None:
        assert config.GOOGLE_ADS_CONVERSION_ID is None

    def test_conversion_labels_default_to_empty(self) -> None:
        assert config.GOOGLE_ADS_CONVERSION_LABELS == {}
