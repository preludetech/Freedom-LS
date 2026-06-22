"""Tests for the course_access Django system check."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.content_engine.factories import CourseFactory

DEFAULT_BACKEND = "freedom_ls.course_access.backends.DefaultCourseAccessBackend"


@pytest.mark.django_db
class TestCourseAccessSystemCheck:
    """The Django system check surfaces bad access_config."""

    @override_settings(COURSE_ACCESS_BACKEND=DEFAULT_BACKEND)
    def test_valid_config_produces_no_errors(self, mock_site_context):
        from freedom_ls.course_access.checks import check_course_access_configs

        CourseFactory(access_config={"access_type": "free"})
        errors = check_course_access_configs(app_configs=None)
        assert errors == []

    @override_settings(COURSE_ACCESS_BACKEND=DEFAULT_BACKEND)
    def test_empty_config_produces_no_errors(self, mock_site_context):
        from freedom_ls.course_access.checks import check_course_access_configs

        CourseFactory(access_config={})
        errors = check_course_access_configs(app_configs=None)
        assert errors == []

    @override_settings(COURSE_ACCESS_BACKEND=DEFAULT_BACKEND)
    def test_bad_access_config_produces_error(self, mock_site_context):
        """A Course with invalid access_config set directly (bypassing validation) produces an error."""
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.checks import check_course_access_configs

        course = CourseFactory()
        # Bypass load-time validation by using .objects.update()
        Course.objects.filter(pk=course.pk).update(
            access_config={"access_type": "application_gated"}
        )
        errors = check_course_access_configs(app_configs=None)
        assert len(errors) >= 1

    @override_settings(COURSE_ACCESS_BACKEND=DEFAULT_BACKEND)
    def test_error_includes_course_slug(self, mock_site_context):
        """Error message names the offending course slug."""
        from freedom_ls.content_engine.models import Course
        from freedom_ls.course_access.checks import check_course_access_configs

        course = CourseFactory(slug="bad-course")
        Course.objects.filter(pk=course.pk).update(
            access_config={"access_type": "unknown_type"}
        )
        errors = check_course_access_configs(app_configs=None)
        assert any("bad-course" in str(e) for e in errors)
