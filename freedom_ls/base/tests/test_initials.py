"""Tests for the shared initials-composition helpers."""

import pytest

from freedom_ls.base.initials import is_latin, two_or_one


class TestIsLatin:
    def test_latin_letter_is_latin(self) -> None:
        assert is_latin("M") is True

    def test_latin_letter_with_diacritic_is_latin(self) -> None:
        assert is_latin("É") is True

    def test_cjk_character_is_not_latin(self) -> None:
        assert is_latin("田") is False

    def test_digit_is_not_latin(self) -> None:
        assert is_latin("7") is False

    def test_empty_string_is_not_latin(self) -> None:
        assert is_latin("") is False


class TestTwoOrOne:
    def test_two_latin_letters_compose_uppercase_pair(self) -> None:
        assert two_or_one("m", "j") == "MJ"

    def test_second_non_latin_falls_back_to_single_letter(self) -> None:
        assert two_or_one("m", "田") == "M"

    def test_missing_second_falls_back_to_single_letter(self) -> None:
        assert two_or_one("m", "") == "M"

    @pytest.mark.parametrize(
        ("first", "second", "expected"), [("a", "b", "AB"), ("z", "", "Z")]
    )
    def test_parametrized_cases(self, first: str, second: str, expected: str) -> None:
        assert two_or_one(first, second) == expected
