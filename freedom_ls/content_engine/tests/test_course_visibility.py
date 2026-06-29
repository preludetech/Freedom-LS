"""Tests for CourseVisibility enum and the visibility field on Course.

TDD: these tests are written before the implementation.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility


@pytest.mark.django_db
class TestCourseVisibilityDefault:
    """A new Course defaults to PUBLISHED."""

    def test_new_course_defaults_to_published(self, mock_site_context):
        """A Course created without specifying visibility defaults to PUBLISHED."""
        course = CourseFactory()
        assert course.visibility == CourseVisibility.PUBLISHED

    def test_default_is_published_string_value(self, mock_site_context):
        """The default visibility string value is 'published'."""
        course = CourseFactory()
        assert course.visibility == "published"


@pytest.mark.django_db
class TestCourseVisibilityRoundTrip:
    """All three visibility values survive a DB round-trip."""

    def test_published_round_trips(self, mock_site_context):
        """PUBLISHED visibility is saved and retrieved correctly."""
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)
        course.refresh_from_db()
        assert course.visibility == CourseVisibility.PUBLISHED

    def test_coming_soon_round_trips(self, mock_site_context):
        """COMING_SOON visibility is saved and retrieved correctly."""
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        course.refresh_from_db()
        assert course.visibility == CourseVisibility.COMING_SOON

    def test_hidden_round_trips(self, mock_site_context):
        """HIDDEN visibility is saved and retrieved correctly."""
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        course.refresh_from_db()
        assert course.visibility == CourseVisibility.HIDDEN


@pytest.mark.django_db
class TestCourseVisibilityBackfillGuarantee:
    """Rows that do not specify visibility end up as PUBLISHED (migration backfill guarantee)."""

    def test_course_without_visibility_kwarg_is_published(self, mock_site_context):
        """A Course created without the visibility kwarg (simulating a pre-migration row)
        ends up with visibility == PUBLISHED via the model/DB default.
        """
        # Simulate a pre-migration row: create via factory without visibility arg,
        # then verify the DB column contains 'published'.
        course = CourseFactory()
        db_value = (
            Course.objects.filter(pk=course.pk)
            .values_list("visibility", flat=True)
            .get()
        )
        assert db_value == "published"
