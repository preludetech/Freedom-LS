"""Tests for the shared initials-composition helpers."""

import pytest

from freedom_ls.base.initials import is_latin, two_or_one


class TestIsLatin:
    @pytest.mark.parametrize(
        ("character", "expected"),
        [("M", True), ("É", True), ("田", False), ("7", False), ("", False)],
    )
    def test_latin_letters_are_latin_and_nothing_else_is(
        self, character: str, expected: bool
    ) -> None:
        assert is_latin(character) is expected


class TestTwoOrOne:
    def test_two_latin_letters_compose_uppercase_pair(self) -> None:
        assert two_or_one("m", "j") == "MJ"

    def test_second_non_latin_falls_back_to_single_letter(self) -> None:
        assert two_or_one("m", "田") == "M"

    def test_missing_second_falls_back_to_single_letter(self) -> None:
        assert two_or_one("m", "") == "M"
