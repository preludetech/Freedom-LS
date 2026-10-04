"""Tests for the content scanner: file discovery and cross-file validation
of an article's `image` path."""

from pathlib import Path

import pytest

from freedom_ls.content_engine.validate import get_all_files, validate


def test_get_all_files_skips_widget_declarations(tmp_path: Path) -> None:
    """Widget declarations live in the dot-prefixed `.claude/` directory,
    which is never scanned as content."""
    # Arrange
    (tmp_path / "course.md").write_text("---\ncontent_type: COURSE\ntitle: X\n---\n")
    widgets_dir = tmp_path / ".claude" / "fls-content" / "widgets"
    widgets_dir.mkdir(parents=True)
    (widgets_dir / "c-foo.md").write_text("# `c-foo`\n\n**Allowed attributes:** none\n")

    # Act
    found = get_all_files(tmp_path)

    # Assert
    assert found == [tmp_path / "course.md"]


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _article(path: Path, image: str | None = None) -> Path:
    image_line = f"image: {image}\nimage_alt: A cover\n" if image else ""
    return _write(
        path,
        f"---\ncontent_type: ARTICLE\ntitle: An Article\n"
        f"published_on: 2026-01-02\n{image_line}---\nBody\n",
    )


def test_missing_article_image_fails_naming_file_path_and_field(tmp_path: Path):
    _article(tmp_path / "post.md", image="images/missing.png")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "post.md" in message
    assert "images/missing.png" in message
    assert "Field: image" in message


def test_article_image_that_exists_passes(tmp_path: Path):
    _write(tmp_path / "images" / "cover.png", "png")
    _article(tmp_path / "post.md", image="images/cover.png")

    validate(tmp_path)


def test_article_image_under_an_underscore_directory_fails(tmp_path: Path):
    _write(tmp_path / "_drafts" / "cover.png", "png")
    _article(tmp_path / "post.md", image="_drafts/cover.png")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    assert "_drafts/cover.png" in str(exc_info.value)


def test_article_image_that_is_not_an_image_fails(tmp_path: Path):
    _write(tmp_path / "handout.pdf", "pdf")
    _article(tmp_path / "post.md", image="handout.pdf")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "handout.pdf" in message
    assert "Field: image" in message
    assert "not an image" in message


def test_article_image_pointing_at_a_content_file_fails(tmp_path: Path):
    _article(tmp_path / "other.md")
    _article(tmp_path / "post.md", image="other.md")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    assert "not an image" in str(exc_info.value)


def test_article_image_path_with_parent_segments_resolves(tmp_path: Path):
    _write(tmp_path / "shared" / "cover.png", "png")
    _article(tmp_path / "posts" / "post.md", image="../shared/cover.png")

    validate(tmp_path)


def test_topic_image_key_is_not_checked(tmp_path: Path):
    _write(
        tmp_path / "topic.md",
        "---\ncontent_type: TOPIC\ntitle: A Topic\nimage: missing.png\n---\nBody\n",
    )

    validate(tmp_path)


def test_validating_the_article_file_alone_skips_the_image_check(tmp_path: Path):
    article = _article(tmp_path / "post.md", image="images/missing.png")

    validate(article)
