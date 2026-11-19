"""Tests for the educator interface's template tags."""

from __future__ import annotations

from freedom_ls.educator_interface.templatetags.educator_tags import lookup


def test_lookup_gives_the_value_of_a_present_key() -> None:
    assert lookup({"a": 1}, "a") == 1


def test_lookup_gives_none_for_a_missing_key() -> None:
    assert lookup({"a": 1}, "b") is None
