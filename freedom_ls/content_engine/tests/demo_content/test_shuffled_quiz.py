"""The shipped shuffled demo quiz shows every shuffle setting and stays valid.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from django.conf import settings

from freedom_ls.content_engine.validate import validate
from freedom_ls.form_engine.models import Form, QuestionOption

pytestmark = pytest.mark.fls_internal

DEMO_COURSE = "functionality_demo_shuffled_quiz"
QUIZ_TITLE = "Shuffled quiz"
GROUP_PAGE_TITLE = "The sky"
GROUP_NAME = "sky-picture"


@pytest.mark.django_db
def test_the_demo_quiz_has_three_pages_and_every_shuffle_knob_on(
    site, loaded_demo_content, mock_site_context
):
    form = Form.objects.get(title=QUIZ_TITLE, site=site)

    assert (
        form.pages.count() >= 3,
        form.shuffle_pages,
        form.shuffle_questions,
        form.shuffle_options,
    ) == (True, True, True, True)


@pytest.mark.django_db
def test_the_demo_quiz_locks_exactly_one_option_reading_all_of_the_above(
    site, loaded_demo_content, mock_site_context
):
    locked = QuestionOption.objects.filter(
        question__form_page__form__title=QUIZ_TITLE, locked=True
    )

    assert [option.text for option in locked] == ["All of the above"]


@pytest.mark.django_db
def test_the_demo_quiz_groups_a_picture_with_two_questions_beside_ungrouped_ones(
    site, loaded_demo_content, mock_site_context
):
    form = Form.objects.get(title=QUIZ_TITLE, site=site)
    page = form.pages.get(title=GROUP_PAGE_TITLE)
    children = page.children()
    grouped = [child for child in children if child.group == GROUP_NAME]
    ungrouped = [child for child in children if not child.group]

    assert (
        [type(child).__name__ for child in grouped],
        "c-picture" in grouped[0].content,
        len(ungrouped) >= 1,
    ) == (["FormContent", "FormQuestion", "FormQuestion"], True, True)


def test_the_demo_quiz_fails_validation_when_a_question_splits_the_group(
    tmp_path: Path,
):
    demo_root = settings.BASE_DIR / "demo_content"
    shutil.copy(demo_root / "course_categories.yaml", tmp_path)
    shutil.copytree(demo_root / DEMO_COURSE, tmp_path / DEMO_COURSE)
    page_file = tmp_path / DEMO_COURSE / "2. quiz" / "2. the sky.yaml"
    sections = page_file.read_text(encoding="utf-8").split("\n---\n")
    # Swap the last two sections: an ungrouped question now sits between
    # the group's two questions.
    sections[-2], sections[-1] = sections[-1], sections[-2]
    page_file.write_text("\n---\n".join(sections), encoding="utf-8")

    with pytest.raises(ValueError, match=f'group "{GROUP_NAME}" is split'):
        validate(tmp_path)
