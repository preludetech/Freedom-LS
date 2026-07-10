"""Tests for the Course.table_of_contents_in_development flag."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.schema import Course as CourseSchema

# ---------------------------------------------------------------------------
# Pydantic schema field + validator
# ---------------------------------------------------------------------------


def test_schema_published_with_flag_true_raises() -> None:
    """A published course cannot have table_of_contents_in_development set."""
    with pytest.raises(ValidationError) as excinfo:
        CourseSchema.model_validate(
            {
                "content_type": "COURSE",
                "file_path": "test/course.yaml",
                "title": "Published In Development",
                "visibility": "published",
                "table_of_contents_in_development": True,
            }
        )
    assert "test/course.yaml" in str(excinfo.value)


def test_schema_published_default_visibility_with_flag_true_raises() -> None:
    """Omitting visibility defaults to published, so the flag still raises."""
    with pytest.raises(ValidationError):
        CourseSchema.model_validate(
            {
                "content_type": "COURSE",
                "file_path": "test/course.yaml",
                "title": "Default Visibility In Development",
                "table_of_contents_in_development": True,
            }
        )


@pytest.mark.parametrize("visibility", ["coming_soon", "hidden"])
def test_schema_non_published_with_flag_true_is_valid(visibility: str) -> None:
    """A coming_soon/hidden course may have the flag set."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Non Published In Development",
            "visibility": visibility,
            "table_of_contents_in_development": True,
        }
    )
    assert schema.table_of_contents_in_development is True


def test_schema_flag_defaults_to_false() -> None:
    """table_of_contents_in_development defaults to False when omitted."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Default Flag Course",
        }
    )
    assert schema.table_of_contents_in_development is False


# ---------------------------------------------------------------------------
# Django model field + schema<->model reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_content_save_persists_toc_in_development_flag(site, mock_site_context):
    """A valid non-published course carrying the flag saves without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "in_development_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text(
            """---
content_type: COURSE
title: In Development Course
visibility: coming_soon
table_of_contents_in_development: true
uuid: 00000000-0000-0000-0000-000000000030
---

Body
"""
        )

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="In Development Course", site=site)
        assert course.table_of_contents_in_development is True
