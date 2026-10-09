"""Tests for the Article model and the article widgets rendered through markdown."""

from __future__ import annotations

import re
from datetime import date
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import (
    ArticleFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Article, ArticleVisibility, Topic
from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.tests.app_guards import app_not_installed

requires_blog = pytest.mark.skipif(
    app_not_installed("freedom_ls.blog"), reason="blog app is not installed"
)


@pytest.mark.django_db
def test_published_excludes_hidden_articles(mock_site_context):
    # Arrange
    shown = ArticleFactory(visibility=ArticleVisibility.PUBLISHED)
    ArticleFactory(visibility=ArticleVisibility.HIDDEN)

    # Act
    result = list(Article.objects.published())

    # Assert
    assert result == [shown]


@pytest.mark.django_db
def test_default_ordering_is_newest_first_with_ties_broken_by_slug(mock_site_context):
    # Arrange
    old = ArticleFactory(slug="zebra", published_on=date(2025, 1, 1))
    tie_b = ArticleFactory(slug="b-article", published_on=date(2026, 3, 1))
    tie_a = ArticleFactory(slug="a-article", published_on=date(2026, 3, 1))

    # Act
    result = list(Article.objects.all())

    # Assert
    assert result == [tie_a, tie_b, old]


@pytest.mark.django_db
@requires_blog
def test_get_absolute_url_reverses_the_article_detail_route(mock_site_context):
    from django.urls import reverse

    # Arrange
    article = ArticleFactory(slug="hello-world")

    # Act
    url = article.get_absolute_url()

    # Assert
    assert url == reverse("blog:article_detail", kwargs={"slug": "hello-world"})


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("override", "setting", "expected"),
    [
        (True, False, True),
        (False, True, False),
        (None, True, True),
        (None, False, False),
    ],
)
def test_shows_date_prefers_override_then_site_default(
    mock_site_context, override, setting, expected
):
    # Arrange
    article = ArticleFactory(show_date=override)

    # Act
    with override_settings(ARTICLE_SHOW_DATE=setting):
        result = article.shows_date

    # Assert
    assert result is expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("override", "setting", "expected"),
    [
        (True, False, True),
        (False, True, False),
        (None, True, True),
        (None, False, False),
    ],
)
def test_shows_author_prefers_override_then_site_default(
    mock_site_context, override, setting, expected
):
    # Arrange
    article = ArticleFactory(author="Ada Lovelace", show_author=override)

    # Act
    with override_settings(ARTICLE_SHOW_AUTHOR=setting):
        result = article.shows_author

    # Assert
    assert result is expected


@pytest.mark.django_db
def test_shows_author_is_false_when_author_is_empty(mock_site_context):
    # Arrange
    article = ArticleFactory(author="", show_author=True)

    # Act
    result = article.shows_author

    # Assert
    assert result is False


@pytest.mark.django_db
def test_image_file_is_none_without_an_image(mock_site_context):
    assert ArticleFactory(file_path="articles/a.md").image_file is None


@pytest.mark.django_db
def test_image_file_is_none_when_the_path_matches_no_file(mock_site_context):
    article = ArticleFactory(file_path="articles/a.md", image="missing.png")

    assert article.image_file is None


@pytest.mark.django_db
def test_image_file_is_the_file_at_the_root_relative_path(mock_site_context):
    file = FileFactory(file_path="articles/photo.png")
    FileFactory(file_path="articles/other.png")
    article = ArticleFactory(file_path="articles/a.md", image="photo.png")

    assert article.image_file == file


@pytest.mark.django_db
def test_image_file_lookup_honours_parent_segments(mock_site_context):
    file = FileFactory(file_path="images/photo.png")
    article = ArticleFactory(file_path="articles/a.md", image="../images/photo.png")

    assert article.image_file == file


@pytest.mark.django_db
def test_image_file_ignores_a_file_belonging_to_another_site(mock_site_context):
    FileFactory(
        file_path="articles/photo.png",
        site=Site.objects.create(name="other", domain="other.example.com"),
    )
    article = ArticleFactory(file_path="articles/a.md", image="photo.png")

    assert article.image_file is None


@pytest.mark.django_db
def test_with_image_files_resolves_every_image_in_two_queries(
    mock_site_context, django_assert_max_num_queries
):
    with_image = ArticleFactory(
        file_path="articles/a.md",
        slug="a",
        image="photo.png",
        published_on=date(2026, 3, 1),
    )
    ArticleFactory(file_path="articles/b.md", slug="b", published_on=date(2026, 2, 1))
    unresolved = ArticleFactory(
        file_path="articles/c.md",
        slug="c",
        image="missing.png",
        published_on=date(2026, 1, 1),
    )
    photo = FileFactory(file_path="articles/photo.png")

    with django_assert_max_num_queries(2):
        articles = Article.objects.published().with_image_files()
        images = [article.image_file for article in articles]

    assert articles == list(Article.objects.published())
    assert articles[0] == with_image
    assert images == [photo, None, None]
    assert articles[2] == unresolved


# Tests for the article cotton widgets rendered through markdown.


def _render(body: str, topic: Topic) -> str:
    return str(render_markdown(body, None, context={"content_instance": topic}))


def _squash(html: str) -> str:
    return re.sub(r"\s+", " ", html).strip()


@pytest.fixture
def source_topic(mock_site_context) -> Topic:
    return cast("Topic", TopicFactory(file_path="2. topic/content.md"))


@pytest.mark.django_db
@requires_blog
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
@requires_blog
class TestArticleCard:
    @pytest.mark.parametrize("variant", ["row", "compact", "bogus"])
    def test_variant_renders_title_link_and_description(
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

        assert re.search(rf'<a href="{url}"[^>]*>\s*Card Title\s*</a>', result)
        assert "Card description text" in result

    def test_unknown_variant_renders_the_same_markup_as_row(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        row = _render(_card(variant="row"), source_topic)
        unknown = _render(_card(variant="bogus"), source_topic)

        assert unknown == row

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


@pytest.mark.django_db
@requires_blog
class TestArticleCardFromArticle:
    def test_article_attribute_renders_the_same_card_as_path(
        self, article_with_image
    ) -> None:
        topic = cast("Topic", TopicFactory(file_path="2. topic/content.md"))
        by_path = _render(
            _card(path="../articles/with-image.md", variant="compact"), topic
        )

        page = render_to_string(
            "blog/article_list.html",
            {"articles": [article_with_image], "blog_name": "Blog"},
        )
        match = re.search(r"<article.*?</article>", page, re.DOTALL)
        assert match is not None
        by_article = match.group(0)

        assert by_path.strip() != ""
        assert _squash(by_article) == _squash(by_path)

    def test_article_attribute_written_in_markdown_is_stripped(
        self, source_topic: Topic
    ) -> None:
        ArticleFactory(slug="target", file_path="articles/target.md")

        result = _render(
            '<c-article-card article="target" path="../articles/missing.md"></c-article-card>',
            source_topic,
        )

        assert "<article" not in result
