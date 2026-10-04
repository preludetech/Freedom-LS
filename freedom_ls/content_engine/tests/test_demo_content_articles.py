"""The shipped demo articles have to show every byline case and widget variant.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from django.conf import settings

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Article, ArticleVisibility
from freedom_ls.content_engine.validate import validate
from freedom_ls.tests.app_guards import app_not_installed

pytestmark = pytest.mark.fls_internal

DEMO_ARTICLES = settings.BASE_DIR / "demo_content" / "functionality_demo_articles"


@pytest.mark.django_db
def test_the_demo_set_has_a_hidden_article(site, loaded_demo_content):
    hidden = Article.objects.filter(site=site, visibility=ArticleVisibility.HIDDEN)

    assert [a.slug for a in hidden] == ["hidden-draft"]


@pytest.mark.django_db
def test_the_demo_set_has_an_article_that_hides_its_date(site, loaded_demo_content):
    article = Article.objects.get(site=site, slug="undated-notes")

    assert article.show_date is False
    assert article.author


@pytest.mark.django_db
def test_the_getting_started_article_has_the_drone_flight_image(
    site, loaded_demo_content
):
    article = Article.objects.get(site=site, slug="getting-started-with-articles")

    assert article.image_file is not None
    assert article.image_file.file_path.endswith("images/backyard-drone-flight.jpg")


@pytest.mark.django_db
def test_the_undated_notes_article_has_no_image(site, loaded_demo_content):
    article = Article.objects.get(site=site, slug="undated-notes")

    assert article.image_file is None


@pytest.mark.django_db
def test_the_demo_set_has_an_article_with_no_author(site, loaded_demo_content):
    article = Article.objects.get(site=site, slug="unsigned-update")

    assert article.author == ""


@pytest.mark.skipif(app_not_installed("freedom_ls.blog"), reason="blog not installed")
@pytest.mark.django_db
def test_the_mixed_grid_article_shows_a_linked_article_card_title(
    site, loaded_demo_content
):
    article = Article.objects.get(site=site, slug="getting-started-with-articles")

    rendered = article.rendered_content()

    assert "Undated notes</a>" in rendered


@pytest.mark.django_db
def test_loading_a_copy_of_the_demo_articles_twice_leaves_the_files_unchanged(
    site, mock_site_context, tmp_path: Path
):
    copy = tmp_path / "functionality_demo_articles"
    shutil.copytree(DEMO_ARTICLES, copy)
    save_content_to_db(tmp_path, site.name)
    after_first = {p.name: p.read_bytes() for p in copy.glob("*.md")}

    save_content_to_db(tmp_path, site.name)

    assert {p.name: p.read_bytes() for p in copy.glob("*.md")} == after_first


def test_the_host_validator_passes_on_the_demo_content():
    validate(settings.BASE_DIR / "demo_content")
