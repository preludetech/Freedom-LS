"""The authored COURSE_CATEGORIES declaration and the Course schema's two replacement keys."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from freedom_ls.content_engine.schema import (
    Course,
    CourseCategories,
    CourseCategoryEntry,
)


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
