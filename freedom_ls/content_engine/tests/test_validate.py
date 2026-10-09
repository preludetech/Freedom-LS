"""Tests for the content scanner and its cross-file validation."""

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.validate import (
    get_all_files,
    parse_single_file,
    validate,
)

# Tests for the content scanner: file discovery and cross-file validation
# of an article's `image` path.


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


# Cross-file validation of a course's `categories`/`dashboard_category` references.


def _write_in_directory(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content)


def _course_dir(repo_dir: Path, name: str = "data-literacy") -> Path:
    """A course's own subdirectory, matching how content is actually authored."""
    course_dir = repo_dir / name
    course_dir.mkdir()
    return course_dir


def test_unknown_category_slug_fails_with_file_slug_and_declared_set():
    """A course naming an undeclared slug in categories fails, naming the file, the slug and the declared set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: start-here
    title: Start here
  - slug: technical
    title: Technical
""",
        )
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - tecnical
---
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course.md" in message
        assert "tecnical" in message
        assert "start-here" in message
        assert "technical" in message


def test_unknown_dashboard_category_fails_naming_file_slug_and_declared_set():
    """An undeclared dashboard_category fails the same way as an undeclared categories entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - technical
dashboard_category: leadership
---
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course.md" in message
        assert "leadership" in message
        assert "technical" in message


def test_dashboard_category_outside_own_categories_fails():
    """A dashboard_category not among the course's own categories fails, naming both."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
  - slug: leadership
    title: Leadership
""",
        )
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - technical
dashboard_category: leadership
---
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course.md" in message
        assert "leadership" in message
        assert "technical" in message


def test_omitting_dashboard_category_with_two_or_more_categories_fails_naming_candidates():
    """Two or more categories with no dashboard_category fails and lists the candidates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
  - slug: leadership
    title: Leadership
""",
        )
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - technical
  - leadership
---
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course.md" in message
        assert "technical" in message
        assert "leadership" in message


def test_retired_category_key_fails_naming_both_replacements():
    """A course still using the retired category key fails, naming categories and dashboard_category."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
category: Technical
---
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "categories" in message
        assert "dashboard_category" in message


def test_two_course_categories_declarations_fail_naming_both_files():
    """Two COURSE_CATEGORIES declarations in one repo fail, naming both files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write_in_directory(
            repo_dir,
            "other_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: leadership
    title: Leadership
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course_categories.yaml" in message
        assert "other_categories.yaml" in message


def test_duplicate_category_slug_fails_naming_the_slug_and_file():
    """Two entries sharing a slug fail, naming the slug and the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
  - slug: technical
    title: Technical Again
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "technical" in message
        assert "course_categories.yaml" in message


def test_duplicate_category_uuid_fails_naming_the_uuid_and_both_slugs():
    """Two entries sharing a uuid fail, naming the uuid and both slugs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        shared_uuid = "10000000-0000-0000-0000-000000000099"
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
    uuid: {shared_uuid}
  - slug: leadership
    title: Leadership
    uuid: {shared_uuid}
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert shared_uuid in message
        assert "technical" in message
        assert "leadership" in message


def test_invalid_category_slug_fails_naming_the_slug_and_file():
    """An entry whose slug is not a valid slug fails, naming the slug and the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: "bad slug!"
    title: Bad
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "bad slug!" in message
        assert "course_categories.yaml" in message


def test_reserved_category_slug_fails_naming_the_reserved_set():
    """An entry whose slug is a reserved section slug fails and lists the reserved set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: recommended
    title: Recommended
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "recommended" in message


def test_category_file_inside_course_directory_fails():
    """A COURSE_CATEGORIES file inside a course directory fails, naming the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        course_dir = repo_dir / "courses" / "data-literacy"
        course_dir.mkdir(parents=True)
        _write_in_directory(
            course_dir,
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
---
""",
        )
        _write_in_directory(
            course_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        assert "course_categories.yaml" in message
        assert "repo root" in message


def test_category_file_after_referencing_courses_validates():
    """A category file appearing later in the sorted file walk still satisfies the courses that reference it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - technical
---
""",
        )
        _write_in_directory(
            repo_dir,
            "zz_course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )

        validate(repo_dir)


def test_five_bad_courses_produce_five_messages_in_one_run():
    """Five courses each naming an undeclared category all fail together, in one run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        for index in range(5):
            _write_in_directory(
                _course_dir(repo_dir, f"course-{index}"),
                "course.md",
                f"""---
content_type: COURSE
title: Course {index}
categories:
  - not-a-real-category-{index}
---
""",
            )

        with pytest.raises(ValueError, match="Validation failed") as exc_info:
            validate(repo_dir)

        message = str(exc_info.value)
        for index in range(5):
            assert f"not-a-real-category-{index}" in message
        assert message.count("❌ Unknown category") == 5


def test_omitting_both_new_keys_passes():
    """A course with no categories and no dashboard_category is the catch-all, not an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
---
""",
        )

        validate(repo_dir)


def test_one_category_with_no_dashboard_category_passes():
    """A course with exactly one category and no dashboard_category resolves via the shorthand."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        _write_in_directory(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write_in_directory(
            _course_dir(repo_dir),
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
categories:
  - technical
---
""",
        )

        validate(repo_dir)


# Cross-file validation of the path a content widget points at.


def _write_widget_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _widget_article(path: Path, slug: str | None = None, body: str = "") -> Path:
    slug_line = f"slug: {slug}\n" if slug else ""
    return _write_widget_file(
        path,
        f"---\ncontent_type: ARTICLE\ntitle: An Article\n"
        f"published_on: 2026-01-02\n{slug_line}---\n{body}\n",
    )


def _topic(path: Path, body: str = "") -> Path:
    return _write_widget_file(
        path, f"---\ncontent_type: TOPIC\ntitle: A Topic\n---\n{body}\n"
    )


def _course(path: Path, body: str = "") -> Path:
    return _write_widget_file(
        path, f"---\ncontent_type: COURSE\ntitle: A Course\n---\n{body}\n"
    )


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
    _widget_article(tmp_path / "post.md")
    _topic(tmp_path / "topic.md", '<c-course-card path="post.md"></c-course-card>')

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "post.md" in message
    assert "not a COURSE" in message


def test_duplicate_article_slugs_fail_naming_both_files(tmp_path: Path):
    _widget_article(tmp_path / "first.md", slug="same-slug")
    _widget_article(tmp_path / "second.md", slug="same-slug")

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    message = str(exc_info.value)
    assert "same-slug" in message
    assert "first.md" in message
    assert "second.md" in message


def test_valid_tree_with_all_three_widgets_passes(tmp_path: Path):
    _widget_article(tmp_path / "blog" / "post.md", slug="post")
    _course(tmp_path / "course" / "course.md")
    _topic(
        tmp_path / "topic.md",
        '<c-article-link path="blog/post.md"></c-article-link>\n\n'
        '<c-article-card path="./blog/../blog/post.md"></c-article-card>\n\n'
        '<c-course-card path="course/course.md"></c-course-card>',
    )

    validate(tmp_path)


# How `tags` is read off a content file.


def test_frontmatter_without_tags_key_parses_to_empty_list(make_temp_file):
    content = """---
content_type: TOPIC
title: Topic Without Tags
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)

    assert len(parsed_items) == 1
    assert parsed_items[0].tags == []


def test_frontmatter_with_a_bare_tags_key_parses_to_empty_list(make_temp_file):
    """YAML reads a valueless `tags:` as None; it means "no tags", not invalid."""
    content = """---
content_type: TOPIC
title: Topic With A Bare Tags Key
tags:
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)

    assert len(parsed_items) == 1
    assert parsed_items[0].tags == []
