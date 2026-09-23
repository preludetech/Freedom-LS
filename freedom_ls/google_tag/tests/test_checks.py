from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.google_tag.checks import check_google_ads_rides_on_google_analytics


def test_google_ads_check_is_registered_via_app_ready() -> None:
    assert (
        check_google_ads_rides_on_google_analytics
        in registry.registry.registered_checks
    )


@override_settings(
    GOOGLE_ADS_CONVERSION_ID="AW-1",
    GOOGLE_ANALYTICS_MEASUREMENT_ID=None,
    GOOGLE_ADS_CONVERSION_LABELS={},
)
def test_ads_id_without_measurement_id_returns_w001() -> None:
    warnings = check_google_ads_rides_on_google_analytics(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_google_tag.W001"]


@override_settings(
    GOOGLE_ADS_CONVERSION_ID=None,
    GOOGLE_ANALYTICS_MEASUREMENT_ID="G-1",
    GOOGLE_ADS_CONVERSION_LABELS={"sign_up": "abc"},
)
def test_labels_without_ads_id_returns_w002() -> None:
    warnings = check_google_ads_rides_on_google_analytics(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_google_tag.W002"]


@override_settings(
    GOOGLE_ADS_CONVERSION_ID=None,
    GOOGLE_ANALYTICS_MEASUREMENT_ID=None,
    GOOGLE_ADS_CONVERSION_LABELS={"sign_up": "abc"},
)
def test_labels_alone_report_only_the_missing_ads_id() -> None:
    # W001 is about an Ads ID that cannot load; with no Ads ID there is nothing
    # for it to say, so only the labels are reported.
    warnings = check_google_ads_rides_on_google_analytics(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_google_tag.W002"]


@override_settings(
    GOOGLE_ADS_CONVERSION_ID="AW-1",
    GOOGLE_ANALYTICS_MEASUREMENT_ID="G-1",
    GOOGLE_ADS_CONVERSION_LABELS={"sign_up": "abc"},
)
def test_complete_google_ads_configuration_returns_no_warnings() -> None:
    warnings = check_google_ads_rides_on_google_analytics(None)

    assert warnings == []


@override_settings(
    GOOGLE_ADS_CONVERSION_ID=None,
    GOOGLE_ANALYTICS_MEASUREMENT_ID="G-1",
    GOOGLE_ADS_CONVERSION_LABELS={},
)
def test_no_google_ads_configuration_returns_no_warnings() -> None:
    warnings = check_google_ads_rides_on_google_analytics(None)

    assert warnings == []
