"""Tests for the course_applications app's declared settings."""

from __future__ import annotations

import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.config import config


def test_start_limit_reads_the_projects_value(settings) -> None:
    settings.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT = 3

    assert config.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT == 3


def test_start_window_reads_the_projects_value(settings) -> None:
    settings.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS = 60

    assert config.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS == 60


def test_start_settings_are_declared() -> None:
    assert {
        "COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT",
        "COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS",
    } <= set(config.declared_settings)
