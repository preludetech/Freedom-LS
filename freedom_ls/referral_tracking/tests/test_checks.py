"""Tests for the referral_tracking app's system checks."""

from __future__ import annotations

import pytest

from freedom_ls.referral_tracking.checks import (
    check_attribution_window,
    check_inactive_destination,
    check_touch_retention,
)


@pytest.mark.parametrize("bad_value", ["//x", "https://x"])
def test_e001_fires_for_a_value_that_is_not_a_site_path(settings, bad_value) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = bad_value

    errors = check_inactive_destination()

    assert [error.id for error in errors] == ["freedom_ls_referral_tracking.E001"]


def test_e001_is_silent_for_the_default(settings) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = None

    assert check_inactive_destination() == []


def test_w001_fires_when_the_window_is_shorter_than_the_cookies_life(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS = 90
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 30

    warnings = check_attribution_window()

    assert [warning.id for warning in warnings] == ["freedom_ls_referral_tracking.W001"]


def test_w001_is_silent_when_the_window_equals_the_cookies_life(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS = 90
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 90

    assert check_attribution_window() == []


def test_e002_fires_when_the_window_does_not_fit_window_days(settings) -> None:
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 32768

    errors = check_attribution_window()

    assert [error.id for error in errors] == ["freedom_ls_referral_tracking.E002"]


def test_e002_is_silent_at_the_largest_window_that_fits(settings) -> None:
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 32767

    assert check_attribution_window() == []


def test_e003_fires_when_retention_is_shorter_than_the_window(settings) -> None:
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 90
    settings.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS = 89

    errors = check_touch_retention()

    assert [error.id for error in errors] == ["freedom_ls_referral_tracking.E003"]


def test_e003_is_silent_when_retention_equals_the_window(settings) -> None:
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 90
    settings.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS = 90

    assert check_touch_retention() == []
