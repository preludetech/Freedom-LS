"""The shipped demo content has a bank form beside the courses and explanations on the
Core Concepts knowledge check, so revision questions can be seen without authoring content.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.content_engine.validate import validate
from freedom_ls.form_engine.models import Form, FormQuestion, QuestionOption

pytestmark = pytest.mark.fls_internal

BANK_TITLE = "Core Concepts revision bank"
CORE_CONCEPTS_PART = "Core Concepts"
KEY_IDEAS_TOPIC = "Key Ideas"
TOPIC_QUESTION = "Can the same course part appear in more than one course?"


def _bank_questions(site) -> list[FormQuestion]:
    return list(
        FormQuestion.objects.filter(
            form_page__form__title=BANK_TITLE, form_page__form__site=site
        )
    )


@pytest.mark.django_db
def test_the_bank_form_is_listed_by_no_course(
    site, loaded_demo_content, mock_site_context
):
    bank = Form.objects.get(title=BANK_TITLE, site=site)

    placements = ContentCollectionItem.objects.filter(child_id=bank.pk)

    assert not placements.exists()


@pytest.mark.django_db
def test_the_bank_form_has_four_choice_questions_each_with_an_explanation(
    site, loaded_demo_content, mock_site_context
):
    questions = _bank_questions(site)

    assert len(questions) == 4
    assert all(question.explanation for question in questions)
    assert all(question.options.filter(correct=True).exists() for question in questions)


@pytest.mark.django_db
def test_bank_questions_without_their_own_list_test_the_course_part(
    site, loaded_demo_content, mock_site_context
):
    questions = [q for q in _bank_questions(site) if q.question != TOPIC_QUESTION]

    assert len(questions) == 3
    for question in questions:
        assert [part.title for part in question.course_parts.all()] == [
            CORE_CONCEPTS_PART
        ]
        assert not question.topics.exists()


@pytest.mark.django_db
def test_the_overriding_bank_question_tests_only_the_topic(
    site, loaded_demo_content, mock_site_context
):
    question = FormQuestion.objects.get(
        question=TOPIC_QUESTION, form_page__form__title=BANK_TITLE
    )

    assert [topic.title for topic in question.topics.all()] == [KEY_IDEAS_TOPIC]
    assert not question.course_parts.exists()


@pytest.mark.django_db
def test_the_all_of_the_above_option_is_stored_locked(
    site, loaded_demo_content, mock_site_context
):
    locked = QuestionOption.objects.filter(
        question__form_page__form__title=BANK_TITLE, locked=True
    ).get()

    assert locked.text == "All of the above"
    assert locked.correct is True


@pytest.mark.django_db
def test_knowledge_check_questions_store_their_explanations(
    site, loaded_demo_content, mock_site_context
):
    explained = FormQuestion.objects.filter(
        form_page__form__title="Knowledge Check", form_page__form__site=site
    ).exclude(explanation="")

    assert explained.count() >= 3


def test_the_demo_content_tree_passes_validation():
    validate("demo_content")
