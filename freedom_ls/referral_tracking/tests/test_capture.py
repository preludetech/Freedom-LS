"""Tests for query-parameter sanitisation and the signed attribution cookie."""

from __future__ import annotations

import datetime

import time_machine

from django.http import HttpResponse
from django.test import RequestFactory

from freedom_ls.referral_tracking.capture import (
    first_touch_from_request,
    read_attribution_cookie,
    sanitise,
    set_attribution_cookie,
)
from freedom_ls.referral_tracking.config import config

rf = RequestFactory()


def _cookie_from(response: HttpResponse) -> str:
    return response.cookies[config.REFERRAL_TRACKING_COOKIE_NAME].value


def test_null_byte_stripped_without_raising() -> None:
    assert sanitise("ab\x00cd", 10) == "abcd"


def test_control_characters_removed() -> None:
    assert sanitise("ab\x01\x1fcd\x7f", 10) == "abcd"


def test_utm_source_is_lowercased() -> None:
    request = rf.get("/?utm_source=Facebook")

    first_touch = first_touch_from_request(request)

    assert first_touch["utm_source"] == "facebook"


def test_utm_campaign_keeps_its_case() -> None:
    request = rf.get("/?utm_campaign=Spring Sale")

    first_touch = first_touch_from_request(request)

    assert first_touch["utm_campaign"] == "Spring Sale"


def test_over_length_value_truncated_to_its_cap() -> None:
    assert sanitise("a" * 100, 5) == "a" * 5


def test_duplicated_parameter_takes_the_last_value() -> None:
    request = rf.get("/?utm_source=a&utm_source=b")

    first_touch = first_touch_from_request(request)

    assert first_touch["utm_source"] == "b"


def test_percent_encoded_plus_is_stored_as_the_literal_character() -> None:
    request = rf.get("/?utm_campaign=a%2Bb")

    first_touch = first_touch_from_request(request)

    assert first_touch["utm_campaign"] == "a+b"


def test_first_seen_round_trips_through_the_cookie() -> None:
    request = rf.get("/?utm_source=x")
    first_touch = first_touch_from_request(request)
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)
    read_request = rf.get("/")
    read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)

    read_back = read_attribution_cookie(read_request)

    assert read_back is not None
    assert read_back["first_seen"] == first_touch["first_seen"]


def test_forged_cookie_value_reads_as_none() -> None:
    request = rf.get("/")
    request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = "forged:value"

    assert read_attribution_cookie(request) is None


def test_signed_but_garbage_payload_reads_as_none() -> None:
    response = HttpResponse()
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME,
        "not valid base64 json",
        salt="freedom_ls.referral_tracking",
    )
    request = rf.get("/")
    request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)

    assert read_attribution_cookie(request) is None


def test_cookie_older_than_the_window_reads_as_none() -> None:
    mint_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    with time_machine.travel(mint_time, tick=False):
        request = rf.get("/?utm_source=x")
        first_touch = first_touch_from_request(request)
        response = HttpResponse()
        set_attribution_cookie(response, first_touch)
        cookie_value = _cookie_from(response)

    past_the_window = mint_time + datetime.timedelta(
        days=config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS + 1
    )
    with time_machine.travel(past_the_window, tick=False):
        read_request = rf.get("/")
        read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = cookie_value

        assert read_attribution_cookie(read_request) is None
