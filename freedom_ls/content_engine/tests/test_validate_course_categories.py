"""Cross-file validation of a course's `categories`/`dashboard_category` references."""

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.validate import validate


def _write(directory: Path, name: str, content: str) -> None:
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
        _write(
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
        _write(
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
        _write(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write(
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
        _write(
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
        _write(
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
        _write(
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
        _write(
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
        _write(
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
        _write(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write(
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
        _write(
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
        _write(
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
        _write(
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
        _write(
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
        _write(
            course_dir,
            "course.md",
            """---
content_type: COURSE
title: Data Literacy
---
""",
        )
        _write(
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
        _write(
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
        _write(
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
        _write(
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
            _write(
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
        _write(
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
        _write(
            repo_dir,
            "course_categories.yaml",
            """---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""",
        )
        _write(
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
