"""Tests for query-parameter sanitisation and the signed attribution cookie."""

from __future__ import annotations

import base64
import datetime
import json

import pytest
import time_machine

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from freedom_ls.referral_tracking import capture
from freedom_ls.referral_tracking.capture import (
    COOKIE_KEYS,
    COOKIE_SALT,
    COOKIE_TOUCHES_KEY,
    TRACKED_PARAMS,
    CookieTouch,
    append_touch,
    first_touch_from_request,
    flushable_cookie_touches,
    is_capture_suppressed,
    is_cookie_clear_requested,
    read_attribution_cookie,
    read_cookie_touches,
    request_cookie_clear,
    sanitise,
    set_attribution_cookie,
    suppress_capture,
)
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import ATTRIBUTION_KEY_FIELDS, CAPS

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


NOW = datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.UTC)
SEVEN_BLANK = dict.fromkeys(ATTRIBUTION_KEY_FIELDS, "")


def _request_holding(response: HttpResponse) -> HttpRequest:
    request = rf.get("/")
    request.COOKIES[config.REFERRAL_TRACKING_COOKIE_NAME] = _cookie_from(response)
    return request


def _request_holding_payload(payload: dict[str, object]) -> HttpRequest:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    response = HttpResponse()
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME, encoded, salt=COOKIE_SALT
    )
    return _request_holding(response)


def _touch(occurred_at: datetime.datetime = NOW, **fields: str) -> CookieTouch:
    return CookieTouch(**{**SEVEN_BLANK, **fields}, occurred_at=occurred_at)


def _first_touch(**fields: str) -> dict[str, str]:
    first_touch = first_touch_from_request(rf.get("/"))
    first_touch.update(fields)
    return first_touch


def _worst_case_touch(char: str) -> CookieTouch:
    return _touch(**{name: char * CAPS[name] for name in ATTRIBUTION_KEY_FIELDS})


def _max_age_of(response: HttpResponse) -> int:
    return int(response.cookies[config.REFERRAL_TRACKING_COOKIE_NAME]["max-age"])


def test_a_cookie_with_a_touch_list_still_reads_exactly_the_first_touch_keys() -> None:
    response = HttpResponse()
    set_attribution_cookie(
        response, _first_touch(utm_source="x"), touches=[_touch(utm_source="y")]
    )

    read_back = read_attribution_cookie(_request_holding(response))

    assert read_back is not None
    assert set(read_back) == set(COOKIE_KEYS)


def test_a_cookie_without_a_touch_list_reads_no_touches() -> None:
    response = HttpResponse()
    set_attribution_cookie(response, _first_touch(utm_source="x"))

    assert read_cookie_touches(_request_holding(response)) == []


def test_a_cookie_with_a_touch_list_reads_its_touches_in_order() -> None:
    response = HttpResponse()
    touches = [_touch(utm_source="a"), _touch(utm_source="b")]
    set_attribution_cookie(response, _first_touch(), touches=touches)

    read_back = read_cookie_touches(_request_holding(response))

    assert [touch.utm_source for touch in read_back] == ["a", "b"]


def test_a_list_entry_reads_back_with_its_landing_time() -> None:
    response = HttpResponse()
    set_attribution_cookie(
        response, _first_touch(), touches=[_touch(NOW, utm_source="a")]
    )

    read_back = read_cookie_touches(_request_holding(response))

    assert read_back[0].occurred_at == NOW


def test_a_list_entry_never_carries_a_landing_path() -> None:
    response = HttpResponse()
    set_attribution_cookie(
        response, _first_touch(), touches=[_touch(utm_source="a", landing_path="/x/")]
    )

    read_back = read_cookie_touches(_request_holding(response))

    assert read_back[0].landing_path == ""


def test_reading_the_list_twice_gives_the_same_touches() -> None:
    response = HttpResponse()
    set_attribution_cookie(response, _first_touch(), touches=[_touch(utm_source="a")])
    request = _request_holding(response)
    first_read = read_cookie_touches(request)

    assert read_cookie_touches(request) == first_read


def test_a_caller_that_mutates_the_first_touch_does_not_change_the_next_read() -> None:
    response = HttpResponse()
    set_attribution_cookie(response, _first_touch(utm_source="x"))
    request = _request_holding(response)
    first_read = read_attribution_cookie(request)
    assert first_read is not None
    first_read.pop("first_seen")

    second_read = read_attribution_cookie(request)

    assert second_read is not None
    assert "first_seen" in second_read


def _valid_entry() -> dict[str, object]:
    return {"s": "x", "ts": NOW.isoformat()}


@pytest.mark.parametrize(
    "touch_list",
    [
        "not a list",
        [["not", "a", "dict"]],
        [{**_valid_entry(), "zz": "unknown key"}],
        [{**_valid_entry(), "s": 5}],
        [{"s": "x", "ts": "not a time"}],
        [{"s": "x", "ts": "2026-03-01T12:00:00"}],
        [{"s": "x"}],
    ],
    ids=[
        "not-a-list",
        "entry-not-a-dict",
        "unknown-key",
        "non-str-value",
        "bad-ts",
        "naive-ts",
        "missing-ts",
    ],
)
def test_a_malformed_touch_list_reads_as_an_absent_cookie(touch_list: object) -> None:
    request = _request_holding_payload(
        {"s": "x", "ts": NOW.isoformat(), COOKIE_TOUCHES_KEY: touch_list}
    )

    with time_machine.travel(NOW, tick=False):
        assert read_attribution_cookie(request) is None


def test_a_first_touch_with_a_naive_landing_time_reads_as_absent() -> None:
    request = _request_holding_payload({"s": "x", "ts": "2026-03-01T12:00:00"})

    assert read_attribution_cookie(request) is None


def test_the_mint_response_carries_the_full_cookie_max_age() -> None:
    response = HttpResponse()

    set_attribution_cookie(response, first_touch_from_request(rf.get("/?utm_source=x")))

    assert _max_age_of(response) == capture._cookie_max_age()


def test_max_age_shrinks_with_the_age_of_the_first_touch() -> None:
    first_seen = NOW - datetime.timedelta(days=10)
    response = HttpResponse()

    with time_machine.travel(NOW, tick=False):
        set_attribution_cookie(
            response, _first_touch(first_seen=first_seen.isoformat())
        )

    assert _max_age_of(response) == capture._cookie_max_age() - 10 * 86400


def test_a_cookie_re_set_at_exactly_the_limit_gets_a_max_age_of_zero() -> None:
    first_seen = NOW - datetime.timedelta(
        days=config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS
    )
    response = HttpResponse()

    with time_machine.travel(NOW, tick=False):
        set_attribution_cookie(
            response, _first_touch(first_seen=first_seen.isoformat())
        )

    assert _max_age_of(response) == 0


def test_a_cookie_at_exactly_the_limit_still_reads() -> None:
    first_seen = NOW - datetime.timedelta(
        days=config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS
    )
    response = HttpResponse()

    with time_machine.travel(NOW, tick=False):
        set_attribution_cookie(
            response, _first_touch(first_seen=first_seen.isoformat())
        )
        assert read_attribution_cookie(_request_holding(response)) is not None


def test_a_re_signed_cookie_whose_first_touch_is_over_the_limit_reads_as_absent() -> (
    None
):
    first_seen = NOW - datetime.timedelta(
        days=config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS, seconds=1
    )
    response = HttpResponse()

    with time_machine.travel(NOW, tick=False):
        set_attribution_cookie(
            response, _first_touch(first_seen=first_seen.isoformat())
        )
        assert read_attribution_cookie(_request_holding(response)) is None


def test_append_touch_skips_a_landing_with_every_key_blank() -> None:
    request = rf.get("/", {"gclid": "abc"})

    assert append_touch([], _first_touch(utm_source="x"), request) is None


def test_append_touch_skips_a_repeat_of_the_first_touch_when_the_list_is_empty() -> (
    None
):
    request = rf.get("/", {"utm_source": "x"})

    assert append_touch([], _first_touch(utm_source="x"), request) is None


def test_append_touch_skips_a_repeat_of_the_last_entry() -> None:
    request = rf.get("/", {"utm_source": "b"})
    touches = [_touch(utm_source="a"), _touch(utm_source="b")]

    assert append_touch(touches, _first_touch(utm_source="x"), request) is None


def test_append_touch_appends_a_landing_that_differs_from_the_last_entry() -> None:
    request = rf.get("/", {"utm_source": "b"})

    result = append_touch(
        [_touch(utm_source="a")], _first_touch(utm_source="x"), request
    )

    assert result is not None
    assert [touch.utm_source for touch in result] == ["a", "b"]


def test_append_touch_appends_a_return_to_an_earlier_key() -> None:
    request = rf.get("/", {"utm_source": "a"})
    touches = [_touch(utm_source="a"), _touch(utm_source="b")]

    result = append_touch(touches, _first_touch(utm_source="x"), request)

    assert result is not None
    assert [touch.utm_source for touch in result] == ["a", "b", "a"]


def test_append_touch_returns_a_new_list() -> None:
    request = rf.get("/", {"utm_source": "b"})
    touches = [_touch(utm_source="a")]

    append_touch(touches, _first_touch(utm_source="x"), request)

    assert len(touches) == 1


@override_settings(REFERRAL_TRACKING_MAX_COOKIE_TOUCHES=2)
def test_append_touch_evicts_the_oldest_entry_at_the_cap() -> None:
    request = rf.get("/", {"utm_source": "c"})
    touches = [_touch(utm_source="a"), _touch(utm_source="b")]

    result = append_touch(touches, _first_touch(utm_source="x"), request)

    assert result is not None
    assert [touch.utm_source for touch in result] == ["b", "c"]


def _entries_ending_in_a_distinct_newest(entry_count: int) -> list[CookieTouch]:
    return [_worst_case_touch("漢")] * (entry_count - 1) + [_worst_case_touch("字")]


@pytest.mark.parametrize("entry_count", [1, 5, 10])
def test_a_multibyte_worst_case_cookie_fits_the_browser_limit_with_a_touch_list(
    entry_count: int,
) -> None:
    response = HttpResponse()

    set_attribution_cookie(
        response,
        _first_touch(utm_source="x"),
        touches=_entries_ending_in_a_distinct_newest(entry_count),
    )

    name_and_value = f"{config.REFERRAL_TRACKING_COOKIE_NAME}={_cookie_from(response)}"
    assert len(name_and_value) <= 4096


@pytest.mark.parametrize("entry_count", [1, 5, 10])
def test_a_multibyte_worst_case_cookie_keeps_the_newest_entry(
    entry_count: int,
) -> None:
    response = HttpResponse()
    set_attribution_cookie(
        response,
        _first_touch(utm_source="x"),
        touches=_entries_ending_in_a_distinct_newest(entry_count),
    )

    read_back = read_cookie_touches(_request_holding(response))

    assert read_back[-1].utm_campaign == "字" * CAPS["utm_campaign"]


def test_a_worst_case_entry_that_cannot_fit_beside_the_first_touch_sets_nothing() -> (
    None
):
    first_touch = first_touch_from_request(_landing_with_every_value_at_its_cap("漢"))
    response = HttpResponse()

    was_set = set_attribution_cookie(
        response, first_touch, touches=[_worst_case_touch("字")]
    )

    assert was_set is False
    assert config.REFERRAL_TRACKING_COOKIE_NAME not in response.cookies


def _flushable_payload(entries: list[dict[str, str]]) -> HttpRequest:
    return _request_holding_payload(
        {
            "ts": NOW.isoformat(),
            "rc": "A",
            "p": "/landing/",
            COOKIE_TOUCHES_KEY: entries,
        }
    )


@time_machine.travel(NOW + datetime.timedelta(days=30), tick=False)
def test_flushable_touches_lead_with_the_first_touch_and_its_landing_path() -> None:
    later = (NOW + datetime.timedelta(days=2)).isoformat()
    request = _flushable_payload([{"rc": "B", "ts": later}])

    touches = flushable_cookie_touches(request)

    assert [(t.referral_code, t.landing_path) for t in touches] == [
        ("A", "/landing/"),
        ("B", ""),
    ]


@time_machine.travel(NOW + datetime.timedelta(days=30), tick=False)
def test_flushable_touches_drop_entries_outside_the_cookies_lifetime() -> None:
    before = (NOW - datetime.timedelta(days=1)).isoformat()
    future = (NOW + datetime.timedelta(days=60)).isoformat()
    request = _flushable_payload([{"rc": "B", "ts": before}, {"rc": "C", "ts": future}])

    touches = flushable_cookie_touches(request)

    assert [t.referral_code for t in touches] == ["A"]


@time_machine.travel(NOW + datetime.timedelta(days=30), tick=False)
def test_flushable_touches_drop_entries_with_every_attribution_value_blank() -> None:
    request = _flushable_payload(
        [{"ts": (NOW + datetime.timedelta(days=2)).isoformat()}]
    )

    touches = flushable_cookie_touches(request)

    assert [t.referral_code for t in touches] == ["A"]


def test_flushable_touches_are_empty_without_a_cookie() -> None:
    assert flushable_cookie_touches(rf.get("/")) == []


def test_a_request_is_not_cookie_clear_requested_by_default() -> None:
    assert not is_cookie_clear_requested(rf.get("/"))


def test_requesting_a_cookie_clear_is_visible_on_the_request() -> None:
    request = rf.get("/")

    request_cookie_clear(request)

    assert is_cookie_clear_requested(request)
