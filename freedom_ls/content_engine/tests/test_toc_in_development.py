"""Tests for the Course.table_of_contents_in_development flag."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.schema import Course as CourseSchema

# ---------------------------------------------------------------------------
# Pydantic schema field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("visibility", ["published", "coming_soon", "hidden"])
def test_schema_flag_true_is_valid_for_every_visibility(visibility: str) -> None:
    """The flag composes freely with every visibility state."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "In Development",
            "visibility": visibility,
            "table_of_contents_in_development": True,
        }
    )
    assert schema.table_of_contents_in_development is True


def test_schema_flag_true_is_valid_with_default_visibility() -> None:
    """Omitting visibility defaults to published, which still accepts the flag.

    This is the application-gated case: applications are open while the
    course's contents are still being written.
    """
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Open For Applications",
            "access_config": {"access_type": "application_gated"},
            "table_of_contents_in_development": True,
        }
    )
    assert schema.visibility == "published"
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
    """A published course carrying the flag saves without error.

    Visibility is omitted so it defaults to published -- the shape that used
    to be rejected at load time.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "in_development_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text(
            """---
content_type: COURSE
title: In Development Course
table_of_contents_in_development: true
uuid: 00000000-0000-0000-0000-000000000030
---

Body
"""
        )

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="In Development Course", site=site)
        assert course.table_of_contents_in_development is True
