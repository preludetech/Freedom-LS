"""Tests for query-parameter sanitisation and the signed attribution cookie."""

from __future__ import annotations

import base64
import datetime
import json

import time_machine

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.referral_tracking import capture
from freedom_ls.referral_tracking.capture import (
    COOKIE_SALT,
    TRACKED_PARAMS,
    first_touch_from_request,
    is_capture_suppressed,
    read_attribution_cookie,
    sanitise,
    set_attribution_cookie,
    suppress_capture,
)
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import CAPS

rf = RequestFactory()


def _cap_for(name: str) -> int:
    """`CAPS` is keyed by field name; `ref` is the one tracked parameter whose
    field name differs from the parameter it fills."""
    return CAPS["referral_code"] if name == "ref" else CAPS[name]


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


def _landing_with_every_value_at_its_cap(char: str) -> HttpRequest:
    """A tracked landing whose every captured value fills its cap with `char`."""
    params = {name: char * _cap_for(name) for name in TRACKED_PARAMS}
    return rf.get("/", params, HTTP_REFERER=char * CAPS["referer"])


def test_a_multibyte_worst_case_landing_keeps_its_campaign_in_the_cookie() -> None:
    first_touch = first_touch_from_request(_landing_with_every_value_at_its_cap("漢"))
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)
    read_request = rf.get("/")
    read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)
    read_back = read_attribution_cookie(read_request)

    assert read_back is not None
    assert read_back["utm_campaign"] == "漢" * CAPS["utm_campaign"]


def test_a_multibyte_worst_case_landing_drops_raw_query_rather_than_overflowing() -> (
    None
):
    first_touch = first_touch_from_request(_landing_with_every_value_at_its_cap("漢"))
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)
    read_request = rf.get("/")
    read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)
    read_back = read_attribution_cookie(read_request)

    assert read_back is not None
    assert read_back["raw_query"] == ""


def test_a_multibyte_worst_case_cookie_fits_the_browser_limit() -> None:
    first_touch = first_touch_from_request(_landing_with_every_value_at_its_cap("漢"))
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)

    name_and_value = f"{config.REFERRAL_TRACKING_COOKIE_NAME}={_cookie_from(response)}"
    assert len(name_and_value) <= 4096


def test_an_ascii_worst_case_landing_keeps_raw_query_in_the_cookie() -> None:
    first_touch = first_touch_from_request(_landing_with_every_value_at_its_cap("a"))
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)
    read_request = rf.get("/")
    read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)
    read_back = read_attribution_cookie(read_request)

    assert read_back is not None
    assert read_back["raw_query"] == first_touch["raw_query"]


def test_a_payload_that_cannot_fit_sets_no_cookie(monkeypatch) -> None:
    monkeypatch.setattr(capture, "COOKIE_MAX_ENCODED_LENGTH", 10)
    first_touch = first_touch_from_request(rf.get("/?utm_source=x"))
    response = HttpResponse()

    was_set = set_attribution_cookie(response, first_touch)

    assert was_set is False
    assert config.REFERRAL_TRACKING_COOKIE_NAME not in response.cookies


def test_a_multibyte_campaign_with_real_click_ids_keeps_them_in_the_cookie() -> None:
    params = {
        name: "漢" * CAPS[name] for name in ("utm_campaign", "utm_content", "utm_term")
    }
    params |= {
        name: "a" * _cap_for(name) for name in TRACKED_PARAMS if name not in params
    }
    request = rf.get(
        "/" + "p" * (CAPS["landing_path"] - 1),
        params,
        HTTP_REFERER="r" * CAPS["referer"],
    )
    first_touch = first_touch_from_request(request)
    response = HttpResponse()

    set_attribution_cookie(response, first_touch)
    read_request = rf.get("/")
    read_request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)
    read_back = read_attribution_cookie(read_request)

    assert read_back is not None
    assert read_back["gclid"] == "a" * CAPS["gclid"]


def test_ref_lands_in_referral_code() -> None:
    request = rf.get("/?ref=mrbeast")

    first_touch = first_touch_from_request(request)

    assert first_touch["referral_code"] == "mrbeast"


def test_ref_keeps_its_case() -> None:
    request = rf.get("/?ref=MrBeast")

    first_touch = first_touch_from_request(request)

    assert first_touch["referral_code"] == "MrBeast"


def test_ref_over_length_value_is_truncated_to_the_referral_code_cap() -> None:
    request = rf.get("/?ref=" + "a" * 100)

    first_touch = first_touch_from_request(request)

    assert first_touch["referral_code"] == "a" * CAPS["referral_code"]


def test_ref_requires_no_database_access() -> None:
    """A hand-typed `ref` is stored as free text: capture never looks it up
    against `ReferralCode`."""
    request = rf.get("/?ref=mrbeast")

    first_touch_from_request(request)


def test_a_pre_upgrade_cookie_without_rc_reads_with_a_blank_referral_code() -> None:
    payload = {"s": "x", "ts": timezone.now().isoformat()}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode(
        "ascii"
    )
    response = HttpResponse()
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME, encoded, salt=COOKIE_SALT
    )
    request = rf.get("/")
    request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)

    read_back = read_attribution_cookie(request)

    assert read_back is not None
    assert read_back["referral_code"] == ""


def test_suppress_capture_marks_the_request() -> None:
    request = rf.get("/")

    assert is_capture_suppressed(request) is False
    suppress_capture(request)
    assert is_capture_suppressed(request) is True
