"""Tests for the content schemas that validate authored markdown and YAML."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from django.test import override_settings
from django.utils.text import slugify as django_slugify

from freedom_ls.content_engine.schema import (
    Article,
    Course,
    CourseCategories,
    CourseCategoryEntry,
    DiscountedPrice,
    FixedPrice,
    OnRequestPrice,
    RangePrice,
    slugify,
)
from freedom_ls.content_engine.validate import parse_single_file

# Validation of the ARTICLE schema: slug derivation and rejected fields.


def _article(file_path: str, **overrides: object) -> Article:
    fields: dict[str, object] = {
        "content_type": "ARTICLE",
        "title": "My Article",
        "published_on": date(2026, 1, 2),
        "file_path": Path(file_path),
    }
    fields.update(overrides)
    return Article.model_validate(fields)


def test_slug_defaults_to_the_file_stem():
    article = _article("blog/1. My Article.md")

    assert article.slug == "1-my-article"


def test_slug_defaults_to_the_parent_directory_for_content_md():
    article = _article("blog/Launch Day/content.md")

    assert article.slug == "launch-day"


def test_a_written_slug_is_kept():
    article = _article("blog/whatever.md", slug="kept_slug")

    assert article.slug == "kept_slug"


def test_a_written_bad_slug_is_rejected_naming_the_file():
    with pytest.raises(ValidationError, match=r"blog/bad\.md"):
        _article("blog/bad.md", slug="bad slug!")


def test_a_written_bad_slug_error_is_located_at_the_slug_field():
    with pytest.raises(ValidationError) as excinfo:
        _article("blog/bad.md", slug="bad slug!")

    assert excinfo.value.errors()[0]["loc"] == ("slug",)


def test_a_derived_empty_slug_is_rejected_naming_the_file():
    with pytest.raises(ValidationError, match=r"blog/!!!\.md"):
        _article("blog/!!!.md")


def test_published_on_is_required():
    with pytest.raises(ValidationError, match="published_on"):
        Article.model_validate(
            {
                "content_type": "ARTICLE",
                "title": "No date",
                "file_path": Path("blog/no-date.md"),
            }
        )


def test_coming_soon_visibility_is_rejected_naming_the_allowed_values():
    with pytest.raises(ValidationError, match=r"published.*hidden"):
        _article("blog/soon.md", visibility="coming_soon")


def test_category_is_rejected_with_the_article_message():
    with pytest.raises(ValidationError, match="'category' is not an article field"):
        _article("blog/x.md", category="something")


def test_image_with_alt_text_is_accepted():
    article = _article("blog/x.md", image="photo.png", image_alt="A grey square")

    assert (article.image, article.image_alt) == ("photo.png", "A grey square")


def test_image_without_alt_text_is_rejected_naming_the_file():
    with pytest.raises(
        ValidationError, match=r"blog/x\.md has an image but no image_alt"
    ):
        _article("blog/x.md", image="photo.png")


def test_empty_alt_text_marks_the_image_decorative_and_is_accepted():
    article = _article("blog/x.md", image="photo.png", image_alt="")

    assert article.image_alt == ""


def test_empty_image_needs_no_alt_text():
    article = _article("blog/x.md", image="")

    assert not article.image


@pytest.mark.parametrize(
    "value",
    [
        "1. My Article",
        "Hello, World!",
        "  Spaced  out  ",
        "Café Déjà Vu",
        "a_b-c",
        "!!!",
    ],
)
def test_slugify_matches_djangos(value: str):
    assert slugify(value) == django_slugify(value, allow_unicode=True)


def test_slugify_numbered_title():
    assert slugify("1. My Article") == "1-my-article"


# The authored COURSE_CATEGORIES declaration and the Course schema's two replacement keys.


def _course_categories(**overrides):
    data = {
        "content_type": "COURSE_CATEGORIES",
        "file_path": Path("course_categories.yaml"),
        "categories": [
            {
                "slug": "start-here",
                "title": "Start here",
                "description": "New? Begin with these.",
                "show_on_dashboard": True,
            },
            {
                "slug": "technical",
                "title": "Technical",
                "description": "Hands-on, tool-specific courses.",
            },
        ],
    }
    data.update(overrides)
    return data


def _course(**overrides):
    data = {
        "content_type": "COURSE",
        "file_path": Path("courses/demo/course.md"),
        "title": "Demo course",
    }
    data.update(overrides)
    return data


def test_course_categories_declaration_validates():
    declaration = CourseCategories.model_validate(_course_categories())

    assert [entry.slug for entry in declaration.categories] == [
        "start-here",
        "technical",
    ]


def test_show_on_dashboard_defaults_to_true():
    declaration = CourseCategories.model_validate(_course_categories())

    assert declaration.categories[1].show_on_dashboard is True


def test_course_single_category_shorthand_validates():
    course = Course.model_validate(_course(categories=["technical"]))

    assert course.categories == ["technical"]
    assert course.dashboard_category is None


def test_course_multiple_categories_with_explicit_dashboard_category_validates():
    course = Course.model_validate(
        _course(categories=["technical", "start-here"], dashboard_category="technical")
    )

    assert course.categories == ["technical", "start-here"]
    assert course.dashboard_category == "technical"


def test_retired_category_key_fails_naming_both_replacements():
    with pytest.raises(ValidationError) as exc_info:
        Course.model_validate(_course(category="Technical"))

    message = str(exc_info.value)
    assert "categories" in message
    assert "dashboard_category" in message
    assert "Field: category" in message or "category" in message


def test_duplicate_slug_fails_naming_slug_and_file():
    categories = _course_categories()
    categories["categories"].append({"slug": "start-here", "title": "Start here again"})

    with pytest.raises(ValueError, match="start-here") as exc_info:
        CourseCategories.model_validate(categories)

    assert "course_categories.yaml" in str(exc_info.value)


def test_duplicate_uuid_fails_naming_uuid_and_both_slugs():
    categories = _course_categories()
    shared_uuid = "5c1f0a3e-7c2b-4a91-9f0d-2d6a1b83e4c7"
    categories["categories"][0]["uuid"] = shared_uuid
    categories["categories"][1]["uuid"] = shared_uuid

    with pytest.raises(ValidationError) as exc_info:
        CourseCategories.model_validate(categories)

    message = str(exc_info.value)
    assert shared_uuid in message
    assert "start-here" in message
    assert "technical" in message


def test_invalid_slug_fails_naming_slug_and_file():
    categories = _course_categories()
    categories["categories"][0]["slug"] = "bad slug!"

    with pytest.raises(ValidationError) as exc_info:
        CourseCategories.model_validate(categories)

    message = str(exc_info.value)
    assert "bad slug!" in message
    assert "course_categories.yaml" in message


def test_reserved_slug_fails_naming_slug_and_reserved_set():
    categories = _course_categories()
    categories["categories"][0]["slug"] = "available"

    with pytest.raises(ValidationError) as exc_info:
        CourseCategories.model_validate(categories)

    message = str(exc_info.value)
    assert "available" in message
    assert "recommended" in message  # part of the reserved set listed


def test_resolve_dashboard_category_returns_explicit_value():
    course = Course.model_validate(
        _course(categories=["technical", "start-here"], dashboard_category="technical")
    )

    assert course.resolve_dashboard_category() == "technical"


def test_resolve_dashboard_category_resolves_single_entry_shorthand():
    course = Course.model_validate(_course(categories=["technical"]))

    assert course.resolve_dashboard_category() == "technical"


def test_resolve_dashboard_category_is_none_with_no_categories():
    course = Course.model_validate(_course())

    assert course.resolve_dashboard_category() is None


def test_resolve_dashboard_category_is_none_with_multiple_categories_and_no_explicit_choice():
    course = Course.model_validate(_course(categories=["technical", "start-here"]))

    assert course.resolve_dashboard_category() is None


def test_course_categories_entry_forbids_unknown_keys():
    with pytest.raises(ValidationError):
        CourseCategoryEntry.model_validate(
            {"slug": "technical", "title": "Technical", "unexpected": "oops"}
        )


# Tests for the `price:` frontmatter field on the Course content schema.


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


def test_open_ended_range_price_parses_from_frontmatter(make_temp_file) -> None:
    content = """---
content_type: COURSE
title: Open Range Price Course
price:
  kind: range
  low_amount: "500.00"
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    assert isinstance(item.price, RangePrice)
    assert item.price.low_amount == Decimal("500.00")
    assert item.price.high_amount is None


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

    with pytest.raises(ValueError, match="amount: Too large"):
        parse_single_file(temp_file)


# A course names the form its applicants fill in inside its `access_config`, as a
# path relative to its own `course.md`. The schema carries the config through
# untouched; the access backend validates the key and the loader resolves the path.


def _course_data(**extra: object) -> dict[str, object]:
    return {
        "content_type": "COURSE",
        "file_path": "courses/data-science/course.md",
        "title": "Data science",
        **extra,
    }


def test_a_course_may_name_an_application_form():
    course = Course.model_validate(
        _course_data(
            access_config={
                "access_type": "application_gated",
                "application_form": "../forms/application/form.md",
            }
        )
    )

    assert course.access_config == {
        "access_type": "application_gated",
        "application_form": "../forms/application/form.md",
    }


def test_a_course_need_not_name_an_application_form():
    course = Course.model_validate(_course_data())

    assert course.access_config is None


def test_a_top_level_application_form_is_refused():
    """The key belongs under access_config. `extra="forbid"` is what stops the
    older top-level spelling being silently ignored.
    """
    with pytest.raises(ValidationError):
        Course.model_validate(_course_data(application_form="../forms/form.md"))


def test_an_unknown_key_is_still_refused():
    """`extra="forbid"` is what turns an author's typo into a load failure rather
    than a silently ignored line.
    """
    with pytest.raises(ValidationError):
        Course.model_validate(_course_data(aplication_form="../forms/form.md"))


# Course.access_config on the content schema.


def test_course_schema_access_config_defaults_to_none():
    """Course schema access_config defaults to None when absent."""
    schema = Course.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Test Course",
        }
    )
    assert schema.access_config is None
