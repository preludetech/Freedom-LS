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
from phonenumbers import NumberParseException, PhoneNumber, PhoneNumberFormat

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
    other number the library strips the country's own trunk prefix, so no
    digit is added or removed by hand.
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
    return None


def _invalid_message(text: str, country: str) -> str:
    if text.startswith("+"):
        return (
            f'You entered "{text}". Enter a valid phone number, starting '
            f"with + and its country code."
        )
    name = _country_name(country, _active_language())
    example = phonenumbers.example_number(country)
    like = (
        f", like {phonenumbers.format_number(example, PhoneNumberFormat.NATIONAL)}"
        if example is not None
        else ""
    )
    return f'You entered "{text}". Enter a valid phone number for {name}{like}.'


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


def national_phone(text: str) -> str:
    """A stored answer in national format, for refilling the number input.

    The raw text when there is no country to select beside it: a national
    number with no country would not resubmit to the number that is stored.
    """
    number = _stored(text)
    if number is None or stored_phone_country(text) is None:
        return text
    return phonenumbers.format_number(number, PhoneNumberFormat.NATIONAL)


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
