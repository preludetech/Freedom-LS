import re

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import ArticleFactory
from freedom_ls.content_engine.models import ArticleVisibility


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
