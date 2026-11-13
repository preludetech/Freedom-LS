"""Tests for the referral_tracking app's system checks."""

from __future__ import annotations

import pytest

from freedom_ls.referral_tracking.checks import (
    check_attribution_window,
    check_inactive_destination,
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
