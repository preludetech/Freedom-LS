"""Tests for the `price:` frontmatter field going through `save_course`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from django.test import override_settings

from freedom_ls.content_engine.management.commands.content_save import save_course
from freedom_ls.content_engine.models import Course, PriceKind
from freedom_ls.content_engine.validate import parse_single_file


def _save(make_temp_file, mock_site_context, content: str) -> Course:
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)
    return cast(Course, Course.objects.get(site=mock_site_context, title=item.title))


# ---------------------------------------------------------------------------
# Each kind saves
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fixed_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Fixed Price Save Course
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_range_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Range Price Save Course
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("1200.00")
    assert course.price_high_amount == Decimal("3000.00")


@pytest.mark.django_db
def test_discounted_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Discounted Price Save Course
price:
  kind: discounted
  amount: "1499.00"
  sale_amount: "999.00"
  sale_ends_on: 2026-12-31
  currency: ZAR
  tax_note: incl. VAT
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.DISCOUNTED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_sale_amount == Decimal("999.00")
    assert course.price_sale_ends_on == date(2026, 12, 31)
    assert course.price_tax_note == "incl. VAT"


@pytest.mark.django_db
def test_on_request_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: On Request Price Save Course
price:
  kind: on_request
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.ON_REQUEST
    assert course.price_currency == ""


# ---------------------------------------------------------------------------
# Switching kind clears stale columns
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_switching_from_range_to_fixed_clears_low_and_high_amounts(
    make_temp_file, mock_site_context
) -> None:
    range_content = """---
content_type: COURSE
title: Switching Kind Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000010
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", range_content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="Switching Kind Course")
    assert course.price_low_amount == Decimal("1200.00")

    fixed_content = """---
content_type: COURSE
title: Switching Kind Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000010
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
---
"""
    temp_file_2 = make_temp_file(".md", fixed_content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_low_amount is None
    assert course.price_high_amount is None


# ---------------------------------------------------------------------------
# Absent price: leaves the stored value; `price: null` clears it
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_absent_price_key_keeps_an_admin_set_price(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: No Price Key Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000011
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="No Price Key Course")
    course.price_kind = PriceKind.FIXED
    course.price_amount = Decimal("500.00")
    course.price_currency = "ZAR"
    course.save()

    temp_file_2 = make_temp_file(".md", content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("500.00")


@pytest.mark.django_db
def test_explicit_null_price_clears_all_eight_columns(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: Null Price Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000012
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="Null Price Course")
    course.price_kind = PriceKind.FIXED
    course.price_amount = Decimal("500.00")
    course.price_currency = "ZAR"
    course.save()

    null_price_content = """---
content_type: COURSE
title: Null Price Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000012
price: null
---
"""
    temp_file_2 = make_temp_file(".md", null_price_content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == ""
    assert course.price_amount is None
    assert course.price_sale_amount is None
    assert course.price_sale_ends_on is None
    assert course.price_low_amount is None
    assert course.price_high_amount is None
    assert course.price_currency == ""
    assert course.price_tax_note == ""


# ---------------------------------------------------------------------------
# Currency resolution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_blank_currency_takes_default_currency(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: Default Currency Save Course
price:
  kind: fixed
  amount: "1499.00"
---
"""
    with override_settings(DEFAULT_CURRENCY="ZAR"):
        course = _save(make_temp_file, mock_site_context, content)

    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_missing_currency_with_no_default_raises_naming_the_file(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: No Currency No Default Course
price:
  kind: fixed
  amount: "1499.00"
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    with (
        override_settings(DEFAULT_CURRENCY=None),
        pytest.raises(ValueError, match="DEFAULT_CURRENCY is not set") as excinfo,
    ):
        save_course(item, mock_site_context, temp_file.parent)

    assert str(temp_file) in str(excinfo.value)
