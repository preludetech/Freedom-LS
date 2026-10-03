"""Tests for blog per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.blog.config import config


def test_blog_name_defaults_to_articles() -> None:
    assert config.BLOG_NAME == "Articles"


def test_blog_name_reads_project_override() -> None:
    with override_settings(BLOG_NAME="Posts"):
        assert config.BLOG_NAME == "Posts"
