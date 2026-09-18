"""The shipped demo content has to show every way a course can be priced,
so each price display can be seen without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from freedom_ls.content_engine.models import Course, PriceKind

pytestmark = pytest.mark.fls_internal

PRICE_FIELDS = (
    "price_kind",
    "price_amount",
    "price_sale_amount",
    "price_sale_ends_on",
    "price_low_amount",
    "price_high_amount",
    "price_currency",
    "price_tax_note",
)

EXPECTED_PRICES: dict[str, dict[str, object]] = {
    "Functionality Demo - Price: fixed": {
        "price_kind": PriceKind.FIXED,
        "price_amount": Decimal("250.00"),
        "price_currency": "USD",
        "price_tax_note": "excl. tax",
    },
    "Functionality Demo - Price: range": {
        "price_kind": PriceKind.RANGE,
        "price_low_amount": Decimal("1200.00"),
        "price_high_amount": Decimal("3000.00"),
        "price_currency": "ZAR",
    },
    "Functionality Demo - Price: from": {
        "price_kind": PriceKind.RANGE,
        "price_low_amount": Decimal("500.00"),
        "price_currency": "ZAR",
    },
    "Functionality Demo - Price: sale with an end date": {
        "price_kind": PriceKind.DISCOUNTED,
        "price_amount": Decimal("400.00"),
        "price_sale_amount": Decimal("300.00"),
        "price_sale_ends_on": date(2099, 12, 31),
        "price_currency": "EUR",
        "price_tax_note": "incl. VAT",
    },
    "Functionality Demo - Price: expired sale": {
        "price_kind": PriceKind.DISCOUNTED,
        "price_amount": Decimal("800.00"),
        "price_sale_amount": Decimal("500.00"),
        "price_sale_ends_on": date(2020, 1, 1),
        "price_currency": "ZAR",
    },
    "Functionality Demo - Price: on request": {
        "price_kind": PriceKind.ON_REQUEST,
    },
    "Functionality Demo - Price: currency without cents": {
        "price_kind": PriceKind.FIXED,
        "price_amount": Decimal("15000"),
        "price_currency": "JPY",
    },
    "Functionality Demo - Application gated course": {
        "price_kind": PriceKind.DISCOUNTED,
        "price_amount": Decimal("1499.00"),
        "price_sale_amount": Decimal("999.00"),
        "price_currency": "ZAR",
        "price_tax_note": "incl. VAT",
    },
}


def _stored_price(course: Course) -> dict[str, object]:
    """The course's price fields, leaving out the empty ones."""
    stored = {field: getattr(course, field) for field in PRICE_FIELDS}
    return {field: value for field, value in stored.items() if value not in (None, "")}


@pytest.mark.django_db
def test_every_demo_pricing_course_loads_with_its_price(site, loaded_demo_content):
    courses = Course.objects.filter(site=site, title__in=EXPECTED_PRICES)

    stored = {course.title: _stored_price(course) for course in courses}

    assert stored == EXPECTED_PRICES


def test_the_demo_pricing_courses_cover_every_price_kind():
    kinds = {price["price_kind"] for price in EXPECTED_PRICES.values()}

    assert kinds == set(PriceKind)
