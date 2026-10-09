"""Tests for the content_save command: loading content files into the database."""

from __future__ import annotations

import io
import re
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml
from PIL import Image

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import override_settings

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import CourseCategoryFactory
from freedom_ls.content_engine.image_cache import CACHE_DIR_NAME
from freedom_ls.content_engine.images import ImageEncodeDecision, ImageEncodeStatus
from freedom_ls.content_engine.management.commands.content_save import (
    PreservingDumper,
    _format_bytes,
    _format_image_decision_line,
    markdown_translate,
    save_content_to_db,
    save_course,
    save_form_content,
    save_form_page,
    save_form_question,
    save_topic,
)
from freedom_ls.content_engine.models import (
    Article,
    ContentCollectionItem,
    Course,
    CourseCategory,
    CoursePart,
    File,
    PriceKind,
    Topic,
)
from freedom_ls.content_engine.validate import parse_single_file
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import Form, FormPage
from freedom_ls.tests.images import (
    break_png_chunk_crc,
    photographic_jpeg_bytes,
    png_bytes,
)

# Loading ARTICLE markdown files from a content repo.


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


@pytest.mark.django_db
def test_image_and_alt_text_are_stored_then_cleared_when_removed(
    site, mock_site_context, tmp_path
):
    file_path = _write_article(
        tmp_path,
        "writing/launch.md",
        "content_type: ARTICLE\ntitle: Launch\npublished_on: 2026-03-04\n"
        "image: photo.png\nimage_alt: A grey square\n",
    )
    save_content_to_db(tmp_path, site.name)
    article = Article.objects.get(site=site)
    assert (article.image, article.image_alt) == ("photo.png", "A grey square")
    uuid = _front_matter(file_path)["uuid"]
    _write_article(
        tmp_path,
        "writing/launch.md",
        f"content_type: ARTICLE\nuuid: {uuid}\ntitle: Launch\n"
        "published_on: 2026-03-04\n",
    )

    save_content_to_db(tmp_path, site.name)

    article = Article.objects.get(site=site)
    assert (article.image, article.image_alt) == ("", "")


@pytest.mark.django_db
def test_course_contents_get_ordered_correctly(site, mock_site_context):
    """Bug: save_content_to_db orders topics and forms incorrectly.
    If we have a folder containing:

    ```
    ├── course.md
    ├── 1. topic.md
    ├── 2. topic.md
    ├── 3. quiz
    │   ├── 1. page.yaml
    │   └── form.md
    ├── 4. topic.md
    ├── 5. quiz
    │   ├── 1. page.yaml
    │   └── form.md
    ```
    then the final course ordering should be:
    1. topic
    2. topic
    3. quiz
    4. topic
    5. quiz

    But currently it's incorrectly:
    1. topic
    2. topic
    4. topic
    3. quiz
    5. quiz
    """
    # SETUP: Create temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()

        # Create course.md
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Test Course
description: A test course
uuid: 00000000-0000-0000-0000-000000000001
---

Test course content
""")

        # Create 1. topic.md
        (course_dir / "1. topic.md").write_text("""---
content_type: TOPIC
title: Topic 1
description: First topic
uuid: 00000000-0000-0000-0000-000000000002
---

Topic 1 content
""")

        # Create 2. topic.md
        (course_dir / "2. topic.md").write_text("""---
content_type: TOPIC
title: Topic 2
description: Second topic
uuid: 00000000-0000-0000-0000-000000000003
---

Topic 2 content
""")

        # Create 3. quiz directory and files
        quiz_3_dir = course_dir / "3. quiz"
        quiz_3_dir.mkdir()
        (quiz_3_dir / "form.md").write_text("""---
content_type: FORM
strategy: QUIZ
title: Quiz 3
uuid: 00000000-0000-0000-0000-000000000004
quiz_show_incorrect: true
quiz_pass_percentage: 70
---
""")
        (quiz_3_dir / "1. page.yaml").write_text("""---
content_type: FORM_PAGE
title: Page 1
description: First page
uuid: 00000000-0000-0000-0000-000000000005
---
question: Test question?
type: multiple_choice
required: true
options:
  - text: Option 1
    value: opt1
    uuid: 00000000-0000-0000-0000-000000000006
  - text: Option 2
    value: opt2
    uuid: 00000000-0000-0000-0000-000000000007
uuid: 00000000-0000-0000-0000-000000000008
""")

        # Create 4. topic.md
        (course_dir / "4. topic.md").write_text("""---
content_type: TOPIC
title: Topic 4
description: Fourth topic
uuid: 00000000-0000-0000-0000-000000000009
---

Topic 4 content
""")

        # Create 5. quiz directory and files
        quiz_5_dir = course_dir / "5. quiz"
        quiz_5_dir.mkdir()
        (quiz_5_dir / "form.md").write_text("""---
content_type: FORM
strategy: QUIZ
title: Quiz 5
uuid: 00000000-0000-0000-0000-00000000000a
quiz_show_incorrect: true
quiz_pass_percentage: 70
---
""")
        (quiz_5_dir / "1. page.yaml").write_text("""---
content_type: FORM_PAGE
title: Page 1
description: First page
uuid: 00000000-0000-0000-0000-00000000000b
---
question: Test question?
type: multiple_choice
required: true
options:
  - text: Option 1
    value: opt1
    uuid: 00000000-0000-0000-0000-00000000000c
  - text: Option 2
    value: opt2
    uuid: 00000000-0000-0000-0000-00000000000d
uuid: 00000000-0000-0000-0000-00000000000e
""")

        # EXECUTE: Save content to database
        save_content_to_db(course_dir, site.name)

        # VERIFY: Get the course and its children in order
        course = Course.objects.get(title="Test Course", site=site)
        children = course.items.all().order_by("order")

        # Should have 5 children
        assert children.count() == 5, f"Expected 5 children, got {children.count()}"

        # Verify the order
        expected_order = [
            ("Topic 1", Topic),
            ("Topic 2", Topic),
            ("Quiz 3", Form),
            ("Topic 4", Topic),
            ("Quiz 5", Form),
        ]

        for i, (expected_title, expected_model) in enumerate(expected_order):
            child_item = children[i]
            # Get the actual content object
            actual_content = child_item.child

            assert child_item.order == i, (
                f"Child {i} should have order={i}, got {child_item.order}"
            )
            assert isinstance(actual_content, expected_model), (
                f"Child {i} should be {expected_model.__name__}, "
                f"got {type(actual_content).__name__}"
            )
            assert actual_content.title == expected_title, (
                f"Child {i} should have title '{expected_title}', "
                f"got '{actual_content.title}'"
            )


@pytest.mark.django_db
def test_directory_topic_is_discovered_as_child(site, mock_site_context):
    """A topic laid out as a directory with a content.md is linked as a child.

    ```
    ├── course.md
    ├── 1. intro/
    │   └── content.md
    ├── 2. topic.md
    ├── 3. quiz/
    │   ├── form.md
    │   └── 1. page.yaml
    ```
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Test Course
description: A test course
uuid: 10000000-0000-0000-0000-000000000001
---

Test course content
""")

        # 1. intro is a directory-based topic with a content.md
        intro_dir = course_dir / "1. intro"
        intro_dir.mkdir()
        (intro_dir / "content.md").write_text("""---
content_type: TOPIC
title: Intro
description: Directory-based topic
uuid: 10000000-0000-0000-0000-000000000002
---

Intro content
""")

        # 2. topic is a flat topic file (still supported)
        (course_dir / "2. topic.md").write_text("""---
content_type: TOPIC
title: Topic 2
description: Flat topic
uuid: 10000000-0000-0000-0000-000000000003
---

Topic 2 content
""")

        # 3. quiz is a form directory
        quiz_dir = course_dir / "3. quiz"
        quiz_dir.mkdir()
        (quiz_dir / "form.md").write_text("""---
content_type: FORM
strategy: QUIZ
title: Quiz 3
uuid: 10000000-0000-0000-0000-000000000004
quiz_show_incorrect: true
quiz_pass_percentage: 70
---
""")
        (quiz_dir / "1. page.yaml").write_text("""---
content_type: FORM_PAGE
title: Page 1
uuid: 10000000-0000-0000-0000-000000000005
---
question: Test question?
type: multiple_choice
required: true
options:
  - text: Option 1
    value: opt1
    uuid: 10000000-0000-0000-0000-000000000006
  - text: Option 2
    value: opt2
    uuid: 10000000-0000-0000-0000-000000000007
uuid: 10000000-0000-0000-0000-000000000008
""")

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="Test Course", site=site)
        children = course.items.all().order_by("order")

        assert children.count() == 3, f"Expected 3 children, got {children.count()}"

        expected_order = [
            ("Intro", Topic),
            ("Topic 2", Topic),
            ("Quiz 3", Form),
        ]
        for i, (expected_title, expected_model) in enumerate(expected_order):
            child_item = children[i]
            actual_content = child_item.child
            assert child_item.order == i
            assert isinstance(actual_content, expected_model)
            assert actual_content.title == expected_title

        # The directory topic's file_path points at its content.md.
        intro = Topic.objects.get(title="Intro", site=site)
        assert intro.file_path == "1. intro/content.md"


@pytest.mark.django_db
def test_directory_topic_local_image_resolves_relative_to_content(
    site, mock_site_context
):
    """An image in a topic's own images/ resolves relative to its content.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Image Course
uuid: 20000000-0000-0000-0000-000000000001
---
""")

        intro_dir = course_dir / "1. intro"
        intro_dir.mkdir()
        (intro_dir / "content.md").write_text("""---
content_type: TOPIC
title: Intro
uuid: 20000000-0000-0000-0000-000000000002
---

<c-picture src="images/pic.svg"></c-picture>
""")
        images_dir = intro_dir / "images"
        images_dir.mkdir()
        (images_dir / "pic.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        )

        save_content_to_db(course_dir, site.name)

        intro = Topic.objects.get(title="Intro", site=site)
        # The src is written relative to content.md; it resolves to the path
        # relative to the course root, which is where the file was uploaded.
        assert (
            intro.calculate_path_from_root("images/pic.svg")
            == "1. intro/images/pic.svg"
        )
        assert File.objects.filter(
            site=site, file_path="1. intro/images/pic.svg"
        ).exists()


@pytest.mark.django_db
def test_course_part_directory_not_mistaken_for_topic(site, mock_site_context):
    """A COURSE_PART directory containing topic files is still discovered as the
    part, regardless of file ordering, and keeps its topics as children.

    ```
    ├── course.md
    ├── 01. Part One/
    │   ├── 01. welcome.md       (flat topic, sorts before part.yaml)
    │   ├── 02. deep/content.md  (directory topic)
    │   └── part.yaml
    ```
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Parts Course
uuid: 30000000-0000-0000-0000-000000000001
---
""")

        part_dir = course_dir / "01. Part One"
        part_dir.mkdir()
        (part_dir / "part.yaml").write_text("""---
content_type: COURSE_PART
title: Part One
uuid: 30000000-0000-0000-0000-000000000002
""")
        (part_dir / "01. welcome.md").write_text("""---
content_type: TOPIC
title: Welcome
uuid: 30000000-0000-0000-0000-000000000003
---

Welcome content
""")
        deep_dir = part_dir / "02. deep"
        deep_dir.mkdir()
        (deep_dir / "content.md").write_text("""---
content_type: TOPIC
title: Going Deeper
uuid: 30000000-0000-0000-0000-000000000004
---

Deep content
""")

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="Parts Course", site=site)
        course_children = course.items.all().order_by("order")
        assert course_children.count() == 1
        part_child = course_children[0].child
        assert isinstance(part_child, CoursePart)
        assert part_child.title == "Part One"

        part = CoursePart.objects.get(title="Part One", site=site)
        part_children = part.items.all().order_by("order")
        assert [c.child.title for c in part_children] == ["Welcome", "Going Deeper"]


def _write_intro_topic_with_image(
    course_dir: Path,
    *,
    course_uuid: str,
    topic_uuid: str,
    image_name: str,
    image_bytes: bytes,
) -> None:
    """A one-topic course whose topic carries a single image in its own images/."""
    course_dir.mkdir()
    (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Image Course
uuid: {course_uuid}
---
""")
    intro_dir = course_dir / "1. intro"
    intro_dir.mkdir()
    (intro_dir / "content.md").write_text(f"""---
content_type: TOPIC
title: Intro
uuid: {topic_uuid}
---

<c-picture src="images/{image_name}"></c-picture>
""")
    images_dir = intro_dir / "images"
    images_dir.mkdir()
    (images_dir / image_name).write_bytes(image_bytes)


def _distinguishable_webp_bytes() -> bytes:
    """A tiny, valid WebP that optimising the JPEG fixture below could never produce."""
    buf = io.BytesIO()
    Image.new("RGB", (3, 3), (1, 2, 3)).save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


@pytest.mark.django_db
def test_jpeg_image_is_stored_as_optimised_webp(site, mock_site_context):
    """A JPEG is re-encoded to WebP; its path and author-facing filename are untouched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="40000000-0000-0000-0000-000000000001",
            topic_uuid="40000000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=photographic_jpeg_bytes(),
        )

        save_content_to_db(course_dir, site.name)

        file_obj = File.objects.get(site=site, file_path="1. intro/images/photo.jpg")
        assert file_obj.mime_type == "image/webp"
        assert file_obj.file.name.endswith(".webp")
        assert file_obj.file_path == "1. intro/images/photo.jpg"
        assert file_obj.original_filename == "photo.jpg"


@pytest.mark.django_db
def test_repeated_save_produces_identical_stored_bytes(site, mock_site_context):
    """The second run serves the cache the first one wrote instead of re-encoding, and the stored bytes match either way."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="41000000-0000-0000-0000-000000000001",
            topic_uuid="41000000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=photographic_jpeg_bytes(),
        )

        save_content_to_db(course_dir, site.name)
        first_bytes = File.objects.get(
            site=site, file_path="1. intro/images/photo.jpg"
        ).file.read()

        save_content_to_db(course_dir, site.name)
        second_bytes = File.objects.get(
            site=site, file_path="1. intro/images/photo.jpg"
        ).file.read()

        assert first_bytes == second_bytes


@pytest.mark.django_db
def test_second_run_serves_a_planted_cache_entry_through_to_storage(
    site, mock_site_context
):
    """Replacing the cached WebP with a distinguishable file proves a hit is served all the way to `File`, not only reconstructed as a decision."""
    jpeg_source = photographic_jpeg_bytes()
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="41100000-0000-0000-0000-000000000001",
            topic_uuid="41100000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=jpeg_source,
        )

        save_content_to_db(course_dir, site.name)

        stored_webp = course_dir / "1. intro" / "images" / CACHE_DIR_NAME / "photo.webp"
        planted = _distinguishable_webp_bytes()
        stored_webp.write_bytes(planted)

        save_content_to_db(course_dir, site.name)

        file_obj = File.objects.get(site=site, file_path="1. intro/images/photo.jpg")
        assert file_obj.file.read() == planted


@pytest.mark.django_db
def test_cache_hit_prints_the_same_image_lines_as_the_first_encode(
    site, mock_site_context, capsys
):
    """A hit reconstructs the same decision a fresh encode produced, so the lines an author reads about the image don't change."""
    jpeg_source = photographic_jpeg_bytes()
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="41200000-0000-0000-0000-000000000001",
            topic_uuid="41200000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=jpeg_source,
        )

        save_content_to_db(course_dir, site.name)
        first_output = capsys.readouterr().out

        save_content_to_db(course_dir, site.name)
        second_output = capsys.readouterr().out

        # The per-image decision and byte-count lines are the ones
        # save_file_to_db indents; the leading action line ("Created" versus
        # "Updated") legitimately differs between the two runs.
        first_image_lines = [
            line for line in first_output.splitlines() if line.startswith("  ")
        ]
        second_image_lines = [
            line for line in second_output.splitlines() if line.startswith("  ")
        ]
        assert first_image_lines
        assert first_image_lines == second_image_lines


@pytest.mark.django_db
def test_only_the_first_run_reports_optimised_files_to_commit(
    site, mock_site_context, capsys
):
    """The commit reminder names _optimised/ only for a run that changed it; an unchanged tree leaves nothing new to commit."""
    jpeg_source = photographic_jpeg_bytes()
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="41300000-0000-0000-0000-000000000001",
            topic_uuid="41300000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=jpeg_source,
        )

        save_content_to_db(course_dir, site.name)
        first_output = capsys.readouterr().out

        save_content_to_db(course_dir, site.name)
        second_output = capsys.readouterr().out

        assert f"{CACHE_DIR_NAME}/" in first_output
        assert f"{CACHE_DIR_NAME}/" not in second_output


@pytest.mark.django_db
def test_upgrade_run_removes_the_superseded_jpg_object_from_storage(
    site, mock_site_context, django_capture_on_commit_callbacks
):
    """A .jpg stored before this feature shipped is gone once a run converts it to .webp."""
    jpeg_source = photographic_jpeg_bytes()
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="42000000-0000-0000-0000-000000000001",
            topic_uuid="42000000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=jpeg_source,
        )

        pre_existing = File.objects.create(
            site=site,
            file_path="1. intro/images/photo.jpg",
            file_type=File.FileType.IMAGE,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
        )
        pre_existing.file.save("photo.jpg", ContentFile(jpeg_source), save=True)
        storage = pre_existing.file.storage
        old_name = pre_existing.file.name

        with django_capture_on_commit_callbacks(execute=True):
            save_content_to_db(course_dir, site.name)

        assert storage.exists(old_name) is False


@pytest.mark.django_db
def test_superseded_jpg_object_survives_a_run_that_never_commits(
    site, mock_site_context, django_capture_on_commit_callbacks
):
    """The superseded object outlives the run itself, so a rollback cannot strand a File row.

    Capturing the callbacks without executing them is the shape of a run
    that raises after this file: save_content_to_db is atomic, so the row
    goes back to naming photo.jpg, and that object has to still be there.
    """
    jpeg_source = photographic_jpeg_bytes()
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="45000000-0000-0000-0000-000000000001",
            topic_uuid="45000000-0000-0000-0000-000000000002",
            image_name="photo.jpg",
            image_bytes=jpeg_source,
        )

        pre_existing = File.objects.create(
            site=site,
            file_path="1. intro/images/photo.jpg",
            file_type=File.FileType.IMAGE,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
        )
        pre_existing.file.save("photo.jpg", ContentFile(jpeg_source), save=True)
        storage = pre_existing.file.storage
        old_name = pre_existing.file.name

        with django_capture_on_commit_callbacks(execute=False):
            save_content_to_db(course_dir, site.name)

        assert storage.exists(old_name) is True


@pytest.mark.django_db
def test_corrupt_image_is_stored_unchanged_and_run_completes(site, mock_site_context):
    """A corrupt image cannot be decoded, so its source bytes are stored as-is and the run does not abort."""
    corrupt = break_png_chunk_crc(png_bytes())
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="43000000-0000-0000-0000-000000000001",
            topic_uuid="43000000-0000-0000-0000-000000000002",
            image_name="broken.png",
            image_bytes=corrupt,
        )

        save_content_to_db(course_dir, site.name)

        file_obj = File.objects.get(site=site, file_path="1. intro/images/broken.png")
        assert file_obj.file.read() == corrupt


@pytest.mark.django_db
def test_svg_image_is_stored_byte_identical(site, mock_site_context):
    """An SVG passes through by suffix alone, byte for byte."""
    svg_bytes = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_intro_topic_with_image(
            course_dir,
            course_uuid="44000000-0000-0000-0000-000000000001",
            topic_uuid="44000000-0000-0000-0000-000000000002",
            image_name="pic.svg",
            image_bytes=svg_bytes,
        )

        save_content_to_db(course_dir, site.name)

        file_obj = File.objects.get(site=site, file_path="1. intro/images/pic.svg")
        assert file_obj.file.read() == svg_bytes


# ---------------------------------------------------------------------------
# Explicit children lists and application forms
# ---------------------------------------------------------------------------


COURSE_UUID = "20000000-0000-0000-0000-000000000001"


def _write_topic(directory: Path, name: str, title: str, uuid: str) -> None:
    (directory / name).write_text(f"""---
content_type: TOPIC
title: {title}
uuid: {uuid}
---

{title} content
""")


def _write_application_form(directory: Path) -> None:
    directory.mkdir()
    (directory / "form.md").write_text("""---
content_type: FORM
strategy: UNSCORED
title: Application form
uuid: 20000000-0000-0000-0000-000000000010
---

Tell us about yourself.
""")
    (directory / "1. about-you.yaml").write_text("""---
content_type: FORM_PAGE
title: About you
uuid: 20000000-0000-0000-0000-000000000011
---
question: What is your name?
type: short_text
required: true
uuid: 20000000-0000-0000-0000-000000000012
""")


@pytest.mark.django_db
def test_an_explicit_children_list_is_honoured_in_the_order_it_names(
    site, mock_site_context
):
    """An author who writes a `children:` list is choosing the order. Resolving
    those paths against the directory that declares them is what makes the list
    usable at all.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()
        _write_topic(
            course_dir, "1. alpha.md", "Alpha", "20000000-0000-0000-0000-000000000002"
        )
        _write_topic(
            course_dir, "2. beta.md", "Beta", "20000000-0000-0000-0000-000000000003"
        )
        (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Ordered Course
uuid: {COURSE_UUID}
children:
  - path: 2. beta.md
  - path: 1. alpha.md
---
""")

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="Ordered Course", site=site)
        titles = [item.child.title for item in course.items.all().order_by("order")]
        assert titles == ["Beta", "Alpha"]


@pytest.mark.django_db
def test_a_children_entry_naming_a_missing_file_fails_the_load(site, mock_site_context):
    """A silently dropped child is a course missing content nobody notices."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()
        _write_topic(
            course_dir, "1. alpha.md", "Alpha", "20000000-0000-0000-0000-000000000002"
        )
        (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Broken Course
uuid: {COURSE_UUID}
children:
  - path: 9. nowhere.md
---
""")

        with pytest.raises(ValueError, match="Broken Course"):
            save_content_to_db(course_dir, site.name)


@pytest.mark.django_db
def test_a_failed_load_leaves_no_course_behind(site, mock_site_context):
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()
        _write_topic(
            course_dir, "1. alpha.md", "Alpha", "20000000-0000-0000-0000-000000000002"
        )
        (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Broken Course
uuid: {COURSE_UUID}
children:
  - path: 9. nowhere.md
---
""")

        with pytest.raises(ValueError, match=re.escape("9. nowhere.md")):
            save_content_to_db(course_dir, site.name)

        assert Course.objects.filter(title="Broken Course").exists() is False


@pytest.mark.django_db
def test_a_course_binds_the_application_form_its_access_config_names(
    site, mock_site_context
):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_application_form(root / "application_form")
        course_dir = root / "gated_course"
        course_dir.mkdir()
        _write_topic(
            course_dir,
            "1. welcome.md",
            "Welcome",
            "20000000-0000-0000-0000-000000000002",
        )
        (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Gated Course
uuid: {COURSE_UUID}
access_config:
  access_type: application_gated
  application_form: ../application_form/form.md
---
""")

        save_content_to_db(root, site.name)

        course = Course.objects.get(title="Gated Course", site=site)
        assert course.application_form == Form.objects.get(title="Application form")


@pytest.mark.django_db
def test_removing_the_access_config_key_unbinds_the_form(site, mock_site_context):
    """Otherwise an author who deletes the line is left with a course still
    demanding an application nothing in the content asks for.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_application_form(root / "application_form")
        course_dir = root / "gated_course"
        course_dir.mkdir()
        course_file = course_dir / "course.md"
        _write_topic(
            course_dir,
            "1. welcome.md",
            "Welcome",
            "20000000-0000-0000-0000-000000000002",
        )
        course_file.write_text(f"""---
content_type: COURSE
title: Gated Course
uuid: {COURSE_UUID}
access_config:
  access_type: application_gated
  application_form: ../application_form/form.md
---
""")
        save_content_to_db(root, site.name)

        course_file.write_text(f"""---
content_type: COURSE
title: Gated Course
uuid: {COURSE_UUID}
access_config:
  access_type: free
---
""")
        save_content_to_db(root, site.name)

        course = Course.objects.get(title="Gated Course", site=site)
        assert course.application_form is None


@pytest.mark.django_db
def test_an_application_form_path_pointing_at_a_topic_fails_the_load(
    site, mock_site_context
):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        course_dir = root / "gated_course"
        course_dir.mkdir()
        _write_topic(
            course_dir,
            "1. welcome.md",
            "Welcome",
            "20000000-0000-0000-0000-000000000002",
        )
        (course_dir / "course.md").write_text(f"""---
content_type: COURSE
title: Gated Course
uuid: {COURSE_UUID}
access_config:
  access_type: application_gated
  application_form: 1. welcome.md
---
""")

        with pytest.raises(ValueError, match="not a loaded FORM"):
            save_content_to_db(root, site.name)


# Loading COURSE_CATEGORIES declarations and course category/dashboard_category references.


def _read_yaml_document(file_path: Path) -> dict:
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    sections = [s.strip() for s in content.split("---") if s.strip()]
    data = yaml.safe_load(sections[0])
    assert isinstance(data, dict)
    return data


@pytest.mark.django_db
def test_uuid_write_back_touches_only_entries_lacking_one(site, mock_site_context):
    """A first load writes a uuid into every entry that lacked one; an untouched second load is byte-identical."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        existing_uuid = "10000000-0000-0000-0000-000000000001"
        (repo_dir / "course_categories.yaml").write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: start-here
    title: Start here
    uuid: {existing_uuid}
  - slug: technical
    title: Technical
""")

        save_content_to_db(repo_dir, site.name)

        first_load_data = _read_yaml_document(repo_dir / "course_categories.yaml")
        entries = first_load_data["categories"]
        assert entries[0]["uuid"] == existing_uuid
        assert entries[0]["slug"] == "start-here"
        assert entries[1]["uuid"] is not None
        assert entries[1]["slug"] == "technical"

        first_load_bytes = (repo_dir / "course_categories.yaml").read_bytes()

        save_content_to_db(repo_dir, site.name)

        second_load_bytes = (repo_dir / "course_categories.yaml").read_bytes()
        assert second_load_bytes == first_load_bytes
        assert CourseCategory.objects.filter(site=site).count() == 2


@pytest.mark.django_db
def test_authored_slug_survives_a_title_edit(site, mock_site_context):
    """A category's authored slug is not re-derived from its title, unlike every other content type."""
    category_uuid = "20000000-0000-0000-0000-000000000001"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical Skills
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical Skills, Revised
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        category = CourseCategory.objects.get(site=site, id=category_uuid)
        assert category.slug == "technical"
        assert category.title == "Technical Skills, Revised"
        assert CourseCategory.objects.filter(site=site).count() == 1


@pytest.mark.django_db
def test_slug_rename_on_a_fixed_uuid_renames_the_row(site, mock_site_context):
    """Renaming an entry's slug while its uuid stays put renames the existing row rather than creating a second."""
    category_uuid = "30000000-0000-0000-0000-000000000001"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: engineering
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        assert CourseCategory.objects.filter(site=site).count() == 1
        category = CourseCategory.objects.get(site=site, id=category_uuid)
        assert category.slug == "engineering"


@pytest.mark.django_db
def test_order_follows_list_position_and_changes_on_reorder(site, mock_site_context):
    first_uuid = "40000000-0000-0000-0000-000000000001"
    second_uuid = "40000000-0000-0000-0000-000000000002"
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: alpha
    title: Alpha
    uuid: {first_uuid}
  - slug: beta
    title: Beta
    uuid: {second_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        alpha = CourseCategory.objects.get(site=site, id=first_uuid)
        beta = CourseCategory.objects.get(site=site, id=second_uuid)
        assert alpha.order == 0
        assert beta.order == 1

        categories_file.write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: beta
    title: Beta
    uuid: {second_uuid}
  - slug: alpha
    title: Alpha
    uuid: {first_uuid}
""")
        save_content_to_db(repo_dir, site.name)

        alpha.refresh_from_db()
        beta.refresh_from_db()
        assert beta.order == 0
        assert alpha.order == 1


@pytest.mark.django_db
def test_single_category_shorthand_loads_both_fields(site, mock_site_context):
    """A course declaring one category and no dashboard_category loads with both set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
uuid: 50000000-0000-0000-0000-000000000001
---
""")

        save_content_to_db(repo_dir, site.name)

        course = Course.objects.get(site=site, title="Demo Course")
        assert [c.slug for c in course.categories.all()] == ["technical"]
        assert course.dashboard_category.slug == "technical"


@pytest.mark.django_db
def test_dropping_a_category_slug_and_reloading_removes_that_membership(
    site, mock_site_context
):
    """A course's category set is replaced by a reload, not merged into."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
  - slug: start-here
    title: Start here
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
  - start-here
dashboard_category: technical
uuid: 60000000-0000-0000-0000-000000000001
---
""")
        save_content_to_db(repo_dir, site.name)
        course = Course.objects.get(site=site, title="Demo Course")
        assert {c.slug for c in course.categories.all()} == {"technical", "start-here"}

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
dashboard_category: technical
uuid: 60000000-0000-0000-0000-000000000001
---
""")
        save_content_to_db(repo_dir, site.name)
        course.refresh_from_db()
        assert {c.slug for c in course.categories.all()} == {"technical"}


@pytest.mark.django_db
def test_loose_category_file_in_a_course_directory_is_not_adopted_as_a_child(
    site, mock_site_context
):
    """save_content_to_db called directly does not adopt a stray category file as a course child."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
uuid: 70000000-0000-0000-0000-000000000001
---
""")
        (course_dir / "1. topic.md").write_text("""---
content_type: TOPIC
title: Topic One
uuid: 70000000-0000-0000-0000-000000000002
---

Topic content
""")
        # A loose declaration file, inside the course directory rather than
        # the repo root -- content_validate rejects this location (step 4),
        # but save_content_to_db is also called directly and must not treat
        # it as a child of the course it happens to sit beside.
        (course_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(site=site, title="Demo Course")
        children_titles = [item.child.title for item in course.items.all()]
        assert children_titles == ["Topic One"]
        # The category row is still saved -- only child adoption is skipped.
        assert CourseCategory.objects.filter(site=site, slug="technical").exists()


@pytest.mark.django_db
def test_a_failure_later_in_the_load_leaves_no_course_with_a_partial_category_set(
    site, mock_site_context, mocker
):
    """save_content_to_db is atomic: a failure anywhere rolls back every category assignment too."""
    mocker.patch.object(
        ContentCollectionItem.objects,
        "update_or_create",
        side_effect=RuntimeError("forced failure for the atomicity test"),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
""")
        course_dir = repo_dir / "demo_course"
        course_dir.mkdir()
        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Demo Course
categories:
  - technical
uuid: 80000000-0000-0000-0000-000000000001
---
""")
        (course_dir / "1. topic.md").write_text("""---
content_type: TOPIC
title: Topic One
uuid: 80000000-0000-0000-0000-000000000002
---

Topic content
""")

        with pytest.raises(RuntimeError):
            save_content_to_db(repo_dir, site.name)

        assert not Course.objects.filter(site=site).exists()
        assert not CourseCategory.objects.filter(site=site).exists()


@pytest.mark.django_db
def test_two_sites_get_their_own_rows_reusing_slugs_and_titles():
    """Two sites with their own declarations, reusing each other's slugs, get their own rows."""
    site_a = SiteFactory()
    site_b = SiteFactory()

    with tempfile.TemporaryDirectory() as tmpdir_a:
        repo_a = Path(tmpdir_a)
        (repo_a / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical (Site A)
""")
        save_content_to_db(repo_a, site_a.name)

    with tempfile.TemporaryDirectory() as tmpdir_b:
        repo_b = Path(tmpdir_b)
        (repo_b / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical (Site B)
""")
        save_content_to_db(repo_b, site_b.name)

    category_a = CourseCategory._base_manager.get(site=site_a, slug="technical")
    category_b = CourseCategory._base_manager.get(site=site_b, slug="technical")
    assert category_a.id != category_b.id
    assert category_a.title == "Technical (Site A)"
    assert category_b.title == "Technical (Site B)"
    assert CourseCategory._base_manager.filter(site=site_b).count() == 1


@pytest.mark.django_db
def test_loading_one_declaration_into_two_sites_fails_on_duplicate_primary_key():
    """Pinning a pre-existing limit of the content loader: a shared uuid cannot serve two sites in one database."""
    site_a = SiteFactory()
    site_b = SiteFactory()
    category_uuid = "90000000-0000-0000-0000-000000000001"

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text(f"""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Technical
    uuid: {category_uuid}
""")
        save_content_to_db(repo_dir, site_a.name)

        with pytest.raises(IntegrityError):
            save_content_to_db(repo_dir, site_b.name)


def _read_category_entries(file_path: Path) -> list[dict]:
    documents = list(yaml.safe_load_all(file_path.read_text(encoding="utf-8")))
    assert len(documents) == 1
    entries = documents[0]["categories"]
    assert isinstance(entries, list)
    return entries


@pytest.mark.django_db
def test_triple_dash_inside_a_description_loads_the_whole_description(
    site, mock_site_context
):
    """A `---` in a value is prose, not a document separator: the row keeps the full description."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: reference
    title: Reference
    description: Deep dive --- for advanced learners.
    uuid: a0000000-0000-0000-0000-000000000001
""")

        save_content_to_db(repo_dir, site.name)

        category = CourseCategory.objects.get(site=site, slug="reference")
        assert category.description == "Deep dive --- for advanced learners."


@pytest.mark.django_db
def test_uuid_write_back_keeps_a_description_containing_a_triple_dash(
    site, mock_site_context
):
    """Minting a uuid must not split the file at a `---` that sits inside a value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        categories_file = repo_dir / "course_categories.yaml"
        categories_file.write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: reference
    title: Reference
    description: Deep dive --- for advanced learners.
""")

        save_content_to_db(repo_dir, site.name)

        entries = _read_category_entries(categories_file)
        assert entries[0]["description"] == "Deep dive --- for advanced learners."
        assert entries[0]["uuid"] is not None


@pytest.mark.django_db
def test_uuid_less_entry_whose_slug_is_taken_on_the_site_is_refused_with_an_authoring_error(
    site, mock_site_context
):
    """A slug already owned by another row on this site is an authoring error naming the slug, file and owning uuid."""
    existing = CourseCategoryFactory(site=site, slug="start-here", title="Start here")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: start-here
    title: Start here, again
""")

        with pytest.raises(ValueError, match="start-here") as excinfo:
            save_content_to_db(repo_dir, site.name)

    message = str(excinfo.value)
    assert "course_categories.yaml" in message
    assert str(existing.id) in message
    existing.refresh_from_db()
    assert existing.title == "Start here"
    assert CourseCategory.objects.filter(site=site).count() == 1


@pytest.mark.django_db
def test_uuid_entry_renamed_onto_a_slug_owned_by_another_row_is_refused(
    site, mock_site_context
):
    """Renaming an entry onto a slug that a different uuid owns is refused rather than overwriting that row."""
    CourseCategoryFactory(site=site, slug="technical", title="Technical")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        (repo_dir / "course_categories.yaml").write_text("""---
content_type: COURSE_CATEGORIES
categories:
  - slug: technical
    title: Engineering
    uuid: b0000000-0000-0000-0000-000000000001
""")

        with pytest.raises(ValueError, match="technical"):
            save_content_to_db(repo_dir, site.name)

    assert CourseCategory.objects.get(site=site, slug="technical").title == "Technical"


# Tests for the `price:` frontmatter field going through `save_course`.


def _save(make_temp_file, mock_site_context, content: str) -> Course:
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)
    return cast(Course, Course.objects.get(site=mock_site_context, title=item.title))


# ---------------------------------------------------------------------------
# Each kind saves
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fixed_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Fixed Price Save Course
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_range_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Range Price Save Course
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("1200.00")
    assert course.price_high_amount == Decimal("3000.00")


@pytest.mark.django_db
def test_discounted_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: Discounted Price Save Course
price:
  kind: discounted
  amount: "1499.00"
  sale_amount: "999.00"
  sale_ends_on: 2026-12-31
  currency: ZAR
  tax_note: incl. VAT
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.DISCOUNTED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_sale_amount == Decimal("999.00")
    assert course.price_sale_ends_on == date(2026, 12, 31)
    assert course.price_tax_note == "incl. VAT"


@pytest.mark.django_db
def test_on_request_price_saves(make_temp_file, mock_site_context) -> None:
    content = """---
content_type: COURSE
title: On Request Price Save Course
price:
  kind: on_request
---
"""
    course = _save(make_temp_file, mock_site_context, content)

    assert course.price_kind == PriceKind.ON_REQUEST
    assert course.price_currency == ""


# ---------------------------------------------------------------------------
# Switching kind clears stale columns
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_switching_from_range_to_fixed_clears_low_and_high_amounts(
    make_temp_file, mock_site_context
) -> None:
    range_content = """---
content_type: COURSE
title: Switching Kind Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000010
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    temp_file = make_temp_file(".md", range_content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="Switching Kind Course")
    assert course.price_low_amount == Decimal("1200.00")

    fixed_content = """---
content_type: COURSE
title: Switching Kind Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000010
price:
  kind: fixed
  amount: "1499.00"
  currency: ZAR
---
"""
    temp_file_2 = make_temp_file(".md", fixed_content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("1499.00")
    assert course.price_low_amount is None
    assert course.price_high_amount is None


@pytest.mark.django_db
def test_dropping_high_amount_makes_the_range_open_ended(
    make_temp_file, mock_site_context
) -> None:
    closed = """---
content_type: COURSE
title: Opening Range Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000020
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
"""
    open_ended = """---
content_type: COURSE
title: Opening Range Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000020
price:
  kind: range
  low_amount: "1200.00"
  currency: ZAR
---
"""
    _save(make_temp_file, mock_site_context, closed)
    course = _save(make_temp_file, mock_site_context, open_ended)

    assert course.price_kind == PriceKind.RANGE
    assert course.price_low_amount == Decimal("1200.00")
    assert course.price_high_amount is None


# ---------------------------------------------------------------------------
# Absent price: leaves the stored value; `price: null` clears it
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_absent_price_key_keeps_an_admin_set_price(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: No Price Key Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000011
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="No Price Key Course")
    course.price_kind = PriceKind.FIXED
    course.price_amount = Decimal("500.00")
    course.price_currency = "ZAR"
    course.save()

    temp_file_2 = make_temp_file(".md", content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == PriceKind.FIXED
    assert course.price_amount == Decimal("500.00")


@pytest.mark.django_db
def test_explicit_null_price_clears_all_eight_columns(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: Null Price Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000012
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)
    save_course(item, mock_site_context, temp_file.parent)

    course = Course.objects.get(site=mock_site_context, title="Null Price Course")
    course.price_kind = PriceKind.FIXED
    course.price_amount = Decimal("500.00")
    course.price_currency = "ZAR"
    course.save()

    null_price_content = """---
content_type: COURSE
title: Null Price Course
uuid: aaaaaaaa-bbbb-cccc-dddd-000000000012
price: null
---
"""
    temp_file_2 = make_temp_file(".md", null_price_content)
    (item_2,) = parse_single_file(temp_file_2)
    save_course(item_2, mock_site_context, temp_file_2.parent)

    course.refresh_from_db()
    assert course.price_kind == ""
    assert course.price_amount is None
    assert course.price_sale_amount is None
    assert course.price_sale_ends_on is None
    assert course.price_low_amount is None
    assert course.price_high_amount is None
    assert course.price_currency == ""
    assert course.price_tax_note == ""


# ---------------------------------------------------------------------------
# Currency resolution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_blank_currency_takes_default_currency(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: Default Currency Save Course
price:
  kind: fixed
  amount: "1499.00"
---
"""
    with override_settings(DEFAULT_CURRENCY="ZAR"):
        course = _save(make_temp_file, mock_site_context, content)

    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_missing_currency_with_no_default_raises_naming_the_file(
    make_temp_file, mock_site_context
) -> None:
    content = """---
content_type: COURSE
title: No Currency No Default Course
price:
  kind: fixed
  amount: "1499.00"
---
"""
    temp_file = make_temp_file(".md", content)
    (item,) = parse_single_file(temp_file)

    with (
        override_settings(DEFAULT_CURRENCY=None),
        pytest.raises(ValueError, match="DEFAULT_CURRENCY is not set") as excinfo,
    ):
        save_course(item, mock_site_context, temp_file.parent)

    assert str(temp_file) in str(excinfo.value)


# Unit tests for content_save's author-facing image formatting helpers.
#
# No database: both helpers take plain values, and the decisions here are
# constructed by hand rather than run through `optimise_image`.


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1024, "1.0 KB"),
        (10240, "10 KB"),
        (120832, "118 KB"),
        (421888, "412 KB"),
        (5348147, "5.1 MB"),
        (2147483648, "2.0 GB"),
    ],
    ids=[
        "zero_bytes",
        "just_under_a_kb",
        "exactly_one_kb",
        "ten_kb_no_decimal",
        "118_kb",
        "412_kb",
        "5_point_1_mb",
        "two_gb",
    ],
)
def test_format_bytes_renders_human_readable_size(num_bytes, expected):
    assert _format_bytes(num_bytes) == expected


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.OPTIMISED,
                source_format="JPEG",
                source_size=(4032, 3024),
                data=b"x",
                suffix=".webp",
                mime_type="image/webp",
                lossless=False,
                stored_size=(1600, 1200),
                error=None,
            ),
            "JPEG 4032x3024 -> WebP lossy 1600x1200",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.OPTIMISED,
                source_format="PNG",
                source_size=(1840, 1120),
                data=b"x",
                suffix=".webp",
                mime_type="image/webp",
                lossless=True,
                stored_size=(1600, 974),
                error=None,
            ),
            "PNG 1840x1120 -> WebP lossless 1600x974",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.PASSTHROUGH,
                source_format="SVG",
                source_size=None,
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "SVG, passthrough.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.PASSTHROUGH,
                source_format="GIF",
                source_size=(800, 600),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "GIF 800x600, passthrough.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.KEPT_SOURCE,
                source_format="PNG",
                source_size=(200, 120),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error=None,
            ),
            "PNG 200x120, re-encode not smaller, kept source.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.UNDECODABLE,
                source_format=None,
                source_size=None,
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error="ValueError: not enough image data",
            ),
            "could not decode.",
        ),
        (
            ImageEncodeDecision(
                status=ImageEncodeStatus.UNDECODABLE,
                source_format="PNG",
                source_size=(100, 100),
                data=None,
                suffix=None,
                mime_type=None,
                lossless=None,
                stored_size=None,
                error="SyntaxError: broken PNG file",
            ),
            "PNG 100x100, could not decode.",
        ),
    ],
    ids=[
        "optimised_lossy_jpeg",
        "optimised_lossless_png",
        "passthrough_svg_no_dimensions",
        "passthrough_animated_gif_with_dimensions",
        "kept_source_names_the_reason",
        "undecodable_before_format_known",
        "undecodable_after_format_known",
    ],
)
def test_format_image_decision_line_from_decision_alone(decision, expected):
    assert _format_image_decision_line(decision) == expected


# Test UUID handling in content_save.py


def test_preserving_dumper_uses_literal_style_for_html_content():
    """Test that PreservingDumper correctly uses literal block style for multi-line strings with HTML.

    This tests whether the custom YAML dumper properly handles strings containing:
    - Newlines
    - HTML/XML tags with angle brackets
    - Quoted attributes

    The dumper should output these using literal block style (|) not quoted strings.
    """
    # Create content similar to what's in the demo file
    content_with_html = (
        "Considering blah blah, answer the following:\n"
        "<c-picture  \n"
        '   src="../images/graph1.drawio.svg"\n'
        '   alt="Graph example"\n'
        '   title="Example of a graph"\n'
        "   />\n"
        "  Blah blah"
    )

    data = {
        "content_type": "FORM_CONTENT",
        "content": content_with_html,
        "uuid": "9c4265c5-9178-47b8-9a9d-074e69e34a40",
    }

    # Dump using PreservingDumper
    result = yaml.dump(
        data, Dumper=PreservingDumper, default_flow_style=False, allow_unicode=True
    )

    # THE BUG: PreservingDumper should use literal block style (|) for multi-line strings,
    # but it's actually outputting quoted strings with \n escapes instead!
    assert "content: |" in result, (
        f"PreservingDumper should use literal block style (|) for multi-line strings.\n"
        f"Instead it's using quoted strings with \\n escapes.\n"
        f"Got:\n{result}"
    )

    # Should NOT use quoted string format
    assert 'content: "' not in result, (
        f"Content should not use quoted string format.\nGot:\n{result}"
    )

    # HTML tags should appear literally, not escaped
    assert "<c-picture" in result
    assert 'src="../images/graph1.drawio.svg"' in result


@pytest.mark.django_db
def test_form_page_with_uuid_no_duplicates_on_multiple_saves(
    mock_site_context, make_temp_file
):
    """Test that saving a FormPage with same UUID multiple times doesn't create duplicates."""
    form = FormFactory()

    # Create a temporary yaml file for a FormPage without UUID
    yaml_content = {
        "content_type": "FORM_PAGE",
        "title": "Test Form Page",
        "subtitle": "Test Subtitle",
    }
    file_content = "---\n" + yaml.dump(yaml_content)
    temp_file = make_temp_file(suffix=".yaml", content=file_content)

    # Parse and save the first time
    parsed_items = parse_single_file(temp_file)
    assert len(parsed_items) == 1
    item1 = parsed_items[0]

    # Verify no UUID initially
    assert item1.uuid is None

    # Save to database (should create UUID and update file)
    initial_count = FormPage.objects.count()
    page1 = save_form_page(item1, form, mock_site_context, temp_file.parent, order=0)

    assert FormPage.objects.count() == initial_count + 1
    created_uuid = page1.id

    # Verify file was updated with UUID
    with open(temp_file) as f:
        updated_content = yaml.safe_load(f.read().split("---")[1])
        assert "uuid" in updated_content
        assert updated_content["uuid"] == str(created_uuid)

    # Parse the file again (should now have UUID)
    parsed_items2 = parse_single_file(temp_file)
    assert len(parsed_items2) == 1
    item2 = parsed_items2[0]

    # Verify UUID is now present
    assert item2.uuid is not None
    assert item2.uuid == str(created_uuid)

    # Save again (should update, not create new)
    page2 = save_form_page(item2, form, mock_site_context, temp_file.parent, order=0)

    # Assert UUID unchanged and no duplicates
    assert FormPage.objects.count() == initial_count + 1
    assert page2.id == created_uuid

    # Verify file UUID hasn't changed
    with open(temp_file) as f:
        final_content = yaml.safe_load(f.read().split("---")[1])
        assert final_content["uuid"] == str(created_uuid)


@pytest.mark.django_db
def test_saving_form_questions_and_text_adds_uuids_to_file(
    mock_site_context, make_temp_file
):
    """Test that saving form questions and text adds UUIDs to the file."""
    form = FormFactory()

    # Create YAML with form page, question, and text
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_QUESTION
question: What is your favorite color?
type: multiple_choice
required: true
options:
  - text: Red
    value: 1
  - text: Blue
    value: 2
---
content_type: FORM_CONTENT
content: This is some instructional text
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse and save
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 3

    # Verify no UUIDs initially
    assert parsed[0].uuid is None
    assert parsed[1].uuid is None
    assert parsed[2].uuid is None

    # Save to database

    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    question = save_form_question(
        parsed[1], page, mock_site_context, temp_file.parent, order=0
    )
    text = save_form_content(
        parsed[2], page, mock_site_context, temp_file.parent, order=1
    )

    # Read file back
    with open(temp_file) as f:
        result = f.read()

    # Parse sections
    sections = result.split("---")[1:]  # Skip empty first element
    page_data = yaml.safe_load(sections[0])
    question_data = yaml.safe_load(sections[1])
    text_data = yaml.safe_load(sections[2])

    # Verify UUIDs were added
    assert "uuid" in page_data
    assert page_data["uuid"] == str(page.id)

    assert "uuid" in question_data
    assert question_data["uuid"] == str(question.id)

    assert "uuid" in text_data
    assert text_data["uuid"] == str(text.id)

    # Verify original content is preserved
    assert page_data["title"] == "Test Page"
    assert question_data["question"] == "What is your favorite color?"
    assert question_data["type"] == "multiple_choice"
    assert len(question_data["options"]) == 2
    assert text_data["content"] == "This is some instructional text"


@pytest.mark.django_db
def test_saving_form_question_options_saves_uuids_to_file(
    mock_site_context, make_temp_file
):
    """Test that saving a form question with options preserves the options correctly and adds UUID."""
    form = FormFactory()

    # Create YAML with form page and question with options
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_QUESTION
question: What is your favorite programming language?
type: multiple_choice
required: true
category: Programming
options:
  - text: Python
    value: 1
  - text: JavaScript
    value: 2
  - text: Rust
    value: 3
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse and save
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 2

    # Verify no UUIDs initially
    assert parsed[0].uuid is None
    assert parsed[1].uuid is None

    # Save to database
    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    question = save_form_question(
        parsed[1], page, mock_site_context, temp_file.parent, order=0
    )

    # Read file back
    with open(temp_file) as f:
        result = f.read()

    # Parse sections
    sections = result.split("---")[1:]  # Skip empty first element
    # page_data = yaml.safe_load(sections[0])
    question_data = yaml.safe_load(sections[1])

    # Verify UUIDs were added
    # OPTIONS DO HAVE UUIDS
    # Get the options from the database
    from freedom_ls.form_engine.models import QuestionOption

    db_options = list(
        QuestionOption.objects.filter(question=question).order_by("order")
    )

    # Assert each option has the correct UUID matching the database
    assert len(question_data["options"]) == len(db_options)
    for idx, option in enumerate(question_data["options"]):
        assert "uuid" in option
        assert option["uuid"] == str(db_options[idx].id)


@pytest.mark.django_db
def test_yaml_dump_does_not_add_excessive_whitespace(mock_site_context, make_temp_file):
    """Test that yaml.dump doesn't add blank lines when updating multi-document file with UUIDs."""
    form = FormFactory()

    # Create original multi-document YAML with specific compact format
    original_yaml = "---\ncontent_type: FORM_PAGE\ntitle: Test Page\n---\ncontent_type: FORM_CONTENT\ncontent: Some text\n"
    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save to add UUIDs
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    save_form_content(parsed[1], page, mock_site_context, temp_file.parent, order=0)

    # Read back
    with open(temp_file) as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]  # Skip empty first element
    section1_data = yaml.safe_load(sections[0])
    section2_data = yaml.safe_load(sections[1])

    # Expected: compact YAML with no blank lines
    expected_result = f"---\ncontent_type: FORM_PAGE\ntitle: Test Page\nuuid: {section1_data['uuid']}\n---\ncontent: Some text\ncontent_type: FORM_CONTENT\nuuid: {section2_data['uuid']}\n"

    assert result == expected_result, (
        f"YAML formatting incorrect.\nExpected:\n{expected_result!r}\nGot:\n{result!r}"
    )


@pytest.mark.django_db
def test_yaml_dump_doesnt_reformat_multi_line_text_fields(
    mock_site_context, make_temp_file
):
    """Test that yaml.dump preserves multi-line text formatting."""
    form = FormFactory()

    # Create YAML with multi-line text field
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_CONTENT
content: |
  hello there
  this is a multi-line
  string
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save the content
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    save_form_content(parsed[1], page, mock_site_context, temp_file.parent, order=0)

    # Read back
    with open(temp_file) as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]
    section2_data = yaml.safe_load(sections[1])

    # Verify multi-line text is preserved (using literal block style, not quoted)
    # Accept both | and |- as valid literal block styles
    assert "content: |" in result, (
        f"Multi-line text should use literal block style (|), got:\n{result!r}"
    )

    # Verify the parsed content is correct (multi-line text preserved)
    # Note: |- style strips trailing newline, which is acceptable
    assert (
        section2_data["content"]
        in [
            "hello there\nthis is a multi-line\nstring\n",  # | style (keeps trailing newline)
            "hello there\nthis is a multi-line\nstring",  # |- style (strips trailing newline)
        ]
    ), f"Multi-line text content incorrect: {section2_data['content']!r}"

    # Verify no extra blank lines were added (should have exactly 2 sections)
    assert len([s for s in sections if s.strip()]) == 2, (
        "Should have exactly 2 YAML sections"
    )


@pytest.mark.django_db
def test_yaml_dump_preserves_multi_line_content_with_html_tags(
    mock_site_context, make_temp_file
):
    """Test that yaml.dump preserves multi-line text with HTML/XML tags using literal block style.

    This tests the bug where content with HTML tags gets converted from:
        content: |
          Text here
          <c-picture src="..." />
          More text

    To the incorrect format:
        content: "Text here\\n<c-picture src=\\"...\\" />\\nMore text"
    """
    form = FormFactory()

    # Create YAML with multi-line content containing HTML-like tags
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
---
content_type: FORM_CONTENT
content: |
  Considering blah blah, answer the following:
  <c-picture
     src="../images/graph1.drawio.svg"
     alt="Graph example"
     title="Example of a graph"
     />
  Blah blah
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Save the content
    parsed = parse_single_file(temp_file)
    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    save_form_content(parsed[1], page, mock_site_context, temp_file.parent, order=0)

    # Read back
    with open(temp_file) as f:
        result = f.read()

    # Parse to get UUIDs
    sections = result.split("---")[1:]
    section2_data = yaml.safe_load(sections[1])

    # The key assertion: multi-line content with HTML tags should NOT be quoted
    # It should use the literal block style (|)
    assert "content: |" in result, (
        f"Multi-line text with HTML tags should use literal block style (|), "
        f"not quoted strings with \\n escapes.\nGot:\n{result!r}"
    )

    # Verify it does NOT use the incorrect quoted format with \n escapes
    assert 'content: "' not in result, (
        f"Content should not use quoted string format with \\n escapes.\nGot:\n{result!r}"
    )

    # Verify the actual HTML tag is preserved on its own lines, not escaped
    assert "<c-picture" in result, (
        f"HTML tag should be preserved literally, not escaped.\nGot:\n{result!r}"
    )
    assert 'src="../images/graph1.drawio.svg"' in result, (
        f"HTML attributes should be preserved literally.\nGot:\n{result!r}"
    )

    # Verify the parsed content is correct (newlines preserved, not escaped)
    # The content should contain the HTML tag and newlines should be actual newlines, not \n escapes
    assert "Considering blah blah, answer the following:" in section2_data["content"]
    assert "<c-picture" in section2_data["content"]
    assert 'src="../images/graph1.drawio.svg"' in section2_data["content"]
    assert "Blah blah" in section2_data["content"]

    # Most importantly, verify that newlines in the content are real newlines
    # If they were escaped as \n, the parsed content wouldn't have real newlines
    assert "\n" in section2_data["content"], (
        f"Content should contain actual newlines, not escaped \\n sequences.\n"
        f"Got:\n{section2_data['content']!r}"
    )


@pytest.mark.django_db
def test_updating_question_options_preserves_other_sections_multi_line_format(
    mock_site_context, make_temp_file
):
    """Test that adding UUIDs to question options preserves multi-line formatting in other sections.

    This exposes the REAL bug! When update_file_with_option_uuids is called:
    1. It reads the entire file and splits all sections
    2. It strips all sections: `sections = [s.strip() for s in sections]`
    3. It finds the question section and re-dumps it with option UUIDs
    4. It reconstructs the ENTIRE file from the sections list

    The problem: Other sections that have `content: |` multi-line formatting
    are NOT re-dumped, they're just the stripped original text. But when the
    file is reconstructed, those sections are embedded in a fresh yaml.dump()
    of the ENTIRE sections list... NO WAIT, that's not right.

    Actually looking at the code more carefully - it joins the sections as strings,
    not as yaml objects. So the sections that weren't touched should retain their
    format. Unless...

    The bug must be that PreservingDumper is NOT properly preserving multi-line
    strings with special characters like < and >.
    """
    form = FormFactory()

    # Create YAML where question has UUID but options don't, and there's
    # multi-line content in another section
    original_yaml = """---
content_type: FORM_PAGE
title: Test Page
uuid: d5f43271-9465-496d-925d-61118963ad9e
---
content_type: FORM_CONTENT
content: |
  Considering blah blah, answer the following:
  <c-picture
     src="../images/graph1.drawio.svg"
     alt="Graph example"
     title="Example of a graph"
     />
  Blah blah
uuid: 9c4265c5-9178-47b8-9a9d-074e69e34a40
---
content_type: FORM_QUESTION
question: What is your answer?
type: multiple_choice
required: true
uuid: 5e8405d4-2333-49cb-b4fd-9406d3f64b9c
options:
  - text: Option A
    value: a
  - text: Option B
    value: b
"""

    temp_file = make_temp_file(suffix=".yaml", content=original_yaml)

    # Parse
    parsed = parse_single_file(temp_file)
    assert len(parsed) == 3

    # All have UUIDs except the options
    assert parsed[0].uuid == "d5f43271-9465-496d-925d-61118963ad9e"
    assert parsed[1].uuid == "9c4265c5-9178-47b8-9a9d-074e69e34a40"
    assert parsed[2].uuid == "5e8405d4-2333-49cb-b4fd-9406d3f64b9c"
    assert all(opt.uuid is None for opt in parsed[2].options)

    # Save to database - the question has UUID but options don't,
    # so update_file_with_option_uuids will be called
    page = save_form_page(parsed[0], form, mock_site_context, temp_file.parent, order=0)
    save_form_content(parsed[1], page, mock_site_context, temp_file.parent, order=0)
    save_form_question(parsed[2], page, mock_site_context, temp_file.parent, order=1)

    # Read the file back
    with open(temp_file) as f:
        result = f.read()

    # THE BUG: The FormContent section should STILL have literal block style
    assert "content: |" in result, (
        f"Multi-line text with HTML tags should use literal block style (|), "
        f"but got quoted strings with \\n escapes instead.\nGot:\n{result!r}"
    )

    # Verify it does NOT use the incorrect quoted format with \n escapes
    assert 'content: "' not in result, (
        f"Content should not use quoted string format with \\n escapes.\nGot:\n{result!r}"
    )

    # Verify the actual HTML tag is preserved on its own lines, not escaped
    assert "<c-picture" in result, (
        f"HTML tag should be preserved literally, not escaped.\nGot:\n{result!r}"
    )
    assert 'src="../images/graph1.drawio.svg"' in result, (
        f"HTML attributes should be preserved literally.\nGot:\n{result!r}"
    )


def test_markdown_translate_shorthand_with_title_emits_title_attr():
    """markdown_translate converts ![[file|text]] to c-picture with a title attr, no caption."""
    result = markdown_translate("![[graph.png | Example of a graph]]")
    assert 'title="Example of a graph"' in result
    assert "caption=" not in result
    assert '<c-picture src="graph.png"' in result


def test_markdown_translate_shorthand_without_title_emits_no_title_attr():
    """markdown_translate converts ![[file]] to c-picture without a title attribute."""
    result = markdown_translate("![[graph.png]]")
    assert "caption=" not in result
    assert "title=" not in result
    assert '<c-picture src="graph.png"' in result


def test_markdown_translate_strips_whitespace_around_title():
    """markdown_translate trims whitespace from the title slot."""
    result = markdown_translate("![[graph.png |  Some title  ]]")
    assert 'title="Some title"' in result


# Tests for Form.submit_on_exit schema (content-loading) validation.


def _write_quiz_course(course_dir: Path, *, submit_on_exit_line: str) -> None:
    """Write a minimal quiz course whose form.md frontmatter optionally carries
    a ``submit_on_exit`` line (``submit_on_exit_line`` is inserted verbatim
    before the closing ``---``; pass "" to omit the key entirely)."""
    course_dir.mkdir()
    (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Submit On Exit Course
description: A test course
uuid: aaaaaaaa-0000-0000-0000-000000000001
---
""")

    quiz_dir = course_dir / "1. quiz"
    quiz_dir.mkdir()
    (quiz_dir / "form.md").write_text(f"""---
content_type: FORM
strategy: QUIZ
title: Submit On Exit Quiz
uuid: aaaaaaaa-0000-0000-0000-000000000002
quiz_show_incorrect: true
quiz_pass_percentage: 70
{submit_on_exit_line}---
""")
    (quiz_dir / "1. page.yaml").write_text("""---
content_type: FORM_PAGE
title: Page 1
uuid: aaaaaaaa-0000-0000-0000-000000000003
---
question: Test question?
type: multiple_choice
required: true
options:
  - text: Option 1
    value: opt1
    uuid: aaaaaaaa-0000-0000-0000-000000000004
  - text: Option 2
    value: opt2
    uuid: aaaaaaaa-0000-0000-0000-000000000005
uuid: aaaaaaaa-0000-0000-0000-000000000006
""")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("submit_on_exit_line", "expected"),
    [
        pytest.param("submit_on_exit: true\n", True, id="explicit_true"),
        pytest.param("", False, id="absent_defaults_to_false"),
    ],
)
def test_schema_submit_on_exit_loads_from_frontmatter(
    site, mock_site_context, submit_on_exit_line, expected
):
    """A form.md's submit_on_exit frontmatter loads onto Form.submit_on_exit,
    defaulting to False when the key is absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        _write_quiz_course(course_dir, submit_on_exit_line=submit_on_exit_line)
        save_content_to_db(course_dir, site.name)

    form = Form.objects.get(title="Submit On Exit Quiz", site=site)
    assert form.submit_on_exit is expected


test_data = [
    (
        "tutorial/02-understanding-the-graph-commits-and-checkout.md",
        "images/graph1.drawio.svg",
        "tutorial/images/graph1.drawio.svg",
    ),
    (
        "functionality_demo_course/3. quiz/1. page.yaml",
        "../images/graph1.drawio.svg",
        "functionality_demo_course/images/graph1.drawio.svg",
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("self_path", "other_path", "result"), test_data)
def test_all(self_path, other_path, result, mock_site_context):
    form: Form = FormFactory(title="Test Form")
    form.file_path = self_path
    form.save()

    expected = form.calculate_path_from_root(other_path)
    assert expected == result


# How `tags` is read off a content file, and what a reimport does to it.


_TOPIC_UUID = "11111111-1111-4111-8111-111111111111"


def _topic_file(make_temp_file, tags_line: str):
    return make_temp_file(
        suffix=".md",
        content=(
            "---\n"
            "content_type: TOPIC\n"
            "title: Reimported Topic\n"
            f"uuid: {_TOPIC_UUID}\n"
            f"{tags_line}"
            "---\n"
        ),
    )


def _import(path, site):
    return save_topic(parse_single_file(path)[0], site, path.parent)


@pytest.mark.django_db
def test_reimport_without_a_tags_key_keeps_the_stored_tags(
    site, mock_site_context, make_temp_file
):
    """A file that says nothing about tags must not clear them, as with meta."""
    path = _topic_file(make_temp_file, tags_line="")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == ["curated-in-the-admin"]


@pytest.mark.django_db
def test_reimport_with_an_empty_tags_key_clears_the_stored_tags(
    site, mock_site_context, make_temp_file
):
    """An explicit empty list is how a file says "this has no tags"."""
    path = _topic_file(make_temp_file, tags_line="tags: []\n")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == []


@pytest.mark.django_db
def test_reimport_replaces_the_stored_tags_with_the_files_own(
    site, mock_site_context, make_temp_file
):
    """A file listing tags is authoritative over whatever the admin curated."""
    path = _topic_file(make_temp_file, tags_line="tags: [python, advanced]\n")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == ["python", "advanced"]
