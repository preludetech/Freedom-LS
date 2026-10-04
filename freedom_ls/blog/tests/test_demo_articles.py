"""The public pages for the shipped demo articles.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import re

import pytest

from django.conf import settings
from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import File

pytestmark = pytest.mark.fls_internal

IMAGE_FILES = ["images/backyard-drone-flight.jpg", "images/landscape.svg"]
PUBLISHED = ["getting-started-with-articles", "undated-notes", "unsigned-update"]


@pytest.fixture
def loaded_demo_content(site, mock_site_context) -> None:
    save_content_to_db(settings.BASE_DIR / "demo_content", site.name)


@pytest.mark.django_db
def test_the_hidden_demo_article_returns_404(loaded_demo_content):
    response = Client().get(
        reverse("blog:article_detail", kwargs={"slug": "hidden-draft"})
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("slug", PUBLISHED)
def test_a_published_demo_article_returns_200(loaded_demo_content, slug):
    response = Client().get(reverse("blog:article_detail", kwargs={"slug": slug}))

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_index_lists_the_published_demo_articles(loaded_demo_content):
    response = Client().get(reverse("blog:index"))

    assert response.status_code == 200
    assert "Undated notes" in response.content.decode()


@pytest.mark.django_db
def test_the_sitemap_lists_published_demo_articles_and_not_the_hidden_one(
    loaded_demo_content,
):
    body = Client().get(reverse("sitemap")).content.decode()

    assert all(
        reverse("blog:article_detail", kwargs={"slug": slug}) in body
        for slug in PUBLISHED
    )
    assert reverse("blog:article_detail", kwargs={"slug": "hidden-draft"}) not in body


@pytest.mark.django_db
def test_robots_txt_allows_the_blog_index(loaded_demo_content):
    content = Client().get("/robots.txt").content.decode()

    assert f"Allow: {reverse('blog:index')}" in content


@pytest.mark.django_db
def test_the_getting_started_article_does_not_skip_from_h1_to_h3(loaded_demo_content):
    body = (
        Client()
        .get(
            reverse(
                "blog:article_detail", kwargs={"slug": "getting-started-with-articles"}
            )
        )
        .content.decode()
    )

    assert "<h2>Linking to other articles</h2>" in body
    assert "<h3" not in body.split("<h2", 1)[0]


@pytest.mark.django_db
def test_the_getting_started_page_emits_og_image_and_a_large_twitter_card(
    loaded_demo_content,
):
    body = (
        Client()
        .get(
            reverse(
                "blog:article_detail", kwargs={"slug": "getting-started-with-articles"}
            )
        )
        .content.decode()
    )

    assert re.search(r'<meta[^>]*property="og:image"', body)
    assert re.search(r'<meta[^>]*content="summary_large_image"', body)


@pytest.mark.django_db
def test_the_index_shows_a_thumbnail_for_each_demo_article_with_an_image(
    site, loaded_demo_content
):
    body = Client().get(reverse("blog:index")).content.decode()

    urls = [
        File.objects.get(site=site, file_path__endswith=name).file.url
        for name in IMAGE_FILES
    ]
    assert all(f'src="{url}"' in body for url in urls)
