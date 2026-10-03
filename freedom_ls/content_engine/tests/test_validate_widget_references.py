"""Cross-file validation of the path a content widget points at."""

from pathlib import Path

import pytest

from freedom_ls.content_engine.validate import validate


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _article(path: Path, slug: str | None = None, body: str = "") -> Path:
    slug_line = f"slug: {slug}\n" if slug else ""
    return _write(
        path,
        f"---\ncontent_type: ARTICLE\ntitle: An Article\n"
        f"published_on: 2026-01-02\n{slug_line}---\n{body}\n",
    )


def _topic(path: Path, body: str = "") -> Path:
    return _write(path, f"---\ncontent_type: TOPIC\ntitle: A Topic\n---\n{body}\n")


def _course(path: Path, body: str = "") -> Path:
    return _write(path, f"---\ncontent_type: COURSE\ntitle: A Course\n---\n{body}\n")


@pytest.mark.parametrize(
    "widget", ["c-article-link", "c-article-card", "c-course-card"]
)
def test_broken_widget_path_fails_naming_file_and_path(tmp_path: Path, widget: str):
    _topic(tmp_path / "topic.md", f'<{widget} path="missing/thing.md"></{widget}>')

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "topic.md" in message
    assert "missing/thing.md" in message
    assert "no content file at this path" in message
    assert f"{widget} path" in message


@pytest.mark.parametrize("widget", ["c-article-link", "c-article-card"])
def test_article_widget_pointing_at_a_topic_fails(tmp_path: Path, widget: str):
    _topic(tmp_path / "target.md")
    _topic(tmp_path / "topic.md", f'<{widget} path="target.md"></{widget}>')

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "topic.md" in message
    assert "not an ARTICLE" in message


def test_course_card_pointing_at_an_article_fails(tmp_path: Path):
    _article(tmp_path / "post.md")
    _topic(tmp_path / "topic.md", '<c-course-card path="post.md"></c-course-card>')

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "post.md" in message
    assert "not a COURSE" in message


def test_duplicate_article_slugs_fail_naming_both_files(tmp_path: Path):
    _article(tmp_path / "first.md", slug="same-slug")
    _article(tmp_path / "second.md", slug="same-slug")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "same-slug" in message
    assert "first.md" in message
    assert "second.md" in message


def test_valid_tree_with_all_three_widgets_passes(tmp_path: Path):
    _article(tmp_path / "blog" / "post.md", slug="post")
    _course(tmp_path / "course" / "course.md")
    _topic(
        tmp_path / "topic.md",
        '<c-article-link path="blog/post.md"></c-article-link>\n\n'
        '<c-article-card path="./blog/../blog/post.md"></c-article-card>\n\n'
        '<c-course-card path="course/course.md"></c-course-card>',
    )

    validate(tmp_path)
