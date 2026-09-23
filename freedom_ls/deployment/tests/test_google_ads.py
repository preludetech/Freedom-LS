from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.deployment.google_ads import (
    conversion_send_to,
    parse_conversion_labels,
)


class TestParseConversionLabels:
    def test_empty_string_gives_no_labels(self) -> None:
        assert parse_conversion_labels("") == {}

    def test_one_pair(self) -> None:
        assert parse_conversion_labels("sign_up=AbCdEf") == {"sign_up": "AbCdEf"}

    def test_several_pairs(self) -> None:
        assert parse_conversion_labels("sign_up=AbCdEf,course_registered=GhIjKl") == {
            "sign_up": "AbCdEf",
            "course_registered": "GhIjKl",
        }

    def test_whitespace_around_pairs_and_sides_is_ignored(self) -> None:
        assert parse_conversion_labels(
            " sign_up = AbCdEf , course_registered=GhIjKl "
        ) == {
            "sign_up": "AbCdEf",
            "course_registered": "GhIjKl",
        }

    def test_trailing_comma_is_ignored(self) -> None:
        assert parse_conversion_labels("sign_up=AbCdEf,") == {"sign_up": "AbCdEf"}

    def test_pair_without_equals_raises_naming_the_pair(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="sign_up"):
            parse_conversion_labels("sign_up")

    def test_pair_with_empty_label_raises(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="sign_up="):
            parse_conversion_labels("sign_up=")

    def test_pair_with_empty_event_name_raises(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="=AbCdEf"):
            parse_conversion_labels("=AbCdEf")


class TestConversionSendTo:
    def test_joins_conversion_id_and_label(self) -> None:
        assert conversion_send_to("AW-1", {"sign_up": "abc"}, "sign_up") == "AW-1/abc"

    def test_none_when_no_conversion_id(self) -> None:
        assert conversion_send_to(None, {"sign_up": "abc"}, "sign_up") is None

    def test_none_when_event_has_no_label(self) -> None:
        assert conversion_send_to("AW-1", {"sign_up": "abc"}, "course_started") is None
