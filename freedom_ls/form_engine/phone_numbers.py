"""Phone answers: the countries on offer, the check a submission must pass, and
the one stored form.

Every call into `phonenumbers` lives here, so the rest of the form engine
speaks in countries and strings. Imports no `models`, which reaches this
module through `typed_answers`.
"""

from __future__ import annotations

import functools
import unicodedata

import phonenumbers
from babel import Locale, UnknownLocaleError, parse_locale
from phonenumbers import (
    NumberParseException,
    PhoneNumber,
    PhoneNumberFormat,
    PhoneNumberType,
)

from django.conf import settings
from django.utils import translation

# The library's word for a country. Re-exported so callers that only need
# membership do not import the library themselves.
SUPPORTED_REGIONS = phonenumbers.SUPPORTED_REGIONS


def _active_language() -> str:
    # None while translations are deactivated, as in a management command.
    return translation.get_language() or settings.LANGUAGE_CODE


@functools.cache
def _locale(language: str) -> Locale:
    """Babel's locale for a Django language code.

    Django writes "en-us" where Babel wants "en_US". A language Babel does
    not know falls back to the site's default instead of failing the page.
    """
    try:
        return Locale.parse(translation.to_locale(language))
    except UnknownLocaleError:
        return Locale.parse(translation.to_locale(settings.LANGUAGE_CODE))


def _country_name(country: str, language: str) -> str:
    """The country's name in `language`, or its code when Babel has no name."""
    name: str = _locale(language).territories.get(country, country)
    return name


def _sort_key(name: str) -> str:
    # Accent-folded, so "Åland Islands" sorts under A instead of after Z.
    folded = unicodedata.normalize("NFKD", name)
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).casefold()


@functools.cache
def _country_choices(language: str) -> tuple[tuple[str, str], ...]:
    named = [
        (country, _country_name(country, language)) for country in SUPPORTED_REGIONS
    ]
    named.sort(key=lambda pair: _sort_key(pair[1]))
    return tuple(
        (country, f"{name} (+{phonenumbers.country_code_for_region(country)})")
        for country, name in named
    )


def country_choices() -> list[tuple[str, str]]:
    """One `(country, label)` pair per supported country, sorted by name."""
    return list(_country_choices(_active_language()))


def _parsed(text: str, country: str) -> PhoneNumber | None:
    """`text` as a phone number, or None when it does not parse.

    A leading + wins over the selected country: a pasted or autofilled
    international number is read as typed, whatever the picker says. For any
    other number the library strips a trunk prefix or calling code it finds;
    `_extra_digits_message` reports what it stripped.
    """
    default_country = None if text.startswith("+") else country or None
    try:
        return phonenumbers.parse(text, default_country)
    except NumberParseException:
        return None


def phone_answer_error(text: str, country: str) -> str | None:
    """Why `text`, with `country` selected, is not an acceptable phone answer."""
    if not text.startswith("+") and not country:
        return (
            f'You entered "{text}". Choose a country, or start the number '
            f"with + and its country code."
        )
    number = _parsed(text, country)
    if number is None:
        return _invalid_message(text, country)
    if number.extension:
        # E.164 cannot hold an extension, and dropping it without a word would
        # store a different number than the one typed.
        return f'You entered "{text}". Enter the number without an extension.'
    # The library reads letters as keypad digits ("0800 FLOWERS"). A typed word
    # is far more often a mistake than a vanity number.
    if any(ch.isalpha() for ch in text) or not phonenumbers.is_valid_number(number):
        return _invalid_message(text, country)
    if not text.startswith("+"):
        return _extra_digits_message(text, country, number)
    return None


def _like(country: str) -> str:
    example = phone_example(country)
    return f", like {example}" if example is not None else ""


def _extra_digits_message(text: str, country: str, number: PhoneNumber) -> str | None:
    """Why `text` is refused when it holds more than the digits that follow the
    calling code, or None when it holds exactly those.

    The picker reads "South Africa (+27)", so the box beside it holds what
    follows +27. A trunk 0, a calling code or an international prefix typed in
    front changes the number read that way, even though the library strips it.
    """
    typed = phonenumbers.normalize_digits_only(text)
    national = phonenumbers.national_significant_number(number)
    if typed == national:
        return None
    if typed.endswith(national):
        extra = typed[: -len(national)]
        return (
            f'You entered "{text}". Leave out the {extra} at the start{_like(country)}.'
        )
    calling_code = phonenumbers.country_code_for_region(country)
    return (
        f'You entered "{text}". Enter the number that follows '
        f"+{calling_code}{_like(country)}."
    )


def _invalid_message(text: str, country: str) -> str:
    if text.startswith("+"):
        return (
            f'You entered "{text}". Enter a valid phone number, starting '
            f"with + and its country code."
        )
    name = _country_name(country, _active_language())
    return (
        f'You entered "{text}". Enter a valid phone number for {name}{_like(country)}.'
    )


def _after_calling_code(number: PhoneNumber) -> str:
    """`number` as it is typed beside its country: no calling code, no trunk
    prefix (`82 123 4567`), so it resubmits to the same number."""
    international = phonenumbers.format_number(number, PhoneNumberFormat.INTERNATIONAL)
    return international.removeprefix(f"+{number.country_code}").strip()


def phone_example(country: str) -> str | None:
    """An example number for `country`, written as it follows the calling code.

    A mobile number where the library has one: it is what most people type.
    """
    example = phonenumbers.example_number_for_type(
        country, PhoneNumberType.MOBILE
    ) or phonenumbers.example_number(country)
    return _after_calling_code(example) if example is not None else None


@functools.cache
def _phone_examples() -> tuple[tuple[str, str], ...]:
    examples = ((country, phone_example(country)) for country in SUPPORTED_REGIONS)
    return tuple(
        (country, example) for country, example in examples if example is not None
    )


def phone_examples() -> dict[str, str]:
    """`phone_example` for every supported country that has one."""
    return dict(_phone_examples())


def e164_phone_answer(text: str, country: str) -> str:
    """The E.164 form of an answer `phone_answer_error` accepted."""
    number = _parsed(text, country)
    if number is None:
        raise ValueError(f"not a phone number: {text!r}")
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def _stored(text: str) -> PhoneNumber | None:
    """A stored answer as a phone number, or None for a legacy row (one that
    does not parse as E.164).

    Parsed with no country and never re-validated: a row accepted under an
    older release of the library must keep rendering after an upgrade, and a
    legacy row must stay readable.
    """
    if not text.startswith("+"):
        return None
    return _parsed(text, "")


def display_phone(text: str) -> str:
    """A stored answer in international format, or the raw text."""
    number = _stored(text)
    if number is None:
        return text
    return phonenumbers.format_number(number, PhoneNumberFormat.INTERNATIONAL)


def stored_phone_country(text: str) -> str | None:
    """The country of a stored E.164 answer, or None for a legacy row or a
    number that belongs to no supported country."""
    number = _stored(text)
    if number is None:
        return None
    # The library answers None for a number shared by no single country and
    # "001" for a non-geographic one; neither is a country on offer.
    country = phonenumbers.region_code_for_number(number)
    return country if country in SUPPORTED_REGIONS else None


def phone_after_calling_code(text: str) -> str:
    """A stored answer as it is typed beside its country, for refilling the
    number input.

    The raw text when there is no country to select beside it: a number with
    no country would not resubmit to the number that is stored.
    """
    number = _stored(text)
    if number is None or stored_phone_country(text) is None:
        return text
    return _after_calling_code(number)


def _quality(parameters: list[str]) -> float:
    """The tag's q value: 1 when absent, 0 when unreadable, so a tag with a
    broken weight is dropped instead of promoted."""
    for parameter in parameters:
        name, _, value = parameter.strip().partition("=")
        if name.strip() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def _tag_country(tag: str) -> str | None:
    """The country a language tag names, or None when it names none on offer."""
    try:
        _language, region_subtag, *_rest = parse_locale(tag, sep="-")
    except ValueError:
        # "*", an empty tag, or anything else that is not a language tag.
        return None
    # Membership also drops the numeric and non-geographic region subtags a
    # tag can carry: "419", "001", "EU".
    return region_subtag if region_subtag in SUPPORTED_REGIONS else None


def browser_country(accept_language: str) -> str | None:
    """The country the browser's Accept-Language header names, if any.

    Read by hand instead of through LocaleMiddleware, which would switch the
    active language for the whole site.
    """
    weighted: list[tuple[float, str]] = []
    for part in accept_language.split(","):
        tag, *parameters = part.split(";")
        quality = _quality(parameters)
        if quality > 0:
            weighted.append((quality, tag.strip()))
    # The sort is stable, so tags of equal weight keep the header's order.
    weighted.sort(key=lambda pair: -pair[0])
    countries = (_tag_country(tag) for _, tag in weighted)
    return next((country for country in countries if country is not None), None)
