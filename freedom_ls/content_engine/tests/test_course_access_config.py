"""Tests for the Course.access_config model field and its schema counterpart."""

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.schema import Course as CourseSchema

# ---------------------------------------------------------------------------
# Model field: access_config
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_access_config_defaults_to_empty_dict(mock_site_context):
    """A newly created Course has access_config == {}."""
    course = CourseFactory()
    course.refresh_from_db()
    assert course.access_config == {}


# ---------------------------------------------------------------------------
# Pydantic schema field: access_config
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
