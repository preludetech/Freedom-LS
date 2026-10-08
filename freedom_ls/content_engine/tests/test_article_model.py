from datetime import date

import pytest

from django.contrib.sites.models import Site
from django.test import override_settings

from freedom_ls.content_engine.factories import ArticleFactory, FileFactory
from freedom_ls.content_engine.models import Article, ArticleVisibility
from freedom_ls.tests.app_guards import app_not_installed


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
@pytest.mark.skipif(
    app_not_installed("freedom_ls.blog"), reason="blog app is not installed"
)
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
