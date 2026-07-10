"""Tests for course_access per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.course_access.config import CourseAccessConfig


def test_override_course_visibility_to_visible_defaults_to_false_when_unset() -> None:
    config = CourseAccessConfig()

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=None):
        assert config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE is False


def test_override_course_visibility_to_visible_reads_true_when_set() -> None:
    config = CourseAccessConfig()

    with override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True):
        assert config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE is True


def test_override_course_access_to_free_defaults_to_false_when_unset() -> None:
    config = CourseAccessConfig()

    with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=None):
        assert config.OVERRIDE_COURSE_ACCESS_TO_FREE is False


def test_override_course_access_to_free_reads_true_when_set() -> None:
    config = CourseAccessConfig()

    with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=True):
        assert config.OVERRIDE_COURSE_ACCESS_TO_FREE is True
