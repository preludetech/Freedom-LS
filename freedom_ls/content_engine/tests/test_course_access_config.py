"""Tests for Course.access_config field (Task A.1) and schema field (Task A.2).

TDD — written before implementation.

A.1: Model field round-trip.
A.2: Pydantic schema field pass-through.
"""

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.schema import Course as CourseSchema

# ---------------------------------------------------------------------------
# A.1 — Model field: access_config
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_access_config_defaults_to_empty_dict(mock_site_context):
    """A newly created Course has access_config == {}."""
    course = CourseFactory()
    course.refresh_from_db()
    assert course.access_config == {}


@pytest.mark.django_db
def test_course_access_config_persists_value(mock_site_context):
    """A Course saved with an access_config dict persists it correctly."""
    config = {"access_type": "free"}
    course = CourseFactory(access_config=config)
    course.refresh_from_db()
    assert course.access_config == config


# ---------------------------------------------------------------------------
# A.2 — Pydantic schema field: access_config
# ---------------------------------------------------------------------------


def test_course_schema_access_config_defaults_to_none():
    """Course schema access_config defaults to None when absent."""
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Test Course",
        }
    )
    assert schema.access_config is None


def test_course_schema_access_config_accepts_dict():
    """Course schema access_config accepts and stores a dict value."""
    config = {"access_type": "free"}
    schema = CourseSchema.model_validate(
        {
            "content_type": "COURSE",
            "file_path": "test/course.yaml",
            "title": "Test Course",
            "access_config": config,
        }
    )
    assert schema.access_config == config
