import tempfile
from pathlib import Path
import pytest
from freedom_ls.content_engine.management.commands.content_save import save_content_to_db
from freedom_ls.content_engine.models import Course, ContentCollectionItem, Topic, Form


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
        children = ContentCollectionItem.objects.filter(
            site=site, collection=course
        ).order_by("order")

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
