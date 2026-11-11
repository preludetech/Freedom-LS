from __future__ import annotations

import phonenumbers
import pytest
from phonenumbers import PhoneNumberFormat

from django.utils import translation

from freedom_ls.form_engine.phone_numbers import (
    country_choices,
    display_phone,
    e164_phone_answer,
    national_phone,
    phone_answer_error,
    stored_phone_country,
)

ZA_MESSAGE = (
    'You entered "{text}". Enter a valid phone number for South Africa, '
    "like 010 123 4567."
)
ITALIAN_NATIONAL = phonenumbers.format_number(
    phonenumbers.example_number("IT"), PhoneNumberFormat.NATIONAL
)


@pytest.mark.parametrize(
    ("text", "country", "expected"),
    [
        ("082 123 4567", "ZA", "+27821234567"),
        ("+27 82 123 4567", "GB", "+27821234567"),
        ("(082) 123-4567", "ZA", "+27821234567"),
        (ITALIAN_NATIONAL, "IT", "+390212345678"),
    ],
)
def test_valid_phone_answer_is_accepted_and_stored_as_e164(
    text: str, country: str, expected: str
) -> None:
    assert phone_answer_error(text, country) is None
    assert e164_phone_answer(text, country) == expected


def test_national_number_without_a_country_asks_for_one() -> None:
    assert phone_answer_error("082 123 4567", "") == (
        'You entered "082 123 4567". Choose a country, or start the number '
        "with + and its country code."
    )


@pytest.mark.parametrize("text", ["hello", "099 123 4567"])
def test_invalid_national_number_names_the_country_and_an_example(text: str) -> None:
    assert phone_answer_error(text, "ZA") == ZA_MESSAGE.format(text=text)


def test_invalid_international_number_asks_for_a_country_code() -> None:
    assert phone_answer_error("+27 12", "ZA") == (
        'You entered "+27 12". Enter a valid phone number, starting with + '
        "and its country code."
    )


def test_number_with_an_extension_is_rejected() -> None:
    assert phone_answer_error("082 123 4567 ext. 12", "ZA") == (
        'You entered "082 123 4567 ext. 12". Enter the number without an extension.'
    )


@pytest.mark.parametrize("text", ["0800 FLOWERS", "082 123 4S67"])
def test_number_written_with_letters_is_rejected(text: str) -> None:
    assert phone_answer_error(text, "ZA") == ZA_MESSAGE.format(text=text)


def test_invalid_number_message_omits_the_example_when_the_country_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(phonenumbers, "example_number", lambda country: None)

    assert phone_answer_error("hello", "ZA") == (
        'You entered "hello". Enter a valid phone number for South Africa.'
    )


def test_country_choices_include_the_name_and_calling_code() -> None:
    assert ("ZA", "South Africa (+27)") in country_choices()


def test_country_choices_sort_accented_names_with_their_unaccented_letter() -> None:
    codes = [code for code, _label in country_choices()]

    assert codes.index("AF") < codes.index("AX") < codes.index("AL")


def test_country_choices_fall_back_to_the_code_when_the_language_has_no_name() -> None:
    with translation.override("ce"):
        choices = country_choices()

    assert ("MK", "MK (+389)") in choices


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("+27821234567", "+27 82 123 4567"),
        ("082 123 4567", "082 123 4567"),
        ("hello", "hello"),
    ],
)
def test_display_phone_formats_e164_and_leaves_legacy_text_as_typed(
    stored: str, expected: str
) -> None:
    assert display_phone(stored) == expected


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("+27821234567", "ZA"), ("082 123 4567", None), ("hello", None)],
)
def test_stored_phone_country_names_the_country_of_an_e164_answer(
    stored: str, expected: str | None
) -> None:
    assert stored_phone_country(stored) == expected


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("+27821234567", "082 123 4567"),
        ("082 123 4567", "082 123 4567"),
        ("hello", "hello"),
    ],
)
def test_national_phone_formats_e164_and_leaves_legacy_text_as_typed(
    stored: str, expected: str
) -> None:
    assert national_phone(stored) == expected


def test_non_geographic_number_has_no_country_and_keeps_its_stored_text() -> None:
    stored = "+80012345678"

    assert stored_phone_country(stored) is None
    assert national_phone(stored) == stored


@pytest.mark.parametrize(
    "stored",
    [
        "+27101234567",
        "+390212345678",
        "+12015550123",
        "+441212345678",
        "+541123456789",
        "+522001234567",
        "+551123456789",
    ],
)
def test_refilled_country_and_number_resubmit_to_the_stored_answer(
    stored: str,
) -> None:
    country = stored_phone_country(stored) or ""
    number = national_phone(stored)

    assert phone_answer_error(number, country) is None
    assert e164_phone_answer(number, country) == stored
