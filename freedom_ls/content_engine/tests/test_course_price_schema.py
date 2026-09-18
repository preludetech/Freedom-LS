"""Tests for the `price:` frontmatter field on the Course content schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from django.test import override_settings

from freedom_ls.content_engine.schema import (
    DiscountedPrice,
    FixedPrice,
    OnRequestPrice,
    RangePrice,
)
from freedom_ls.content_engine.validate import parse_single_file

# ---------------------------------------------------------------------------
# Each kind parses from YAML frontmatter
# ---------------------------------------------------------------------------


def test_fixed_price_parses_from_frontmatter(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Fixed Price Course
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert isinstance(item.price, FixedPrice)
    assert item.price.kind == "fixed"
    assert item.price.amount == Decimal("1499.00")
    assert item.price.currency == "ZAR"


def test_range_price_parses_from_frontmatter(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Range Price Course
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert isinstance(item.price, RangePrice)
    assert item.price.low_amount == Decimal("1200.00")
    assert item.price.high_amount == Decimal("3000.00")


def test_discounted_price_parses_from_frontmatter(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Discounted Price Course
price:
  kind: discounted
  amount: "1499.00"
  sale_amount: "999.00"
  sale_ends_on: 2026-12-31
  currency: ZAR
  tax_note: incl. VAT
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert isinstance(item.price, DiscountedPrice)
    assert item.price.sale_amount == Decimal("999.00")
    assert item.price.sale_ends_on == date(2026, 12, 31)
    assert item.price.tax_note == "incl. VAT"


def test_on_request_price_parses_from_frontmatter(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: On Request Price Course
price:
  kind: on_request
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert isinstance(item.price, OnRequestPrice)
    assert item.price.kind == "on_request"


def test_absent_price_key_is_none(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: No Price Course
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert item.price is None


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------


def test_bare_number_amount_is_rejected(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Unquoted Amount Course
price:
  kind: fixed
  amount: 1499.00
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="write amounts as quoted strings"):
        parse_single_file(temp_file)


def test_unknown_kind_gives_union_tag_invalid(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Unknown Kind Course
price:
  kind: subscription
  amount: "1499.00"
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="Validation failed") as excinfo:
        parse_single_file(temp_file)

    cause = excinfo.value.__cause__
    assert isinstance(cause, ValidationError)
    assert any(error["type"] == "union_tag_invalid" for error in cause.errors())


def test_extra_key_on_a_kind_is_rejected(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Extra Key Course
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
  frobnicate: true
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="Validation failed"):
        parse_single_file(temp_file)


def test_currency_on_on_request_is_rejected(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: On Request With Currency Course
price:
  kind: on_request
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="Validation failed"):
        parse_single_file(temp_file)


@override_settings(DEFAULT_CURRENCY=None)
def test_decimal_places_check_is_skipped_with_no_currency_and_no_default(
    make_temp_file,
) -> None:
    """An amount with three decimal places and no currency anywhere passes.

    `price_errors` only checks decimal places against a currency it can look
    up the precision for; with no `currency:` and `DEFAULT_CURRENCY` unset,
    that half of the rule is skipped.
    """
    content = """---
content_type: COURSE
title: No Currency Course
price:
  kind: fixed
  amount: "1499.123"
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert item.price.amount == Decimal("1499.123")


@override_settings(DEFAULT_CURRENCY="JPY")
def test_decimal_places_check_uses_the_default_currency_when_absent(
    make_temp_file,
) -> None:
    """A JPY amount with a fractional yen fails even though `currency:` is absent."""
    content = """---
content_type: COURSE
title: Default Currency Course
price:
  kind: fixed
  amount: "1500.50"
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="more decimal places"):
        parse_single_file(temp_file)


def test_amount_too_large_for_the_column_fails_validation(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Too Large Course
price:
  kind: fixed
  amount: "1000000000"
  currency: IDR
---
"""
    temp_file = make_temp_file(".md", content)

    with pytest.raises(ValueError, match="amount is too large"):
        parse_single_file(temp_file)
