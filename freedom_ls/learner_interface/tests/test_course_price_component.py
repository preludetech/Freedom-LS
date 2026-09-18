"""Tests for the <c-course-price /> cotton component.

Renders the component through a template string with a ``CoursePrice`` in the
context, the same pattern ``test_button_component.py`` and
``test_error_page_component.py`` use for other cotton components.
"""

from __future__ import annotations

from decimal import Decimal

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template
from django.test import override_settings

from freedom_ls.content_engine.prices import CoursePrice

_cotton_compiler = CottonCompiler()


def _render(template_string: str, price: CoursePrice) -> str:
    processed = _cotton_compiler.process(template_string)
    t = Template(processed)
    return t.render(Context({"price": price}))


FIXED = CoursePrice(kind="fixed", currency="ZAR", amount=Decimal("1499.00"))
RANGE = CoursePrice(
    kind="range",
    currency="ZAR",
    low_amount=Decimal("1200.00"),
    high_amount=Decimal("3000.00"),
)
DISCOUNTED = CoursePrice(
    kind="discounted",
    currency="ZAR",
    amount=Decimal("1499.00"),
    sale_amount=Decimal("999.00"),
)
ON_REQUEST = CoursePrice(kind="on_request")


class TestFixedPrice:
    def test_compact_shows_formatted_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', FIXED)
        assert FIXED.formatted_amount in result

    def test_full_shows_formatted_amount(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', FIXED)
        assert FIXED.formatted_amount in result

    def test_compact_omits_tax_note(self) -> None:
        priced = CoursePrice(
            kind="fixed",
            currency="ZAR",
            amount=Decimal("1499.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" />', priced)
        assert "incl. VAT" not in result

    def test_full_shows_tax_note_when_set(self) -> None:
        priced = CoursePrice(
            kind="fixed",
            currency="ZAR",
            amount=Decimal("1499.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" variant="full" />', priced)
        assert "incl. VAT" in result

    def test_full_omits_tax_note_when_blank(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', FIXED)
        assert "incl. VAT" not in result


class TestRangePrice:
    def test_compact_shows_from_low_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', RANGE)
        assert f"From {RANGE.formatted_low_amount}" in result
        assert RANGE.formatted_high_amount not in result

    def test_full_shows_low_and_high_amount(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', RANGE)
        assert RANGE.formatted_low_amount in result
        assert RANGE.formatted_high_amount in result


class TestDiscountedPrice:
    def test_compact_shows_original_and_sale_amount(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert DISCOUNTED.formatted_amount in result
        assert DISCOUNTED.formatted_sale_amount in result

    def test_compact_has_sr_only_original_price_label(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert "sr-only" in result
        assert "Original price:" in result

    def test_compact_has_sr_only_now_label(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert "Now:" in result

    def test_compact_original_amount_is_struck_through(self) -> None:
        result = _render('<c-course-price :price="price" />', DISCOUNTED)
        assert "<s" in result

    def test_full_shows_tax_note_when_set(self) -> None:
        priced = CoursePrice(
            kind="discounted",
            currency="ZAR",
            amount=Decimal("1499.00"),
            sale_amount=Decimal("999.00"),
            tax_note="incl. VAT",
        )
        result = _render('<c-course-price :price="price" variant="full" />', priced)
        assert "incl. VAT" in result


class TestOnRequestPrice:
    def test_compact_shows_price_on_request(self) -> None:
        result = _render('<c-course-price :price="price" />', ON_REQUEST)
        assert "Price on request" in result

    def test_full_shows_price_on_request(self) -> None:
        result = _render('<c-course-price :price="price" variant="full" />', ON_REQUEST)
        assert "Price on request" in result


class TestFormattingLocale:
    def test_en_za_locale_formats_zar_with_comma_decimal(self) -> None:
        with override_settings(PRICE_LOCALE="en_ZA"):
            price = CoursePrice(kind="fixed", currency="ZAR", amount=Decimal("1499.00"))
            result = _render('<c-course-price :price="price" />', price)

        normalised = result.replace("\xa0", " ")
        assert "R1 499,00" in normalised
