"""Tests for writing live attribution touches."""

from __future__ import annotations

from datetime import timedelta

import pytest
import time_machine

from django.db import DatabaseError
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.conversions import (
    record_conversion,
    record_live_touch,
)
from freedom_ls.referral_tracking.factories import (
    AttributionTouchFactory,
    ConversionFactory,
)
from freedom_ls.referral_tracking.models import (
    AttributionTouch,
    Conversion,
    ConversionKind,
    TouchSource,
)

rf = RequestFactory()


def _record(user, site, path: str = "/?ref=A", occurred_at=None):
    return record_live_touch(
        request=rf.get(path),
        user=user,
        site=site,
        occurred_at=occurred_at or timezone.now(),
    )


@pytest.mark.django_db
def test_a_coded_landing_writes_one_live_touch(mock_site_context, site) -> None:
    user = UserFactory()

    touch = _record(user, site, "/courses/?ref=A&utm_source=news")

    assert touch is not None
    assert touch.recorded_via == TouchSource.LIVE
    assert (touch.referral_code, touch.utm_source) == ("A", "news")
    assert touch.landing_path == "/courses/"
    assert AttributionTouch._base_manager.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_click_id_only_landing_writes_nothing(mock_site_context, site) -> None:
    user = UserFactory()

    touch = _record(user, site, "/?gclid=abc")

    assert touch is None
    assert not AttributionTouch._base_manager.exists()


@pytest.mark.django_db
def test_a_landing_with_the_latest_touchs_key_writes_nothing(
    mock_site_context, site
) -> None:
    user = UserFactory()
    AttributionTouchFactory(user=user, referral_code="A", utm_source="")

    touch = _record(user, site, "/?ref=A")

    assert touch is None
    assert AttributionTouch._base_manager.count() == 1


@pytest.mark.django_db
def test_a_landing_on_a_to_b_to_a_writes_a_third_row(mock_site_context, site) -> None:
    user = UserFactory()
    AttributionTouchFactory(
        user=user,
        referral_code="A",
        utm_source="",
        occurred_at=timezone.now() - timedelta(days=2),
    )
    AttributionTouchFactory(
        user=user,
        referral_code="B",
        utm_source="",
        occurred_at=timezone.now() - timedelta(days=1),
    )

    _record(user, site, "/?ref=A")

    assert AttributionTouch._base_manager.filter(user=user).count() == 3


@pytest.mark.django_db
def test_a_failed_write_returns_none_and_is_reported(
    mock_site_context, site, mocker
) -> None:
    user = UserFactory()
    mocker.patch.object(
        AttributionTouch._base_manager, "create", side_effect=DatabaseError("boom")
    )
    sentry = mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")

    touch = _record(user, site)

    assert touch is None
    sentry.capture_exception.assert_called_once()


def _convert(user, target, occurred_at=None, label="Intro to Rust"):
    return record_conversion(
        user=user,
        kind=ConversionKind.COURSE_INTEREST,
        target=target,
        occurred_at=occurred_at or timezone.now(),
        target_label=label,
    )


@pytest.mark.django_db
def test_record_conversion_freezes_the_touches_and_their_codes(
    mock_site_context,
) -> None:
    user = UserFactory()
    first = AttributionTouchFactory(
        user=user, referral_code="A", occurred_at=timezone.now() - timedelta(days=5)
    )
    last = AttributionTouchFactory(
        user=user, referral_code="B", occurred_at=timezone.now() - timedelta(days=1)
    )

    conversion = _convert(user, user)

    assert conversion is not None
    assert (conversion.first_touch, conversion.last_touch) == (first, last)
    assert (conversion.first_referral_code, conversion.last_referral_code) == (
        "A",
        "B",
    )


@pytest.mark.django_db
@time_machine.travel("2026-06-01T12:00:00Z", tick=False)
def test_record_conversion_freezes_the_window_label_and_instant(
    mock_site_context, settings
) -> None:
    settings.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS = 45
    user = UserFactory()
    occurred_at = timezone.now() - timedelta(hours=1)

    conversion = _convert(user, user, occurred_at=occurred_at, label="Intro to Rust")

    assert conversion is not None
    assert conversion.window_days == 45
    assert conversion.target_label == "Intro to Rust"
    assert conversion.occurred_at == occurred_at
    assert conversion.target == user
    assert conversion.site == user.site


@pytest.mark.django_db
def test_record_conversion_with_no_touches_records_blank_codes(
    mock_site_context,
) -> None:
    user = UserFactory()

    conversion = _convert(user, user)

    assert conversion is not None
    assert (conversion.first_referral_code, conversion.last_referral_code) == ("", "")
    assert (conversion.first_touch, conversion.last_touch) == (None, None)


@pytest.mark.django_db
def test_record_conversion_on_an_already_converted_target_writes_no_second_row(
    mock_site_context,
) -> None:
    user = UserFactory()
    ConversionFactory(user=user, kind=ConversionKind.COURSE_INTEREST, target=user)

    _convert(user, user)

    assert Conversion._base_manager.count() == 1


@pytest.mark.django_db
def test_a_failed_conversion_write_returns_none_and_is_reported(
    mock_site_context, mocker
) -> None:
    user = UserFactory()
    mocker.patch.object(
        Conversion._base_manager, "get_or_create", side_effect=DatabaseError("boom")
    )
    sentry = mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")

    conversion = _convert(user, user)

    assert conversion is None
    sentry.capture_exception.assert_called_once()
