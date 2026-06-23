import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Course, CoursePart, File, Form, Topic


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
