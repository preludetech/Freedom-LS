"""Tests for markdown_rendering per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.markdown_rendering.config import MarkdownRenderingConfig


def test_markdown_allowed_tags_defaults_to_empty_dict_when_unset() -> None:
    """Unset MARKDOWN_ALLOWED_TAGS degrades to {} — render stays safe (nh3 base allowlist)."""
    config = MarkdownRenderingConfig()

    with override_settings(MARKDOWN_ALLOWED_TAGS=None):
        assert config.MARKDOWN_ALLOWED_TAGS == {}
