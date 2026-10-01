"""Validation of the ARTICLE schema: slug derivation and rejected fields."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from django.utils.text import slugify as django_slugify

from freedom_ls.content_engine.schema import Article, slugify


def _article(file_path: str, **overrides: object) -> Article:
    fields: dict[str, object] = {
        "content_type": "ARTICLE",
        "title": "My Article",
        "published_on": date(2026, 1, 2),
        "file_path": Path(file_path),
    }
    fields.update(overrides)
    return Article.model_validate(fields)


def test_slug_defaults_to_the_file_stem():
    article = _article("blog/1. My Article.md")

    assert article.slug == "1-my-article"


def test_slug_defaults_to_the_parent_directory_for_content_md():
    article = _article("blog/Launch Day/content.md")

    assert article.slug == "launch-day"


def test_a_written_slug_is_kept():
    article = _article("blog/whatever.md", slug="kept_slug")

    assert article.slug == "kept_slug"


def test_a_written_bad_slug_is_rejected_naming_the_file():
    with pytest.raises(ValidationError, match=r"blog/bad\.md"):
        _article("blog/bad.md", slug="bad slug!")


def test_a_written_bad_slug_error_is_located_at_the_slug_field():
    with pytest.raises(ValidationError) as excinfo:
        _article("blog/bad.md", slug="bad slug!")

    assert excinfo.value.errors()[0]["loc"] == ("slug",)


def test_a_derived_empty_slug_is_rejected_naming_the_file():
    with pytest.raises(ValidationError, match=r"blog/!!!\.md"):
        _article("blog/!!!.md")


def test_published_on_is_required():
    with pytest.raises(ValidationError, match="published_on"):
        Article.model_validate(
            {
                "content_type": "ARTICLE",
                "title": "No date",
                "file_path": Path("blog/no-date.md"),
            }
        )


def test_coming_soon_visibility_is_rejected_naming_the_allowed_values():
    with pytest.raises(ValidationError, match=r"published.*hidden"):
        _article("blog/soon.md", visibility="coming_soon")


@pytest.mark.parametrize("field", ["category", "image"])
def test_course_only_fields_are_rejected_with_the_article_message(field: str):
    with pytest.raises(ValidationError, match=f"'{field}' is not an article field"):
        _article("blog/x.md", **{field: "something"})


@pytest.mark.parametrize(
    "value",
    [
        "1. My Article",
        "Hello, World!",
        "  Spaced  out  ",
        "Café Déjà Vu",
        "a_b-c",
        "!!!",
    ],
)
def test_slugify_matches_djangos(value: str):
    assert slugify(value) == django_slugify(value, allow_unicode=True)


def test_slugify_numbered_title():
    assert slugify("1. My Article") == "1-my-article"
