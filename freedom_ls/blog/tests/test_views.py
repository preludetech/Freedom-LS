import re
from datetime import date

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import ArticleFactory
from freedom_ls.content_engine.models import Article, ArticleVisibility


def _without_csrf_token(content: bytes) -> str:
    """The page embeds a fresh CSRF token per response, so mask it before comparing."""
    return re.sub(
        r"X-CSRFToken&quot;: &quot;[^&]*&quot;|X-CSRFToken\": \"[^\"]*\"",
        "",
        content.decode(),
    )


@pytest.mark.django_db
def test_published_article_renders_for_logged_out_visitor(client, mock_site_context):
    # Arrange
    article = ArticleFactory(
        title="Why we teach",
        subtitle="A short reflection",
        content="Learning is **a practice**.",
    )

    # Act
    response = client.get(reverse("blog:article_detail", kwargs={"slug": article.slug}))

    # Assert
    assert response.status_code == 200
    body = response.content.decode()
    assert "Why we teach" in body
    assert "A short reflection" in body
    assert "<strong>a practice</strong>" in body


@pytest.mark.django_db
def test_hidden_and_unknown_slugs_return_identical_404s(client, mock_site_context):
    # Arrange
    ArticleFactory(slug="secret", visibility=ArticleVisibility.HIDDEN)
    ArticleFactory(slug="open")

    # Act
    hidden = client.get(reverse("blog:article_detail", kwargs={"slug": "secret"}))
    unknown = client.get(reverse("blog:article_detail", kwargs={"slug": "nope"}))
    published = client.get(reverse("blog:article_detail", kwargs={"slug": "open"}))

    # Assert
    assert published.status_code == 200
    assert hidden.status_code == 404
    assert unknown.status_code == 404
    assert _without_csrf_token(hidden.content) == _without_csrf_token(unknown.content)


@pytest.mark.django_db
def test_article_on_another_site_returns_404(client, mock_site_context):
    # Arrange
    other_site = SiteFactory(domain="other.example.com", name="Other")
    ArticleFactory(slug="elsewhere", site=other_site)
    ArticleFactory(slug="here")

    # Act
    elsewhere = client.get(reverse("blog:article_detail", kwargs={"slug": "elsewhere"}))
    here = client.get(reverse("blog:article_detail", kwargs={"slug": "here"}))

    # Assert
    assert here.status_code == 200
    assert elsewhere.status_code == 404


@pytest.mark.django_db
def test_byline_shows_date_and_author_when_allowed(client, mock_site_context):
    # Arrange
    article = ArticleFactory(
        title="Bylined",
        published_on=date(2026, 3, 9),
        author="Ada Lovelace",
        show_date=True,
        show_author=True,
    )

    # Act
    response = client.get(reverse("blog:article_detail", kwargs={"slug": article.slug}))

    # Assert
    body = response.content.decode()
    assert '<time datetime="2026-03-09">' in body
    assert "Ada Lovelace" in body


@pytest.mark.django_db
def test_byline_is_absent_when_date_and_author_are_hidden(client, mock_site_context):
    # Arrange
    article = ArticleFactory(
        title="Unbylined",
        published_on=date(2026, 3, 9),
        author="Ada Lovelace",
        show_date=False,
        show_author=False,
    )

    # Act
    response = client.get(reverse("blog:article_detail", kwargs={"slug": article.slug}))

    # Assert
    body = response.content.decode()
    assert "Unbylined" in body
    assert "<time" not in body
    assert "Ada Lovelace" not in body


def _get_article_page(client: Client, article: Article) -> str:
    response = client.get(reverse("blog:article_detail", kwargs={"slug": article.slug}))
    assert response.status_code == 200
    return response.content.decode()


def _title(body: str) -> str:
    match = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
    assert match, "no <title> tag found"
    return match.group(1).strip()


def _meta(body: str, attr: str, key: str) -> str | None:
    """Content of the first ``<meta {attr}="{key}">`` tag, whichever order its attributes take."""
    for tag in re.findall(r"<meta\b[^>]*>", body):
        if f'{attr}="{key}"' in tag:
            content = re.search(r'content="([^"]*)"', tag)
            assert content, f"meta {key} has no content"
            return content.group(1)
    return None


@pytest.mark.django_db
def test_article_page_title_is_the_article_title(client, mock_site_context):
    # Arrange
    article = ArticleFactory(title="Why we teach")

    # Act
    body = _get_article_page(client, article)

    # Assert
    assert _title(body) == "Why we teach"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("description", "subtitle", "expected"),
    [
        ("The description", "The subtitle", "The description"),
        ("", "The subtitle", "The subtitle"),
        ("", "", "The title"),
    ],
)
def test_meta_description_falls_back_from_description_to_subtitle_to_title(
    client, mock_site_context, description, subtitle, expected
):
    # Arrange
    article = ArticleFactory(
        title="The title", subtitle=subtitle, description=description
    )

    # Act
    body = _get_article_page(client, article)

    # Assert
    assert _meta(body, "name", "description") == expected
    assert _meta(body, "property", "og:description") == expected


@pytest.mark.django_db
def test_article_page_carries_open_graph_tags(client, mock_site_context):
    # Arrange
    article = ArticleFactory(title="Why we teach", description="A reflection")

    # Act
    body = _get_article_page(client, article)

    # Assert
    assert _meta(body, "property", "og:type") == "article"
    assert _meta(body, "property", "og:title") == "Why we teach"
    assert _meta(body, "property", "og:description") == "A reflection"


@pytest.mark.django_db
def test_published_time_and_author_meta_present_when_shown(client, mock_site_context):
    # Arrange
    article = ArticleFactory(
        published_on=date(2026, 3, 9),
        author="Ada Lovelace",
        show_date=True,
        show_author=True,
    )

    # Act
    body = _get_article_page(client, article)

    # Assert
    assert _meta(body, "property", "article:published_time") == "2026-03-09"
    assert _meta(body, "name", "author") == "Ada Lovelace"


@pytest.mark.django_db
def test_published_time_and_author_meta_absent_when_hidden(client, mock_site_context):
    # Arrange
    article = ArticleFactory(
        title="Quiet",
        published_on=date(2026, 3, 9),
        author="Ada Lovelace",
        show_date=False,
        show_author=False,
    )

    # Act
    body = _get_article_page(client, article)

    # Assert
    assert _meta(body, "property", "og:title") == "Quiet"
    assert _meta(body, "property", "article:published_time") is None
    assert _meta(body, "name", "author") is None


@pytest.mark.django_db
def test_canonical_link_equals_the_article_url_and_no_og_image(
    client, mock_site_context
):
    # Arrange
    article = ArticleFactory()
    path = reverse("blog:article_detail", kwargs={"slug": article.slug})

    # Act
    body = _get_article_page(client, article)

    # Assert
    canonical = re.search(r'<link rel="canonical" href="([^"]*)"', body)
    assert canonical
    assert canonical.group(1).endswith(path)
    assert _meta(body, "property", "og:url") == canonical.group(1)
    assert _meta(body, "name", "twitter:card") == "summary"
    assert _meta(body, "property", "og:image") is None


@pytest.mark.django_db
def test_index_lists_only_published_articles_newest_first(client, mock_site_context):
    # Arrange
    ArticleFactory(title="Oldest", published_on=date(2026, 1, 1))
    ArticleFactory(title="Newest", published_on=date(2026, 3, 1))
    ArticleFactory(title="Middle", published_on=date(2026, 2, 1))
    ArticleFactory(title="Draft", visibility=ArticleVisibility.HIDDEN)

    # Act
    response = client.get(reverse("blog:index"))

    # Assert
    assert response.status_code == 200
    body = response.content.decode()
    assert "Draft" not in body
    assert body.index("Newest") < body.index("Middle") < body.index("Oldest")


@pytest.mark.django_db
def test_index_links_each_title_and_shows_the_description(client, mock_site_context):
    # Arrange
    article = ArticleFactory(title="Why we teach", description="A short reflection")

    # Act
    response = client.get(reverse("blog:index"))

    # Assert
    body = response.content.decode()
    assert f'href="{article.get_absolute_url()}"' in body
    assert "Why we teach" in body
    assert "A short reflection" in body


@pytest.mark.django_db
def test_index_excludes_another_sites_articles(client, mock_site_context):
    # Arrange
    other_site = SiteFactory(domain="other.example.com", name="Other")
    ArticleFactory(title="Elsewhere piece", site=other_site)
    ArticleFactory(title="Local piece")

    # Act
    response = client.get(reverse("blog:index"))

    # Assert
    body = response.content.decode()
    assert "Local piece" in body
    assert "Elsewhere piece" not in body


@pytest.mark.django_db
def test_index_shows_an_empty_state_when_there_are_no_articles(
    client, mock_site_context
):
    # Act
    response = client.get(reverse("blog:index"))

    # Assert
    assert response.status_code == 200
    body = response.content.decode()
    assert "Articles" in body
    assert "content_save" in body


@pytest.mark.django_db
def test_index_byline_obeys_show_date(client, mock_site_context):
    # Arrange
    ArticleFactory(title="Dated", published_on=date(2026, 3, 9), show_date=True)
    ArticleFactory(title="Undated", published_on=date(2026, 4, 9), show_date=False)

    # Act
    response = client.get(reverse("blog:index"))

    # Assert
    body = response.content.decode()
    assert '<time datetime="2026-03-09">' in body
    assert '<time datetime="2026-04-09">' not in body


@pytest.mark.django_db
def test_article_body_is_wrapped_in_the_markdown_container(client, mock_site_context):
    # Arrange
    article = ArticleFactory(content="First paragraph.\n\nSecond paragraph.")

    # Act
    response = client.get(reverse("blog:article_detail", kwargs={"slug": article.slug}))

    # Assert
    body = response.content.decode()
    assert re.search(
        r'<div class="[^"]*space-y-4[^"]*">\s*<p>First paragraph\.</p>', body
    )
