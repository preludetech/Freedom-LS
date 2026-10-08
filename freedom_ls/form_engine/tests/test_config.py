"""Tests for the form_engine app's declared settings."""

from __future__ import annotations

from freedom_ls.form_engine.config import config


def test_upload_limit_reads_the_projects_value(settings) -> None:
    settings.FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT = 3

    assert config.FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT == 3


def test_upload_window_reads_the_projects_value(settings) -> None:
    settings.FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS = 60

    assert config.FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS == 60


def test_upload_settings_are_declared() -> None:
    assert {
        "FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT",
        "FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS",
    } <= set(config.declared_settings)
