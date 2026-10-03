"""Loading ARTICLE markdown files from a content repo."""

from pathlib import Path

import pytest
import yaml

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Article, ContentCollectionItem


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


@pytest.mark.django_db
def test_slug_held_by_another_uuid_is_refused_naming_the_owner(
    site, mock_site_context, tmp_path
):
    _write_article(
        tmp_path,
        "writing/launch.md",
        "content_type: ARTICLE\ntitle: Launch\npublished_on: 2026-03-04\n",
    )
    save_content_to_db(tmp_path, site.name)
    owner = Article.objects.get(site=site)
    _write_article(
        tmp_path,
        "other/launch.md",
        "content_type: ARTICLE\ntitle: Imposter\npublished_on: 2026-03-05\n",
    )

    with pytest.raises(ValueError, match=str(owner.id)):
        save_content_to_db(tmp_path, site.name)

    assert Article.objects.get(site=site).title == "Launch"


@pytest.mark.django_db
def test_removing_optional_fields_clears_the_stored_values(
    site, mock_site_context, tmp_path
):
    file_path = _write_article(
        tmp_path,
        "writing/launch.md",
        "content_type: ARTICLE\ntitle: Launch\npublished_on: 2026-03-04\n"
        "author: Sam\nshow_date: false\nshow_author: false\n",
    )
    save_content_to_db(tmp_path, site.name)
    uuid = _front_matter(file_path)["uuid"]
    _write_article(
        tmp_path,
        "writing/launch.md",
        f"content_type: ARTICLE\nuuid: {uuid}\ntitle: Launch\n"
        "published_on: 2026-03-04\n",
    )

    save_content_to_db(tmp_path, site.name)

    article = Article.objects.get(site=site)
    assert article.author == ""
    assert (article.show_date, article.show_author) == (None, None)


@pytest.mark.django_db
def test_article_inside_a_course_directory_loads_but_is_not_a_child(
    site, mock_site_context, tmp_path
):
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    (course_dir / "course.md").write_text(
        "---\ncontent_type: COURSE\ntitle: My course\n---\n\nBody.\n"
    )
    _write_article(
        tmp_path,
        "my-course/loose.md",
        "content_type: ARTICLE\ntitle: Loose\npublished_on: 2026-03-04\n",
    )
    _write_article(
        tmp_path,
        "my-course/nested/content.md",
        "content_type: ARTICLE\ntitle: Nested\npublished_on: 2026-03-04\n",
    )

    save_content_to_db(tmp_path, site.name)

    assert set(Article.objects.filter(site=site).values_list("slug", flat=True)) == {
        "loose",
        "nested",
    }
    assert ContentCollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_deleting_the_file_and_reloading_leaves_the_row(
    site, mock_site_context, tmp_path
):
    file_path = _write_article(
        tmp_path,
        "writing/launch.md",
        "content_type: ARTICLE\ntitle: Launch\npublished_on: 2026-03-04\n",
    )
    other = _write_article(
        tmp_path,
        "writing/keep.md",
        "content_type: ARTICLE\ntitle: Keep\npublished_on: 2026-03-04\n",
    )
    save_content_to_db(tmp_path, site.name)
    file_path.unlink()

    save_content_to_db(tmp_path, site.name)

    assert other.exists()
    assert set(Article.objects.filter(site=site).values_list("slug", flat=True)) == {
        "launch",
        "keep",
    }
