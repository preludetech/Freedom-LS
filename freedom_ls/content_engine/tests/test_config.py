"""Tests for content_engine per-app config defaults."""

from __future__ import annotations

from freedom_ls.content_engine.config import config


def test_content_media_storage_alias_defaults_to_course_media() -> None:
    assert config.CONTENT_MEDIA_STORAGE_ALIAS == "course_media"
