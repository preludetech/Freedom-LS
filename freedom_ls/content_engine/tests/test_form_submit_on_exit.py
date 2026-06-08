"""Tests for Form.submit_on_exit schema (content-loading) validation."""

import tempfile
from pathlib import Path

import pytest

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Form


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
