"""Tests for the referral_tracking app's system checks."""

from __future__ import annotations

import pytest

from freedom_ls.referral_tracking.checks import check_inactive_destination


@pytest.mark.parametrize("bad_value", ["//x", "https://x"])
def test_e001_fires_for_a_value_that_is_not_a_site_path(settings, bad_value) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = bad_value

    errors = check_inactive_destination()

    assert [error.id for error in errors] == ["freedom_ls_referral_tracking.E001"]


def test_e001_is_silent_for_the_default(settings) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = None

    assert check_inactive_destination() == []
