"""The shipped question pool demo quiz draws from both kinds of page and stays valid.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.content_engine.validate import validate
from freedom_ls.form_engine.models import Form

pytestmark = pytest.mark.fls_internal

DEMO_COURSE = "functionality_demo_question_pools"
QUIZ_TITLE = "Question pool quiz"
SINGLES_PAGE_FILE = "1. the planets.yaml"
GROUPS_PAGE_FILE = "2. short passages.yaml"


def _copy_course_to(tmp_path: Path) -> Path:
    """A copy of the demo course, with the categories file it needs, under tmp_path."""
    demo_root = settings.BASE_DIR / "demo_content"
    shutil.copy(demo_root / "course_categories.yaml", tmp_path)
    shutil.copytree(demo_root / DEMO_COURSE, tmp_path / DEMO_COURSE)
    return tmp_path / DEMO_COURSE / "01. quiz"


@pytest.mark.django_db
def test_the_demo_quiz_shuffles_and_has_a_drawing_page_of_questions_and_one_of_groups(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
) -> None:
    form = Form.objects.get(title=QUIZ_TITLE, site=site)
    singles, groups = form.pages.order_by("order")

    assert (
        form.shuffle_questions,
        singles.draw,
        [type(child).__name__ for child in singles.children()],
        groups.draw,
        [child.group for child in groups.children()],
        [type(child).__name__ for child in groups.children()[:3]],
    ) == (
        True,
        3,
        ["FormQuestion"] * 6,
        2,
        [name for name in ("tides", "seasons", "eclipse", "comets") for _ in range(3)],
        ["FormContent", "FormQuestion", "FormQuestion"],
    )


def test_the_demo_course_passes_validation(tmp_path: Path) -> None:
    _copy_course_to(tmp_path)

    validate(tmp_path)


def test_a_draw_above_the_number_of_questions_fails_validation(tmp_path: Path) -> None:
    quiz_dir = _copy_course_to(tmp_path)
    page_file = quiz_dir / SINGLES_PAGE_FILE
    page_file.write_text(
        page_file.read_text(encoding="utf-8").replace("draw: 3", "draw: 7"),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=re.escape(
            "draw is 7, but this page has 6 questions or groups to draw from."
        ),
    ):
        validate(tmp_path)


def test_a_group_with_an_extra_question_fails_validation(tmp_path: Path) -> None:
    quiz_dir = _copy_course_to(tmp_path)
    page_file = quiz_dir / GROUPS_PAGE_FILE
    last_question = page_file.read_text(encoding="utf-8").split("\n---\n")[-1]
    extra_question = re.sub(r"^ *uuid: .*\n", "", last_question, flags=re.MULTILINE)
    page_file.write_text(
        page_file.read_text(encoding="utf-8").rstrip("\n") + "\n---\n" + extra_question,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must each hold the same number of questions"):
        validate(tmp_path)
