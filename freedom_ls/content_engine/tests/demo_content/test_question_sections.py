"""The shipped demo content has to show how a question names the sections it tests,
as a form default, a question-level override and across a quiz, so the stored rows
can be seen without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.conf import settings
from django.test import override_settings

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import (
    FormQuestionCoursePart,
    FormQuestionTopic,
)
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.fls_internal

OVERRIDING_QUESTION = "What is a course part?"
KEY_IDEAS_TOPIC = "Key Ideas"
CORE_CONCEPTS_PART = "Core Concepts"
BEFORE_MID_QUIZ_TOPIC = "Content title 2 - Before Quiz"
BEFORE_END_QUIZ_TOPIC = "Content title 4 - After quiz"


def _section_titles(question: FormQuestion) -> tuple[set[str], set[str]]:
    return (
        {topic.title for topic in question.topics.all()},
        {part.title for part in question.course_parts.all()},
    )


@pytest.mark.django_db
def test_knowledge_check_questions_without_the_key_test_only_the_course_part(
    site, loaded_demo_content, mock_site_context
):
    questions = FormQuestion.objects.filter(
        form_page__form__title="Knowledge Check", form_page__form__site=site
    ).exclude(question=OVERRIDING_QUESTION)

    sections = [_section_titles(question) for question in questions]

    assert len(sections) == 2
    assert sections == [(set(), {CORE_CONCEPTS_PART})] * 2


@pytest.mark.django_db
def test_knowledge_check_question_with_its_own_list_tests_only_that_topic(
    site, loaded_demo_content, mock_site_context
):
    question = FormQuestion.objects.get(
        question=OVERRIDING_QUESTION, form_page__form__site=site
    )

    assert _section_titles(question) == ({KEY_IDEAS_TOPIC}, set())


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("quiz_title", "topic_title"),
    [
        ("Mid course Quiz", BEFORE_MID_QUIZ_TOPIC),
        ("End course Quiz", BEFORE_END_QUIZ_TOPIC),
    ],
)
def test_end_with_quiz_questions_test_the_topic_before_their_quiz(
    site, loaded_demo_content, mock_site_context, quiz_title, topic_title
):
    questions = FormQuestion.objects.filter(
        form_page__form__title=quiz_title,
        form_page__form__site=site,
    )

    sections = {frozenset(_section_titles(q)[0]) for q in questions}

    assert questions.exists()
    assert sections == {frozenset({topic_title})}


@pytest.mark.django_db
def test_loading_the_demo_content_again_keeps_the_same_section_rows(
    site, loaded_demo_content, mock_site_context, demo_media_root: Path
):
    topic_rows = set(FormQuestionTopic.objects.values_list("id", flat=True))
    part_rows = set(FormQuestionCoursePart.objects.values_list("id", flat=True))

    with override_settings(MEDIA_ROOT=demo_media_root), site_context(site):
        save_content_to_db(settings.BASE_DIR / "demo_content", site.name)

    assert topic_rows
    assert part_rows
    assert set(FormQuestionTopic.objects.values_list("id", flat=True)) == topic_rows
    assert set(FormQuestionCoursePart.objects.values_list("id", flat=True)) == part_rows
