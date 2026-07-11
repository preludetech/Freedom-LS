"""Tests for the course_access Django system check."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.content_engine.factories import CourseFactory

DEFAULT_BACKEND = "freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend"


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

    @override_settings(COURSE_ACCESS_BACKEND="")
    def test_unset_backend_reports_required_setting_error(self, mock_site_context):
        """An unset COURSE_ACCESS_BACKEND reports a clear E001 instead of crashing."""
        from freedom_ls.course_access.checks import check_course_access_configs

        errors = check_course_access_configs(app_configs=None)
        assert len(errors) == 1
        assert errors[0].id == "freedom_ls_course_access.E001"
        assert "COURSE_ACCESS_BACKEND" in errors[0].msg


class TestPreviewOverridesDisabledInProductionCheck:
    """W001: warn when a preview override is left on outside DEBUG."""

    @override_settings(
        DEBUG=False,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True,
        OVERRIDE_COURSE_ACCESS_TO_FREE=False,
    )
    def test_fires_when_visibility_override_on_and_debug_false(self):
        from freedom_ls.course_access.checks import (
            check_preview_overrides_disabled_in_production,
        )

        warnings = check_preview_overrides_disabled_in_production(app_configs=None)

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_course_access.W001"
        assert "OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE" in warnings[0].msg

    @override_settings(
        DEBUG=False,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
        OVERRIDE_COURSE_ACCESS_TO_FREE=True,
    )
    def test_fires_when_access_override_on_and_debug_false(self):
        from freedom_ls.course_access.checks import (
            check_preview_overrides_disabled_in_production,
        )

        warnings = check_preview_overrides_disabled_in_production(app_configs=None)

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_course_access.W001"
        assert "OVERRIDE_COURSE_ACCESS_TO_FREE" in warnings[0].msg

    @override_settings(
        DEBUG=False,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True,
        OVERRIDE_COURSE_ACCESS_TO_FREE=True,
    )
    def test_fires_once_listing_both_names_when_both_overrides_on(self):
        from freedom_ls.course_access.checks import (
            check_preview_overrides_disabled_in_production,
        )

        warnings = check_preview_overrides_disabled_in_production(app_configs=None)

        assert len(warnings) == 1
        assert "OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE" in warnings[0].msg
        assert "OVERRIDE_COURSE_ACCESS_TO_FREE" in warnings[0].msg

    @override_settings(
        DEBUG=True,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True,
        OVERRIDE_COURSE_ACCESS_TO_FREE=True,
    )
    def test_silent_when_debug_true_even_with_overrides_on(self):
        from freedom_ls.course_access.checks import (
            check_preview_overrides_disabled_in_production,
        )

        warnings = check_preview_overrides_disabled_in_production(app_configs=None)

        assert warnings == []

    @override_settings(
        DEBUG=False,
        OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False,
        OVERRIDE_COURSE_ACCESS_TO_FREE=False,
    )
    def test_silent_when_both_overrides_off(self):
        from freedom_ls.course_access.checks import (
            check_preview_overrides_disabled_in_production,
        )

        warnings = check_preview_overrides_disabled_in_production(app_configs=None)

        assert warnings == []
