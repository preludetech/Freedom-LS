"""Tests for the article cotton widgets rendered through markdown."""

from __future__ import annotations

import re
from typing import cast

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
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

    def test_link_adds_no_whitespace_around_itself(self, source_topic: Topic) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        result = _render(
            '(<c-article-link path="../articles/target.md">read this</c-article-link>).',
            source_topic,
        )

        assert "(<a " in result
        assert "read this</a>)." in result

    def test_fallback_text_adds_no_whitespace_around_itself(
        self, source_topic: Topic
    ) -> None:
        result = _render(
            '(<c-article-link path="../articles/nope.md">fallback text</c-article-link>).',
            source_topic,
        )

        assert "(fallback text)." in result


def _card(path: str = "../articles/target.md", variant: str | None = None) -> str:
    variant_attr = f' variant="{variant}"' if variant else ""
    return f'<c-article-card path="{path}"{variant_attr}></c-article-card>'


@pytest.mark.django_db
class TestArticleCard:
    @pytest.mark.parametrize("variant", ["row", "compact", "bogus"])
    def test_variant_renders_title_link_inside_h3_and_description(
        self, source_topic: Topic, variant: str
    ) -> None:
        article = ArticleFactory(
            title="Card Title",
            description="Card description text",
            slug="target",
            file_path="articles/target.md",
        )
        url = reverse("blog:article_detail", args=[article.slug])

        result = _render(_card(variant=variant), source_topic)

        assert re.search(
            rf'<h3>\s*<a href="{url}"[^>]*>\s*Card Title\s*</a>\s*</h3>', result
        )
        assert "Card description text" in result

    def test_unknown_variant_renders_the_same_markup_as_row(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        row = _render(_card(variant="row"), source_topic)
        unknown = _render(_card(variant="bogus"), source_topic)

        assert unknown == row

    def test_compact_markup_differs_from_row(self, source_topic: Topic) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        assert _render(_card(variant="compact"), source_topic) != _render(
            _card(variant="row"), source_topic
        )

    @pytest.mark.parametrize("variant", ["row", "compact"])
    def test_target_with_image_renders_img_and_keeps_one_link(
        self, article_with_image, variant: str
    ) -> None:
        topic = cast("Topic", TopicFactory(file_path="2. topic/content.md"))
        path = "../articles/with-image.md"

        result = _render(_card(path=path, variant=variant), topic)

        assert result.count("<img") == 1
        assert article_with_image.image_file.file.url in result
        assert 'alt="A grey square"' in result
        assert result.count("<a ") == 1

    @pytest.mark.parametrize("variant", ["row", "compact"])
    def test_target_without_image_renders_no_img(
        self, source_topic: Topic, variant: str
    ) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        result = _render(_card(variant=variant), source_topic)

        assert "<img" not in result

    def test_byline_shows_date_and_author_when_enabled(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(
            slug="target",
            file_path="articles/target.md",
            author="Ada Author",
            show_date=True,
            show_author=True,
        )

        result = _render(_card(), source_topic)

        assert "Ada Author" in result
        assert "<time" in result

    def test_byline_omits_date_and_author_when_disabled(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(
            title="Plain Card",
            slug="target",
            file_path="articles/target.md",
            author="Ada Author",
            show_date=False,
            show_author=False,
        )

        result = _render(_card(), source_topic)

        assert "Plain Card" in result
        assert "Ada Author" not in result
        assert "<time" not in result

    def test_hidden_target_renders_nothing(self, source_topic: Topic) -> None:
        ArticleFactory(
            title="Secret Title",
            slug="target",
            file_path="articles/target.md",
            visibility=ArticleVisibility.HIDDEN,
        )

        result = _render(f"before {_card()} after", source_topic)

        assert "before" in result
        assert "Secret Title" not in result
        assert "<article" not in result

    def test_missing_target_renders_nothing(self, source_topic: Topic) -> None:
        result = _render(f"before {_card('../articles/nope.md')} after", source_topic)

        assert "before" in result
        assert "<article" not in result

    def test_blog_urls_absent_renders_nothing(self, source_topic: Topic) -> None:
        ArticleFactory(
            title="Target Title", slug="target", file_path="articles/target.md"
        )

        with override_settings(
            ROOT_URLCONF="freedom_ls.content_engine.tests.no_blog_urls"
        ):
            result = _render(f"before {_card()} after", source_topic)

        assert "before" in result
        assert "Target Title" not in result
        assert "<article" not in result

    def test_lookup_is_scoped_to_the_content_instance_site(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(
            title="Other Site Title",
            slug="target",
            file_path="articles/target.md",
            site=SiteFactory(),
        )

        result = _render(f"before {_card()} after", source_topic)

        assert "before" in result
        assert "Other Site Title" not in result
