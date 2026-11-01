"""Tests for the content scanner and its cross-file validation."""

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.validate import (
    auto_discovered_children,
    get_all_files,
    parse_single_file,
    validate,
    validate_due_date_placements,
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


def _activity(path: Path) -> Path:
    return _write_widget_file(
        path, "---\ncontent_type: ACTIVITY\ntitle: An Activity\n---\nBody\n"
    )


def _part(path: Path) -> Path:
    return _write_widget_file(
        path, "---\ncontent_type: COURSE_PART\ntitle: A Part\n---\n"
    )


def _course_with_entries(path: Path, entries: list[str]) -> Path:
    """A course whose children are the given `path` values, each with a due date."""
    lines = "".join(
        f"  - path: {entry}\n    due_days_after_registration: 3\n" for entry in entries
    )
    return _write_widget_file(
        path, f"---\ncontent_type: COURSE\ntitle: A Course\nchildren:\n{lines}---\n"
    )


def _placement_errors(directory: Path) -> list[str]:
    parsed = [
        item
        for file_path in get_all_files(directory)
        for item in parse_single_file(file_path)
    ]
    return validate_due_date_placements(parsed)


@pytest.mark.parametrize(
    ("filename", "make_child"),
    [
        ("activity.md", _activity),
        ("article.md", _widget_article),
        ("part.yaml", _part),
    ],
)
def test_due_keys_on_a_non_topic_non_form_entry_fail_naming_file_entry_and_path(
    tmp_path: Path, filename: str, make_child
):
    make_child(tmp_path / filename)
    _course_with_entries(tmp_path / "course.md", [filename])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "course.md" in errors[0]
    assert "children[0]" in errors[0]
    assert filename in errors[0]


def test_two_bad_entries_give_two_messages(tmp_path: Path):
    _activity(tmp_path / "activity.md")
    _widget_article(tmp_path / "article.md")
    _course_with_entries(tmp_path / "course.md", ["activity.md", "article.md"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 2


def test_due_keys_on_a_topic_entry_pass(tmp_path: Path):
    _topic(tmp_path / "topic.md")
    _course_with_entries(tmp_path / "course.md", ["topic.md"])

    assert _placement_errors(tmp_path) == []


def test_a_non_topic_entry_without_due_keys_passes(tmp_path: Path):
    _activity(tmp_path / "activity.md")
    _write_widget_file(
        tmp_path / "course.md",
        "---\ncontent_type: COURSE\ntitle: A Course\nchildren:\n"
        "  - path: activity.md\n---\n",
    )

    assert _placement_errors(tmp_path) == []


def test_a_bad_entry_naming_nothing_gives_no_message_here(tmp_path: Path):
    _course_with_entries(tmp_path / "course.md", ["missing.md"])

    assert _placement_errors(tmp_path) == []


def test_validate_lists_a_due_date_on_an_activity_entry_in_the_report(tmp_path: Path):
    _activity(tmp_path / "activity.md")
    _course_with_entries(tmp_path / "course.md", ["activity.md"])

    with pytest.raises(ValueError, match="Validation failed") as exc_info:
        validate(tmp_path)

    assert "Invalid due date placement" in str(exc_info.value)
    assert "activity.md" in str(exc_info.value)


def _course_placing_part(
    path: Path, part_path: str, nested: list[str], part_dir_prefix: str = ""
) -> Path:
    """A course placing the part at `part_path`, with a nested children: entry per path."""
    lines = "".join(
        f"      - path: {entry}\n        due_days_after_registration: 3\n"
        for entry in nested
    )
    return _write_widget_file(
        path,
        "---\ncontent_type: COURSE\ntitle: A Course\nchildren:\n"
        f"  - path: {part_dir_prefix}{part_path}\n    children:\n{lines}---\n",
    )


def _part_listing(path: Path, children: list[str]) -> Path:
    lines = "".join(f"  - path: {child}\n" for child in children)
    return _write_widget_file(
        path,
        f"---\ncontent_type: COURSE_PART\ntitle: A Part\nchildren:\n{lines}---\n",
    )


def test_a_nested_list_naming_the_parts_children_passes(tmp_path: Path) -> None:
    _topic(tmp_path / "part" / "intro.md")
    _part_listing(tmp_path / "part" / "part.yaml", ["intro.md"])
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["intro.md"])

    assert _placement_errors(tmp_path) == []


def test_a_nested_list_on_an_auto_discovered_part_passes(tmp_path: Path) -> None:
    _topic(tmp_path / "part" / "intro.md")
    _write_widget_file(
        tmp_path / "part" / "part.yaml",
        "---\ncontent_type: COURSE_PART\ntitle: A Part\n---\n",
    )
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["intro.md"])

    assert _placement_errors(tmp_path) == []


def test_a_nested_list_in_a_part_yaml_entry_fails(tmp_path: Path) -> None:
    _topic(tmp_path / "intro.md")
    _write_widget_file(
        tmp_path / "part.yaml",
        "---\ncontent_type: COURSE_PART\ntitle: A Part\nchildren:\n"
        "  - path: intro.md\n    children:\n"
        "      - path: intro.md\n        due_days_after_registration: 3\n---\n",
    )

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "a nested children: list in a part.yaml entry" in errors[0]
    assert "children[0].children" in errors[0]


def test_a_nested_list_on_a_topic_entry_fails(tmp_path: Path) -> None:
    _topic(tmp_path / "topic.md")
    _course_placing_part(tmp_path / "course.md", "topic.md", ["x.md"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "a nested children: list on a TOPIC placement" in errors[0]


def test_a_nested_path_naming_nothing_in_a_listed_part_lists_the_parts_children(
    tmp_path: Path,
) -> None:
    _topic(tmp_path / "part" / "intro.md")
    _topic(tmp_path / "part" / "sub" / "deeper.md")
    _part_listing(tmp_path / "part" / "part.yaml", ["intro.md", "sub/deeper.md"])
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["missing.md"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "the part has no child at this path" in errors[0]
    assert "children[0].children[0]" in errors[0]
    assert "missing.md" in errors[0]
    assert "intro.md, sub/deeper.md" in errors[0]


def test_a_nested_path_naming_nothing_in_an_auto_discovered_part_lists_its_children(
    tmp_path: Path,
) -> None:
    _topic(tmp_path / "part" / "01-intro" / "content.md")
    _write_widget_file(
        tmp_path / "part" / "part.yaml",
        "---\ncontent_type: COURSE_PART\ntitle: A Part\n---\n",
    )
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["missing.md"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "01-intro/content.md" in errors[0]


def test_a_nested_path_naming_a_part_fails(tmp_path: Path) -> None:
    _part_listing(tmp_path / "part" / "part.yaml", ["inner/part.yaml"])
    _part(tmp_path / "part" / "inner" / "part.yaml")
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["inner/part.yaml"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "this child is a COURSE_PART" in errors[0]


def test_a_nested_path_naming_an_activity_fails(tmp_path: Path) -> None:
    _activity(tmp_path / "part" / "act.md")
    _part_listing(tmp_path / "part" / "part.yaml", ["act.md"])
    _course_placing_part(tmp_path / "course.md", "part/part.yaml", ["act.md"])

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "this child is a ACTIVITY" in errors[0]


def test_a_child_named_twice_in_a_nested_list_fails(tmp_path: Path) -> None:
    _topic(tmp_path / "part" / "intro.md")
    _part_listing(tmp_path / "part" / "part.yaml", ["intro.md"])
    _course_placing_part(
        tmp_path / "course.md", "part/part.yaml", ["intro.md", "intro.md"]
    )

    errors = _placement_errors(tmp_path)

    assert len(errors) == 1
    assert "this child is named twice" in errors[0]
    assert "children[0].children[1]" in errors[0]


def test_several_nested_rules_in_one_file_give_one_message_each(tmp_path: Path) -> None:
    _topic(tmp_path / "part" / "intro.md")
    _activity(tmp_path / "part" / "act.md")
    _part_listing(tmp_path / "part" / "part.yaml", ["intro.md", "act.md"])
    _course_placing_part(
        tmp_path / "course.md",
        "part/part.yaml",
        ["missing.md", "act.md", "intro.md", "intro.md"],
    )

    errors = _placement_errors(tmp_path)

    assert len(errors) == 3


def test_auto_discovered_children_skips_what_the_walk_skips(tmp_path: Path) -> None:
    _topic(tmp_path / "01-topic-dir" / "content.md")
    _write_widget_file(
        tmp_path / "02-form-dir" / "form.md",
        "---\ncontent_type: FORM\ntitle: A Form\nstrategy: UNSCORED\n---\n",
    )
    _topic(tmp_path / "03-loose.md")
    _topic(tmp_path / "_draft" / "content.md")
    _write_widget_file(
        tmp_path / "course_categories.yaml",
        "---\ncontent_type: COURSE_CATEGORIES\ncategories:\n  - slug: a\n    title: A\n---\n",
    )
    part_file = _write_widget_file(
        tmp_path / "part.yaml", "---\ncontent_type: COURSE_PART\ntitle: A Part\n---\n"
    )

    found = auto_discovered_children(part_file)

    assert found == [
        (tmp_path / "01-topic-dir" / "content.md").resolve(),
        (tmp_path / "02-form-dir" / "form.md").resolve(),
        (tmp_path / "03-loose.md").resolve(),
    ]
