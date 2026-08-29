"""Tests for the shared course-access override-reading helpers."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_access.overrides import (
    is_coming_soon_for_display,
)


@pytest.mark.django_db
class TestIsComingSoonForDisplay:
    def test_true_for_coming_soon_course_when_override_off(
        self, mock_site_context
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            assert is_coming_soon_for_display(course) is True

    def test_false_for_coming_soon_course_when_override_on(
        self, mock_site_context
    ) -> None:
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
            assert is_coming_soon_for_display(course) is False

    def test_false_for_published_course(self, mock_site_context) -> None:
        course = CourseFactory(visibility=CourseVisibility.PUBLISHED)

        with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
            assert is_coming_soon_for_display(course) is False
