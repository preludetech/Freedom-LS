"""Tests for the referral_tracking app's declared settings."""

from __future__ import annotations

from freedom_ls.referral_tracking.config import config


def test_cookie_name_defaults_when_project_sets_nothing(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_NAME = None

    assert config.REFERRAL_TRACKING_COOKIE_NAME == "fls_attribution"


def test_cookie_name_reads_the_projects_value(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_NAME = "my_attribution"

    assert config.REFERRAL_TRACKING_COOKIE_NAME == "my_attribution"


def test_cookie_max_age_days_defaults_when_project_sets_nothing(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS = None

    assert config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS == 90


def test_cookie_max_age_days_reads_the_projects_value(settings) -> None:
    settings.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS = 30

    assert config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS == 30


def test_first_touch_key_cap_defaults_when_project_sets_nothing(settings) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = None

    assert config.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP == 1000


def test_first_touch_key_cap_reads_the_projects_value(settings) -> None:
    settings.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP = 50

    assert config.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP == 50


def test_inactive_destination_defaults_when_project_sets_nothing(settings) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = None

    assert config.REFERRAL_TRACKING_INACTIVE_DESTINATION == "/"


def test_inactive_destination_reads_the_projects_value(settings) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = "/courses/"

    assert config.REFERRAL_TRACKING_INACTIVE_DESTINATION == "/courses/"
