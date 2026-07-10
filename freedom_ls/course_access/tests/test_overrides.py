"""Tests for the shared course-access override-reading helpers."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_access.overrides import (
    is_coming_soon_for_display,
    override_access_to_free,
    override_visibility_to_visible,
)


def test_override_visibility_to_visible_false_when_setting_off() -> None:
    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=False):
        assert override_visibility_to_visible() is False


def test_override_visibility_to_visible_true_when_setting_on() -> None:
    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        assert override_visibility_to_visible() is True


def test_override_access_to_free_false_when_setting_off() -> None:
    with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=False):
        assert override_access_to_free() is False


def test_override_access_to_free_true_when_setting_on() -> None:
    with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=True):
        assert override_access_to_free() is True


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
