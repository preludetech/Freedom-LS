"""Tests for Form.submit_on_exit model field and schema validation."""

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.factories import FormFactory
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Form


@pytest.mark.django_db
def test_form_submit_on_exit_defaults_to_false(mock_site_context):
    """A Form created without specifying submit_on_exit has it False."""
    form = FormFactory()
    assert form.submit_on_exit is False


@pytest.mark.django_db
def test_form_submit_on_exit_can_be_set_true(mock_site_context):
    """A Form created with submit_on_exit=True stores it correctly."""
    form = FormFactory(submit_on_exit=True)
    assert form.submit_on_exit is True


@pytest.mark.django_db
def test_schema_submit_on_exit_true_loads_correctly(site, mock_site_context):
    """A form.md with submit_on_exit: true validates and produces a Form with submit_on_exit=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
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
        (quiz_dir / "form.md").write_text("""---
content_type: FORM
strategy: QUIZ
title: Submit On Exit Quiz
uuid: aaaaaaaa-0000-0000-0000-000000000002
quiz_show_incorrect: true
quiz_pass_percentage: 70
submit_on_exit: true
---
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

        save_content_to_db(course_dir, site.name)

        form = Form.objects.get(title="Submit On Exit Quiz", site=site)
        assert form.submit_on_exit is True


@pytest.mark.django_db
def test_schema_submit_on_exit_absent_defaults_to_false(site, mock_site_context):
    """A form.md without submit_on_exit key produces a Form with submit_on_exit=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "test_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text("""---
content_type: COURSE
title: Default Exit Course
description: A test course
uuid: bbbbbbbb-0000-0000-0000-000000000001
---
""")

        quiz_dir = course_dir / "1. quiz"
        quiz_dir.mkdir()
        (quiz_dir / "form.md").write_text("""---
content_type: FORM
strategy: QUIZ
title: Default Exit Quiz
uuid: bbbbbbbb-0000-0000-0000-000000000002
quiz_show_incorrect: true
quiz_pass_percentage: 70
---
""")
        (quiz_dir / "1. page.yaml").write_text("""---
content_type: FORM_PAGE
title: Page 1
uuid: bbbbbbbb-0000-0000-0000-000000000003
---
question: Test question?
type: multiple_choice
required: true
options:
  - text: Option 1
    value: opt1
    uuid: bbbbbbbb-0000-0000-0000-000000000004
  - text: Option 2
    value: opt2
    uuid: bbbbbbbb-0000-0000-0000-000000000005
uuid: bbbbbbbb-0000-0000-0000-000000000006
""")

        save_content_to_db(course_dir, site.name)

        form = Form.objects.get(title="Default Exit Quiz", site=site)
        assert form.submit_on_exit is False
