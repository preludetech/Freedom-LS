"""Tests for content_engine per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.content_engine.config import config


def test_content_media_storage_alias_defaults_to_course_media_when_unset() -> None:
    with override_settings(CONTENT_MEDIA_STORAGE_ALIAS=None):
        assert config.CONTENT_MEDIA_STORAGE_ALIAS == "course_media"


def test_content_media_storage_alias_reads_project_override() -> None:
    with override_settings(CONTENT_MEDIA_STORAGE_ALIAS="courseware"):
        assert config.CONTENT_MEDIA_STORAGE_ALIAS == "courseware"
