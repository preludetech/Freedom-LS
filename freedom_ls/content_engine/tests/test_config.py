"""Tests for content_engine per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.content_engine.config import config

# Tests for content_engine per-app config defaults.


def test_content_media_storage_alias_defaults_to_course_media_when_unset() -> None:
    with override_settings(CONTENT_MEDIA_STORAGE_ALIAS=None):
        assert config.CONTENT_MEDIA_STORAGE_ALIAS == "course_media"


def test_content_media_storage_alias_reads_project_override() -> None:
    with override_settings(CONTENT_MEDIA_STORAGE_ALIAS="courseware"):
        assert config.CONTENT_MEDIA_STORAGE_ALIAS == "courseware"


def test_article_byline_settings_default_to_shown() -> None:
    assert config.ARTICLE_SHOW_DATE is True
    assert config.ARTICLE_SHOW_AUTHOR is True


def test_article_byline_settings_read_project_override() -> None:
    with override_settings(ARTICLE_SHOW_DATE=False, ARTICLE_SHOW_AUTHOR=False):
        assert config.ARTICLE_SHOW_DATE is False
        assert config.ARTICLE_SHOW_AUTHOR is False
