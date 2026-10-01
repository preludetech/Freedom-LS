"""Tests for the article cotton widgets rendered through markdown."""

from __future__ import annotations

from typing import cast

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.content_engine.factories import ArticleFactory, TopicFactory
from freedom_ls.content_engine.models import ArticleVisibility, Topic
from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.blog"):
    pytest.skip("blog not installed", allow_module_level=True)


def _render(body: str, topic: Topic) -> str:
    return str(render_markdown(body, None, context={"content_instance": topic}))


@pytest.fixture
def source_topic(mock_site_context) -> Topic:
    return cast("Topic", TopicFactory(file_path="2. topic/content.md"))


@pytest.mark.django_db
class TestArticleLink:
    def test_published_target_links_around_the_slot_text(
        self, source_topic: Topic
    ) -> None:
        article = ArticleFactory(slug="target", file_path="articles/target.md")
        url = reverse("blog:article_detail", args=[article.slug])

        result = _render(
            '<c-article-link path="../articles/target.md">read this</c-article-link>',
            source_topic,
        )

        assert f'<a href="{url}">read this</a>' in result

    def test_empty_slot_links_around_the_article_title(
        self, source_topic: Topic
    ) -> None:
        article = ArticleFactory(
            title="The Target Title", slug="target", file_path="articles/target.md"
        )
        url = reverse("blog:article_detail", args=[article.slug])

        result = _render(
            '<c-article-link path="../articles/target.md"></c-article-link>',
            source_topic,
        )

        assert f'<a href="{url}">The Target Title</a>' in result

    def test_hidden_target_renders_plain_text_without_its_title(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(
            title="Secret Title",
            slug="target",
            file_path="articles/target.md",
            visibility=ArticleVisibility.HIDDEN,
        )

        result = _render(
            '<c-article-link path="../articles/target.md">plain words</c-article-link>',
            source_topic,
        )

        assert "plain words" in result
        assert "<a " not in result
        assert "Secret Title" not in result

    def test_hidden_target_with_empty_slot_renders_nothing_and_no_title(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(
            title="Secret Title",
            slug="target",
            file_path="articles/target.md",
            visibility=ArticleVisibility.HIDDEN,
        )

        result = _render(
            'before <c-article-link path="../articles/target.md"></c-article-link> after',
            source_topic,
        )

        assert "before" in result
        assert "Secret Title" not in result
        assert "<a " not in result

    def test_missing_target_renders_plain_text(self, source_topic: Topic) -> None:
        result = _render(
            '<c-article-link path="../articles/nope.md">fallback text</c-article-link>',
            source_topic,
        )

        assert "fallback text" in result
        assert "<a " not in result

    def test_blog_urls_absent_renders_plain_text(self, source_topic: Topic) -> None:
        ArticleFactory(
            title="Target Title", slug="target", file_path="articles/target.md"
        )

        with override_settings(
            ROOT_URLCONF="freedom_ls.content_engine.tests.no_blog_urls"
        ):
            result = _render(
                '<c-article-link path="../articles/target.md">plain words</c-article-link>',
                source_topic,
            )

        assert "plain words" in result
        assert "<a " not in result
        assert "Target Title" not in result
