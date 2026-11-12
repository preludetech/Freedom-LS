"""Tests for writing live attribution touches."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.db import DatabaseError
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.conversions import record_live_touch
from freedom_ls.referral_tracking.factories import AttributionTouchFactory
from freedom_ls.referral_tracking.models import AttributionTouch, TouchSource

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
