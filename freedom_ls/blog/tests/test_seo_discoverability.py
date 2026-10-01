import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import ArticleFactory
from freedom_ls.content_engine.models import ArticleVisibility


@pytest.mark.django_db
def test_sitemap_lists_blog_index_and_published_articles(mock_site_context):
    # Arrange
    article = ArticleFactory(slug="why-we-teach")

    # Act
    body = Client().get(reverse("sitemap")).content.decode()

    # Assert
    assert f"{reverse('blog:index')}</loc>" in body
    assert f"{article.get_absolute_url()}</loc>" in body


@pytest.mark.django_db
def test_sitemap_leaves_out_hidden_and_other_site_articles(mock_site_context):
    # Arrange
    visible = ArticleFactory(slug="open-one")
    hidden = ArticleFactory(slug="secret-one", visibility=ArticleVisibility.HIDDEN)
    foreign = ArticleFactory(
        slug="elsewhere-one", site=SiteFactory(domain="o.example.com", name="O")
    )

    # Act
    body = Client().get(reverse("sitemap")).content.decode()

    # Assert
    assert f"{visible.get_absolute_url()}</loc>" in body
    assert f"{hidden.get_absolute_url()}</loc>" not in body
    assert f"{foreign.get_absolute_url()}</loc>" not in body


@pytest.mark.django_db
def test_robots_txt_allows_blog_index_alongside_courses(mock_site_context):
    # Act
    content = Client().get("/robots.txt").content.decode()

    # Assert
    assert f"Allow: {reverse('blog:index')}" in content
    assert "Allow: /courses/" in content
