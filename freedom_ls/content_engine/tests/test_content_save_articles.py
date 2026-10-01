"""Loading ARTICLE markdown files from a content repo."""

from pathlib import Path

import pytest
import yaml

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Article


def _write_article(repo_dir: Path, relative: str, front_matter: str) -> Path:
    file_path = repo_dir / relative
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"---\n{front_matter}---\n\nBody text.\n")
    return file_path


def _front_matter(file_path: Path) -> dict:
    data = yaml.safe_load(file_path.read_text().split("---")[1])
    assert isinstance(data, dict)
    return data


@pytest.mark.django_db
def test_first_load_writes_the_uuid_back_and_stores_the_fields(
    site, mock_site_context, tmp_path
):
    file_path = _write_article(
        tmp_path,
        "writing/Launch Day.md",
        "content_type: ARTICLE\ntitle: Launch day\npublished_on: 2026-03-04\n"
        "author: Sam\nshow_date: false\nshow_author: true\n",
    )

    save_content_to_db(tmp_path, site.name)

    article = Article.objects.get(site=site)
    assert _front_matter(file_path)["uuid"] == str(article.id)
    assert (article.slug, article.title, article.author) == (
        "launch-day",
        "Launch day",
        "Sam",
    )
    assert (article.show_date, article.show_author) == (False, True)
    assert str(article.published_on) == "2026-03-04"


@pytest.mark.django_db
def test_second_load_changes_nothing_and_leaves_one_row(
    site, mock_site_context, tmp_path
):
    file_path = _write_article(
        tmp_path,
        "writing/launch/content.md",
        "content_type: ARTICLE\ntitle: Launch day\npublished_on: 2026-03-04\n",
    )
    save_content_to_db(tmp_path, site.name)
    first_bytes = file_path.read_bytes()

    save_content_to_db(tmp_path, site.name)

    assert file_path.read_bytes() == first_bytes
    assert Article.objects.filter(site=site).count() == 1
    assert Article.objects.get(site=site).slug == "launch"
