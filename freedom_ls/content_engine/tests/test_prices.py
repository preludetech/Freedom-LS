"""Tests for price validation rules and CoursePrice formatting/JSON-LD."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from django.db import models
from django.test import override_settings

from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.prices import (
    AMOUNT_DECIMAL_PLACES,
    AMOUNT_MAX_DIGITS,
    KIND_FIELDS,
    CoursePrice,
    price_errors,
    price_locale,
)

# price_errors: currency and decimal-place rules


def test_unknown_currency_code_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("100"), currency="ZZZ")

    assert "currency" in errors


def test_jpy_amount_with_fractional_yen_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("1500.50"), currency="JPY")

    assert "amount" in errors


def test_kwd_amount_with_four_decimal_places_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("1.2345"), currency="KWD")

    assert "amount" in errors


def test_kwd_amount_with_three_decimal_places_is_accepted() -> None:
    errors = price_errors("fixed", amount=Decimal("1.234"), currency="KWD")

    assert errors == {}


def test_zar_amount_with_trailing_zero_decimal_places_is_accepted() -> None:
    errors = price_errors("fixed", amount=Decimal("1499.000"), currency="ZAR")

    assert errors == {}


def test_blank_currency_skips_the_decimal_place_check() -> None:
    errors = price_errors("fixed", amount=Decimal("1500.50"), currency="")

    assert errors == {}


def test_blank_currency_skips_the_currency_code_check() -> None:
    errors = price_errors("fixed", amount=Decimal("100"), currency="")

    assert "currency" not in errors


# price_errors: required and stray fields, one per kind


def test_fixed_price_missing_amount_reports_amount_required() -> None:
    errors = price_errors("fixed", currency="ZAR")

    assert errors == {"amount": "Required for a fixed price."}


def test_fixed_price_with_low_amount_reports_low_amount_not_used() -> None:
    errors = price_errors(
        "fixed", amount=Decimal("100"), low_amount=Decimal("50"), currency="ZAR"
    )

    assert errors == {"low_amount": "Not used by a fixed price."}


def test_range_price_without_high_amount_is_open_ended_and_valid() -> None:
    errors = price_errors("range", low_amount=Decimal("100"), currency="ZAR")

    assert errors == {}


def test_range_price_missing_low_amount_reports_low_amount_required() -> None:
    errors = price_errors("range", high_amount=Decimal("100"), currency="ZAR")

    assert errors == {"low_amount": "Required for a range price."}


def test_range_price_with_sale_amount_reports_sale_amount_not_used() -> None:
    errors = price_errors(
        "range",
        low_amount=Decimal("100"),
        high_amount=Decimal("200"),
        sale_amount=Decimal("50"),
        currency="ZAR",
    )

    assert errors == {"sale_amount": "Not used by a range price."}


def test_discounted_price_missing_sale_amount_reports_sale_amount_required() -> None:
    errors = price_errors("discounted", amount=Decimal("100"), currency="ZAR")

    assert errors == {"sale_amount": "Required for a discounted price."}


def test_discounted_price_with_low_amount_reports_low_amount_not_used() -> None:
    errors = price_errors(
        "discounted",
        amount=Decimal("100"),
        sale_amount=Decimal("50"),
        low_amount=Decimal("10"),
        currency="ZAR",
    )

    assert errors == {"low_amount": "Not used by a discounted price."}


def test_on_request_price_with_amount_reports_amount_not_used() -> None:
    errors = price_errors("on_request", amount=Decimal("100"))

    assert errors == {"amount": "Not used by an on-request price."}


def test_on_request_price_with_currency_reports_currency_not_used() -> None:
    errors = price_errors("on_request", currency="ZAR")

    assert errors == {"currency": "Not used by an on-request price."}


def test_on_request_price_with_no_fields_has_no_errors() -> None:
    errors = price_errors("on_request")

    assert errors == {}


# price_errors: amount validity


def test_zero_amount_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("0"), currency="ZAR")

    assert errors == {"amount": "Must be greater than zero."}


def test_negative_amount_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("-10"), currency="ZAR")

    assert errors == {"amount": "Must be greater than zero."}


def test_nan_amount_is_rejected_as_not_finite() -> None:
    errors = price_errors("fixed", amount=Decimal("NaN"), currency="ZAR")

    assert errors == {"amount": "Must be a finite number."}


def test_amount_too_large_for_the_column_is_rejected() -> None:
    errors = price_errors("fixed", amount=Decimal("1000000000"), currency="IDR")

    assert errors == {"amount": "Too large."}


def test_largest_amount_the_column_holds_is_accepted() -> None:
    errors = price_errors("fixed", amount=Decimal("999999999.999"), currency="KWD")

    assert errors == {}


def test_amount_with_more_decimal_places_than_the_column_is_rejected() -> None:
    """CLF allows four decimal places, but the column stores only three."""
    errors = price_errors("fixed", amount=Decimal("0.1234"), currency="CLF")

    assert errors == {"amount": "Can have at most 3 decimal places."}


@pytest.mark.parametrize(
    "field_name",
    ["price_amount", "price_sale_amount", "price_low_amount", "price_high_amount"],
)
def test_amount_limits_match_the_course_columns(field_name: str) -> None:
    field = Course._meta.get_field(field_name)

    assert isinstance(field, models.DecimalField)
    assert field.max_digits == AMOUNT_MAX_DIGITS
    assert field.decimal_places == AMOUNT_DECIMAL_PLACES


# price_errors: ordering rules, both directions


def test_sale_amount_equal_to_amount_is_rejected() -> None:
    errors = price_errors(
        "discounted", amount=Decimal("100"), sale_amount=Decimal("100"), currency="ZAR"
    )

    assert errors == {"sale_amount": "Must be less than the full amount."}


def test_sale_amount_greater_than_amount_is_rejected() -> None:
    errors = price_errors(
        "discounted", amount=Decimal("100"), sale_amount=Decimal("150"), currency="ZAR"
    )

    assert errors == {"sale_amount": "Must be less than the full amount."}


def test_sale_amount_less_than_amount_is_accepted() -> None:
    errors = price_errors(
        "discounted", amount=Decimal("100"), sale_amount=Decimal("50"), currency="ZAR"
    )

    assert errors == {}


def test_low_amount_equal_to_high_amount_is_rejected() -> None:
    errors = price_errors(
        "range", low_amount=Decimal("100"), high_amount=Decimal("100"), currency="ZAR"
    )

    assert errors == {"high_amount": "Must be greater than the low amount."}


def test_low_amount_greater_than_high_amount_is_rejected() -> None:
    errors = price_errors(
        "range", low_amount=Decimal("200"), high_amount=Decimal("100"), currency="ZAR"
    )

    assert errors == {"high_amount": "Must be greater than the low amount."}


def test_low_amount_less_than_high_amount_is_accepted() -> None:
    errors = price_errors(
        "range", low_amount=Decimal("100"), high_amount=Decimal("200"), currency="ZAR"
    )

    assert errors == {}


# KIND_FIELDS


def test_kind_fields_covers_the_four_price_kinds() -> None:
    assert set(KIND_FIELDS) == {"fixed", "range", "discounted", "on_request"}


# price_locale


def test_price_locale_falls_back_to_language_code_when_unset() -> None:
    with override_settings(PRICE_LOCALE=None, LANGUAGE_CODE="en-us"):
        assert price_locale() == "en_US"


def test_price_locale_reads_the_setting_when_set() -> None:
    with override_settings(PRICE_LOCALE="en_ZA"):
        assert price_locale() == "en_ZA"


# CoursePrice formatting


def test_fixed_price_formats_amount_in_south_african_rand() -> None:
    price = CoursePrice(kind="fixed", currency="ZAR", amount=Decimal("1499.00"))

    with override_settings(PRICE_LOCALE="en_ZA"):
        formatted = price.formatted_amount

    assert formatted == "R1" + "\N{NO-BREAK SPACE}" + "499,00"


def test_range_price_formats_low_and_high_amounts() -> None:
    price = CoursePrice(
        kind="range",
        currency="ZAR",
        low_amount=Decimal("1200.00"),
        high_amount=Decimal("3000.00"),
    )

    with override_settings(PRICE_LOCALE="en_ZA"):
        low = price.formatted_low_amount
        high = price.formatted_high_amount

    assert low == "R1" + "\N{NO-BREAK SPACE}" + "200,00"
    assert high == "R3" + "\N{NO-BREAK SPACE}" + "000,00"


def test_discounted_price_formats_amount_and_sale_amount() -> None:
    price = CoursePrice(
        kind="discounted",
        currency="ZAR",
        amount=Decimal("1499.00"),
        sale_amount=Decimal("999.00"),
    )

    with override_settings(PRICE_LOCALE="en_ZA"):
        original = price.formatted_amount
        sale = price.formatted_sale_amount

    assert original == "R1" + "\N{NO-BREAK SPACE}" + "499,00"
    assert sale == "R999,00"


def test_formatted_amount_raises_when_amount_is_none() -> None:
    price = CoursePrice(kind="fixed", currency="ZAR")

    with pytest.raises(ValueError, match="no amount to format"):
        _ = price.formatted_amount


# CoursePrice.offers_json_ld


def test_fixed_price_offer_json_ld() -> None:
    price = CoursePrice(kind="fixed", currency="ZAR", amount=Decimal("1499.000"))

    assert price.offers_json_ld() == {
        "@type": "Offer",
        "price": "1499.00",
        "priceCurrency": "ZAR",
    }


def test_fixed_price_offer_json_ld_quantizes_to_currency_precision() -> None:
    price = CoursePrice(kind="fixed", currency="JPY", amount=Decimal("1500"))

    assert price.offers_json_ld() == {
        "@type": "Offer",
        "price": "1500",
        "priceCurrency": "JPY",
    }


def test_range_price_offer_json_ld() -> None:
    price = CoursePrice(
        kind="range",
        currency="ZAR",
        low_amount=Decimal("1200.000"),
        high_amount=Decimal("3000.000"),
    )

    assert price.offers_json_ld() == {
        "@type": "AggregateOffer",
        "lowPrice": "1200.00",
        "highPrice": "3000.00",
        "priceCurrency": "ZAR",
    }


def test_open_ended_range_price_offer_json_ld_has_no_high_price() -> None:
    price = CoursePrice(kind="range", currency="ZAR", low_amount=Decimal("500.000"))

    assert price.offers_json_ld() == {
        "@type": "AggregateOffer",
        "lowPrice": "500.00",
        "priceCurrency": "ZAR",
    }


def test_discounted_price_offer_json_ld_with_sale_end_date() -> None:
    price = CoursePrice(
        kind="discounted",
        currency="ZAR",
        amount=Decimal("1499.000"),
        sale_amount=Decimal("999.000"),
        sale_ends_on=date(2026, 12, 31),
    )

    assert price.offers_json_ld() == {
        "@type": "Offer",
        "price": "999.00",
        "priceCurrency": "ZAR",
        "priceValidUntil": "2026-12-31",
    }


def test_discounted_price_offer_json_ld_without_sale_end_date_has_no_valid_until() -> (
    None
):
    price = CoursePrice(
        kind="discounted",
        currency="ZAR",
        amount=Decimal("1499.000"),
        sale_amount=Decimal("999.000"),
    )

    offers = price.offers_json_ld()

    assert offers is not None
    assert "priceValidUntil" not in offers


def test_on_request_price_has_no_offer() -> None:
    price = CoursePrice(kind="on_request", currency="")

    assert price.offers_json_ld() is None
