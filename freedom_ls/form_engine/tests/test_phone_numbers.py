from __future__ import annotations

from collections.abc import Iterator

import phonenumbers
import pytest
from phonenumbers import PhoneNumberFormat
from pytest_django.fixtures import SettingsWrapper

from django.utils import translation

from freedom_ls.form_engine import phone_numbers
from freedom_ls.form_engine.phone_numbers import (
    browser_country,
    country_choices,
    display_phone,
    e164_phone_answer,
    phone_after_calling_code,
    phone_answer_error,
    phone_example,
    phone_examples,
    stored_phone_country,
)

ZA_MESSAGE = (
    'You entered "{text}". Enter a valid phone number for South Africa, '
    "like 71 123 4567."
)
ITALIAN_NATIONAL = phonenumbers.format_number(
    phonenumbers.example_number("IT"), PhoneNumberFormat.NATIONAL
)


@pytest.mark.parametrize(
    ("text", "country", "expected"),
    [
        ("82 123 4567", "ZA", "+27821234567"),
        ("+27 82 123 4567", "GB", "+27821234567"),
        ("(82) 123-4567", "ZA", "+27821234567"),
        (ITALIAN_NATIONAL, "IT", "+390212345678"),
        ("(+27) 82 123 4567", "", "+27821234567"),
        ("(+27) 82 123 4567", "US", "+27821234567"),
        # An invisible direction mark, as a contacts app puts before a copied number.
        ("‪+27 82 123 4567", "", "+27821234567"),
        ("‪+27 82 123 4567", "US", "+27821234567"),
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


@pytest.mark.parametrize(
    ("text", "extra"),
    [("082 123 4567", "0"), ("27821234567", "27"), ("0027 82 123 4567", "0027")],
)
def test_number_typed_with_digits_before_the_calling_code_follows_is_rejected(
    text: str, extra: str
) -> None:
    assert phone_answer_error(text, "ZA") == (
        f'You entered "{text}". Leave out the {extra} at the start, like 71 123 4567.'
    )


def test_number_that_does_not_end_with_the_national_number_names_the_calling_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        phonenumbers, "national_significant_number", lambda number: "999999999"
    )

    assert phone_answer_error("82 123 4567", "ZA") == (
        'You entered "82 123 4567". Enter the number that follows +27, '
        "like 71 123 4567."
    )


@pytest.mark.parametrize("text", ["hello", "99 123 4567", "82 12"])
def test_invalid_national_number_names_the_country_and_an_example(text: str) -> None:
    assert phone_answer_error(text, "ZA") == ZA_MESSAGE.format(text=text)


@pytest.mark.parametrize(
    ("text", "country"), [("+27 12", "ZA"), ("(+27) 12", ""), ("(+27) 12", "US")]
)
def test_invalid_international_number_asks_for_a_country_code(
    text: str, country: str
) -> None:
    assert phone_answer_error(text, country) == (
        f'You entered "{text}". Enter a valid phone number, starting with + '
        "and its country code."
    )


def test_number_with_an_extension_is_rejected() -> None:
    assert phone_answer_error("82 123 4567 ext. 12", "ZA") == (
        'You entered "82 123 4567 ext. 12". Enter the number without an extension.'
    )


@pytest.mark.parametrize("text", ["0800 FLOWERS", "82 123 4S67"])
def test_number_written_with_letters_is_rejected(text: str) -> None:
    assert phone_answer_error(text, "ZA") == ZA_MESSAGE.format(text=text)


def test_invalid_number_message_omits_the_example_when_the_country_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(phonenumbers, "example_number", lambda country: None)
    monkeypatch.setattr(
        phonenumbers, "example_number_for_type", lambda country, kind: None
    )

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


@pytest.fixture
def _fresh_locale_caches() -> Iterator[None]:
    """The country names are cached per language, and these tests change what
    a language resolves to."""
    phone_numbers._locale.cache_clear()
    phone_numbers._country_choices.cache_clear()
    yield
    phone_numbers._locale.cache_clear()
    phone_numbers._country_choices.cache_clear()


@pytest.mark.usefixtures("_fresh_locale_caches")
def test_country_choices_use_the_site_language_when_babel_lacks_the_active_one(
    settings: SettingsWrapper,
) -> None:
    settings.LANGUAGE_CODE = "fr"

    with translation.override("udm"):
        choices = country_choices()

    assert ("ZA", "Afrique du Sud (+27)") in choices


@pytest.mark.usefixtures("_fresh_locale_caches")
def test_country_choices_are_english_when_babel_lacks_the_site_language_too(
    settings: SettingsWrapper,
) -> None:
    settings.LANGUAGE_CODE = "udm"

    with translation.override("udm"):
        choices = country_choices()

    assert ("ZA", "South Africa (+27)") in choices


LEGACY_TEXT_STARTING_WITH_A_PLUS = [
    "+27 82 123 4567 (mom)",
    "+27 82 123 4567 home",
    "+27 82 CALL ME",
    "+27 82 123 4567",
]


@pytest.mark.parametrize("stored", LEGACY_TEXT_STARTING_WITH_A_PLUS)
def test_stored_text_that_is_not_exactly_e164_is_shown_and_refilled_as_typed(
    stored: str,
) -> None:
    assert display_phone(stored) == stored
    assert stored_phone_country(stored) is None
    assert phone_after_calling_code(stored) == stored


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
        ("+27821234567", "82 123 4567"),
        ("+390212345678", "02 1234 5678"),
        ("082 123 4567", "082 123 4567"),
        ("hello", "hello"),
    ],
)
def test_phone_after_calling_code_drops_the_calling_code_and_leaves_legacy_text(
    stored: str, expected: str
) -> None:
    assert phone_after_calling_code(stored) == expected


def test_non_geographic_number_has_no_country_and_keeps_its_stored_text() -> None:
    stored = "+80012345678"

    assert stored_phone_country(stored) is None
    assert phone_after_calling_code(stored) == stored


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
    number = phone_after_calling_code(stored)

    assert phone_answer_error(number, country) is None
    assert e164_phone_answer(number, country) == stored


@pytest.mark.parametrize(
    ("country", "expected"), [("ZA", "71 123 4567"), ("GB", "7400 123456")]
)
def test_phone_example_is_a_mobile_number_written_after_its_calling_code(
    country: str, expected: str
) -> None:
    assert phone_example(country) == expected


def test_phone_example_is_none_when_the_library_has_no_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(phonenumbers, "example_number", lambda country: None)
    monkeypatch.setattr(
        phonenumbers, "example_number_for_type", lambda country, kind: None
    )

    assert phone_example("ZA") is None


@pytest.mark.parametrize("country", sorted(phonenumbers.SUPPORTED_REGIONS))
def test_every_country_example_is_an_accepted_answer(country: str) -> None:
    assert phone_answer_error(phone_examples()[country], country) is None


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("en-ZA", "ZA"),
        ("en-GB,en;q=0.9", "GB"),
        ("en, fr-FR;q=0.8", "FR"),
        ("fr-FR;q=0.5, de-DE;q=0.9", "DE"),
        ("en-ZA;q=0, fr-FR;q=0.5", "FR"),
        ("zh-Hant-TW", "TW"),
        ("es-419", None),
        ("en", None),
        ("*", None),
        ("", None),
        ("en-001", None),
        (";;;,=", None),
        ("en-ZA;q=banana", None),
    ],
)
def test_browser_country_reads_the_country_an_accept_language_header_prefers(
    header: str, expected: str | None
) -> None:
    assert browser_country(header) == expected
