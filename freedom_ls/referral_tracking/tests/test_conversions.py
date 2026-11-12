"""Tests for writing live attribution touches."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.capture import (
    COOKIE_SALT,
    COOKIE_TOUCHES_KEY,
    is_cookie_clear_requested,
)
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.conversions import (
    flush_cookie_touches,
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
from freedom_ls.tests.site_context import drop_ambient_request

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


FIRST_LANDING = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
SECOND_LANDING = FIRST_LANDING + timedelta(days=2)
THIRD_LANDING = FIRST_LANDING + timedelta(days=4)
FLUSH_TIME = FIRST_LANDING + timedelta(days=10)


def _request_holding_cookie(entries: list[dict[str, str]]) -> HttpRequest:
    payload = {
        "ts": FIRST_LANDING.isoformat(),
        "rc": "A",
        "p": "/landing/",
        COOKIE_TOUCHES_KEY: entries,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    response = HttpResponse()
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME, encoded, salt=COOKIE_SALT
    )
    request = rf.get("/")
    request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = response.cookies[
        config.REFERRAL_TRACKING_COOKIE_NAME
    ].value
    return request


def _three_landings_request() -> HttpRequest:
    return _request_holding_cookie(
        [
            {"rc": "B", "ts": SECOND_LANDING.isoformat()},
            {"rc": "C", "ts": THIRD_LANDING.isoformat()},
        ]
    )


def _flush(request, user, source=TouchSource.SIGNUP_FLUSH):
    return flush_cookie_touches(request=request, user=user, source=source)


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_flush_writes_one_touch_per_landing_at_its_time(mock_site_context) -> None:
    user = UserFactory()

    _flush(_three_landings_request(), user)

    touches = AttributionTouch._base_manager.filter(user=user).order_by("occurred_at")
    assert [(t.referral_code, t.occurred_at) for t in touches] == [
        ("A", FIRST_LANDING),
        ("B", SECOND_LANDING),
        ("C", THIRD_LANDING),
    ]


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_flush_marks_the_touches_with_the_given_source(mock_site_context) -> None:
    user = UserFactory()

    _flush(_three_landings_request(), user, TouchSource.LOGIN_FLUSH)

    sources = AttributionTouch._base_manager.values_list("recorded_via", flat=True)
    assert set(sources) == {TouchSource.LOGIN_FLUSH}


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_the_first_touch_keeps_its_landing_path_and_list_entries_have_none(
    mock_site_context,
) -> None:
    user = UserFactory()

    _flush(_three_landings_request(), user)

    touches = AttributionTouch._base_manager.filter(user=user).order_by("occurred_at")
    assert [t.landing_path for t in touches] == ["/landing/", "", ""]


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_an_entry_dated_in_the_future_is_skipped(mock_site_context) -> None:
    user = UserFactory()
    future = (FLUSH_TIME + timedelta(days=1)).isoformat()

    _flush(_request_holding_cookie([{"rc": "B", "ts": future}]), user)

    assert AttributionTouch._base_manager.filter(user=user).count() == 1


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_an_entry_dated_before_the_first_landing_is_skipped(mock_site_context) -> None:
    user = UserFactory()
    earlier = (FIRST_LANDING - timedelta(days=1)).isoformat()

    _flush(_request_holding_cookie([{"rc": "B", "ts": earlier}]), user)

    assert AttributionTouch._base_manager.filter(user=user).count() == 1


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_flush_of_touches_already_written_writes_no_second_row(
    mock_site_context,
) -> None:
    user = UserFactory()
    for code, when in (
        ("A", FIRST_LANDING),
        ("B", SECOND_LANDING),
        ("C", THIRD_LANDING),
    ):
        AttributionTouchFactory(
            user=user, referral_code=code, utm_source="", occurred_at=when
        )

    _flush(_three_landings_request(), user)

    assert AttributionTouch._base_manager.filter(user=user).count() == 3


@pytest.mark.django_db
def test_a_flush_without_a_request_returns_an_empty_list(mock_site_context) -> None:
    flushed = flush_cookie_touches(
        request=None, user=UserFactory(), source=TouchSource.LOGIN_FLUSH
    )

    assert flushed == []


@pytest.mark.django_db
def test_a_flush_for_a_request_without_a_cookie_writes_nothing(
    mock_site_context,
) -> None:
    user = UserFactory()

    _flush(rf.get("/"), user)

    assert not AttributionTouch._base_manager.exists()


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_flush_writes_on_the_users_site_without_an_ambient_request(
    mock_site_context,
) -> None:
    user = UserFactory()
    request = _three_landings_request()
    drop_ambient_request()

    _flush(request, user)

    sites = AttributionTouch._base_manager.values_list("site", flat=True)
    assert set(sites) == {user.site_id}


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_flush_sets_the_clear_flag(mock_site_context) -> None:
    request = _three_landings_request()

    _flush(request, UserFactory())

    assert is_cookie_clear_requested(request)


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_failed_flush_returns_nothing(mock_site_context, mocker) -> None:
    mocker.patch.object(
        AttributionTouch._base_manager, "get_or_create", side_effect=DatabaseError("x")
    )
    mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")

    flushed = _flush(_three_landings_request(), UserFactory())

    assert flushed == []


@pytest.mark.django_db
@time_machine.travel(FLUSH_TIME, tick=False)
def test_a_failed_flush_still_sets_the_clear_flag(mock_site_context, mocker) -> None:
    mocker.patch.object(
        AttributionTouch._base_manager, "get_or_create", side_effect=DatabaseError("x")
    )
    mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")
    request = _three_landings_request()

    _flush(request, UserFactory())

    assert is_cookie_clear_requested(request)
