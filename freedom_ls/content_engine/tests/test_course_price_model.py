"""Tests for Course price fields, the DB constraint, clean() and current_price()."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import time_machine

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import PriceKind
from freedom_ls.content_engine.prices import KIND_FIELDS, CoursePrice

# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fixed_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.000")
    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_range_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("1200.000"),
        price_high_amount=Decimal("3000.000"),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("1200.000")
    assert course.price_high_amount == Decimal("3000.000")


@pytest.mark.django_db
def test_discounted_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
    )
    course.refresh_from_db()

    assert course.price_kind == PriceKind.DISCOUNTED
    assert course.price_amount == Decimal("1499.000")
    assert course.price_sale_amount == Decimal("999.000")
    assert course.price_sale_ends_on == date(2026, 12, 31)


@pytest.mark.django_db
def test_on_request_price_round_trips(mock_site_context) -> None:
    course = CourseFactory(price_kind=PriceKind.ON_REQUEST)
    course.refresh_from_db()

    assert course.price_kind == PriceKind.ON_REQUEST


@pytest.mark.django_db
def test_course_defaults_to_no_price(mock_site_context) -> None:
    course = CourseFactory()
    course.refresh_from_db()

    assert course.price_kind == ""


# ---------------------------------------------------------------------------
# CheckConstraint: course_price_fields_match_kind
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fixed_price_rejects_a_stray_low_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("100.000"),
            price_currency="ZAR",
            price_low_amount=Decimal("50.000"),
        )


@pytest.mark.django_db
def test_fixed_price_rejects_a_non_positive_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("0.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_fixed_price_rejects_a_blank_currency(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("100.000"),
            price_currency="",
        )


@pytest.mark.django_db
def test_range_price_rejects_low_not_below_high(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.RANGE,
            price_low_amount=Decimal("100.000"),
            price_high_amount=Decimal("100.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_discounted_price_rejects_sale_not_below_original(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(
            price_kind=PriceKind.DISCOUNTED,
            price_amount=Decimal("100.000"),
            price_sale_amount=Decimal("100.000"),
            price_currency="ZAR",
        )


@pytest.mark.django_db
def test_on_request_price_rejects_a_stray_currency(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(price_kind=PriceKind.ON_REQUEST, price_currency="ZAR")


@pytest.mark.django_db
def test_no_price_rejects_a_stray_amount(mock_site_context) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseFactory(price_kind="", price_amount=Decimal("100.000"))


# ---------------------------------------------------------------------------
# Course.clean()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_clean_fills_a_blank_currency_from_the_default(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.FIXED, price_amount=Decimal("100.000")
    )

    with override_settings(DEFAULT_CURRENCY="ZAR"):
        course.clean()

    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_clean_errors_when_currency_missing_and_no_default(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.FIXED, price_amount=Decimal("100.000")
    )

    with (
        override_settings(DEFAULT_CURRENCY=None),
        pytest.raises(ValidationError) as excinfo,
    ):
        course.clean()

    assert "price_currency" in excinfo.value.message_dict


@pytest.mark.django_db
def test_clean_errors_on_a_stray_field_for_the_kind(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind=PriceKind.ON_REQUEST, price_amount=Decimal("100.000")
    )

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert "price_amount" in excinfo.value.message_dict


@pytest.mark.django_db
def test_clean_errors_when_price_fields_set_without_a_kind(mock_site_context) -> None:
    course = CourseFactory.build(
        price_kind="", price_amount=Decimal("100.000"), price_currency="ZAR"
    )

    with pytest.raises(ValidationError) as excinfo:
        course.clean()

    assert "price_kind" in excinfo.value.message_dict


@pytest.mark.django_db
def test_clean_passes_for_a_course_with_no_price(mock_site_context) -> None:
    course = CourseFactory.build()

    course.clean()


# ---------------------------------------------------------------------------
# Course.current_price()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_current_price_is_none_when_no_price_is_set(mock_site_context) -> None:
    course = CourseFactory()

    assert course.current_price() is None


@pytest.mark.django_db
def test_current_price_for_a_fixed_price(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
        price_tax_note="incl. VAT",
    )

    price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.FIXED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        tax_note="incl. VAT",
    )


@pytest.mark.django_db
def test_current_price_for_a_range_price(mock_site_context) -> None:
    course = CourseFactory(
        price_kind=PriceKind.RANGE,
        price_low_amount=Decimal("1200.000"),
        price_high_amount=Decimal("3000.000"),
        price_currency="ZAR",
    )

    price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.RANGE,
        currency="ZAR",
        low_amount=Decimal("1200.000"),
        high_amount=Decimal("3000.000"),
    )


@pytest.mark.django_db
def test_current_price_for_on_request(mock_site_context) -> None:
    course = CourseFactory(price_kind=PriceKind.ON_REQUEST)

    price = course.current_price()

    assert price == CoursePrice(kind=PriceKind.ON_REQUEST)


@pytest.mark.django_db
def test_current_price_discount_is_live_on_the_sale_end_date(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
    )

    with time_machine.travel("2026-12-31T23:00:00Z", tick=False):
        price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.DISCOUNTED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        sale_amount=Decimal("999.000"),
        sale_ends_on=date(2026, 12, 31),
    )


@pytest.mark.django_db
def test_current_price_discount_becomes_fixed_the_day_after_it_ends(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_sale_ends_on=date(2026, 12, 31),
        price_currency="ZAR",
        price_tax_note="incl. VAT",
    )

    with time_machine.travel("2027-01-01T00:00:00Z", tick=False):
        price = course.current_price()

    assert price == CoursePrice(
        kind=PriceKind.FIXED,
        currency="ZAR",
        amount=Decimal("1499.000"),
        tax_note="incl. VAT",
    )


@pytest.mark.django_db
def test_current_price_discount_with_no_end_date_never_expires(
    mock_site_context,
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.000"),
        price_sale_amount=Decimal("999.000"),
        price_currency="ZAR",
    )

    with time_machine.travel("2099-01-01T00:00:00Z", tick=False):
        price = course.current_price()

    assert price.kind == PriceKind.DISCOUNTED


@pytest.mark.django_db
def test_current_price_runs_no_queries(
    mock_site_context, django_assert_num_queries
) -> None:
    course = CourseFactory(
        price_kind=PriceKind.FIXED,
        price_amount=Decimal("1499.000"),
        price_currency="ZAR",
    )

    with django_assert_num_queries(0):
        course.current_price()


# ---------------------------------------------------------------------------
# KIND_FIELDS <-> PriceKind parity
# ---------------------------------------------------------------------------


def test_kind_fields_keys_match_price_kind_values() -> None:
    assert set(KIND_FIELDS) == set(PriceKind.values)
