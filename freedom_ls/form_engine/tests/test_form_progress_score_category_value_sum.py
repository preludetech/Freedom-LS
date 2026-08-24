"""Tests for the CATEGORY_VALUE_SUM strategy: option values summed per category."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionOption,
)


def _scored_question(
    page: FormPage, *, category: str, order: int, values: tuple[str, str]
) -> tuple[FormQuestion, QuestionOption]:
    """A question offering two option values; the first is returned to be selected."""
    question: FormQuestion = FormQuestionFactory(
        form_page=page,
        question=f"Question {order + 1}",
        type="multiple_choice",
        order=order,
        category=category,
    )
    highest, lowest = values
    top_option: QuestionOption = QuestionOptionFactory(
        question=question, text="Option 1", value=highest, order=0
    )
    QuestionOptionFactory(question=question, text="Option 2", value=lowest, order=1)
    return question, top_option


def _answer(
    form_progress: FormProgress, question: FormQuestion, option: QuestionOption
) -> None:
    answer: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question
    )
    answer.selected_options.add(option)


@pytest.mark.django_db
def test_score_category_value_sum_single_question(mock_site_context):
    """One answered question scores its option value under both page and question category."""
    form = FormFactory()
    page = FormPageFactory(form=form, title="Page 1", order=0, category="Wellbeing")
    question = FormQuestionFactory(
        form_page=page,
        question="How are you feeling?",
        type="multiple_choice",
        order=0,
        category="Mental Health",
    )
    best_option = QuestionOptionFactory(
        question=question, text="Great", value="5", order=0
    )
    QuestionOptionFactory(question=question, text="Good", value="3", order=1)
    QuestionOptionFactory(question=question, text="Poor", value="1", order=2)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, question, best_option)

    form_progress.score_category_value_sum()

    form_progress.refresh_from_db()
    assert form_progress.scores == {
        "Wellbeing": {
            "score": 5,
            "max_score": 5,
            "sub_categories": {
                "Mental Health": {"score": 5, "max_score": 5, "sub_categories": {}}
            },
        }
    }


@pytest.mark.django_db
def test_score_category_value_sum_calculates_max_score_correctly_with_unanswered_questions(
    mock_site_context,
):
    """max_score counts every question's highest option value, answered or not."""
    form = FormFactory()
    page = FormPageFactory(form=form, title="Page 1", order=0, category="Wellbeing")
    question_1, top_option_1 = _scored_question(
        page, category="Mental Health", order=0, values=("5", "3")
    )
    _scored_question(page, category="Mental Health", order=1, values=("10", "7"))

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, question_1, top_option_1)

    form_progress.score_category_value_sum()

    form_progress.refresh_from_db()
    assert form_progress.scores == {
        "Wellbeing": {
            "score": 5,
            "max_score": 15,
            "sub_categories": {
                "Mental Health": {"score": 5, "max_score": 15, "sub_categories": {}}
            },
        }
    }


@pytest.mark.django_db
def test_score_category_value_sum_categorises_questions_correctly(
    mock_site_context,
):
    """A question with no category of its own scores into its page's category alone.

    It must not conjure an "Uncategorized" sub-category to sit in.
    """
    form = FormFactory()
    page = FormPageFactory(form=form, title="Anatomy Page", order=0, category="Anatomy")
    uncategorised_question, uncategorised_top = _scored_question(
        page, category="", order=0, values=("5", "3")
    )
    categorised_question, categorised_top = _scored_question(
        page, category="Bones", order=1, values=("10", "7")
    )

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, uncategorised_question, uncategorised_top)
    _answer(form_progress, categorised_question, categorised_top)

    form_progress.score_category_value_sum()

    form_progress.refresh_from_db()
    assert form_progress.scores == {
        "Anatomy": {
            "score": 15,
            "max_score": 15,
            "sub_categories": {
                "Bones": {"score": 10, "max_score": 10, "sub_categories": {}}
            },
        }
    }


@pytest.mark.django_db
def test_score_category_value_sum_with_three_level_hierarchy(
    mock_site_context,
):
    """A pipe-separated page category nests under itself, with the question category below."""
    form = FormFactory()
    page = FormPageFactory(
        form=form, title="Health Page", order=0, category="Wellbeing | Physical Health"
    )
    exercise_question, exercise_top = _scored_question(
        page, category="Exercise", order=0, values=("5", "3")
    )
    nutrition_question, nutrition_top = _scored_question(
        page, category="Nutrition", order=1, values=("10", "7")
    )

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    _answer(form_progress, exercise_question, exercise_top)
    _answer(form_progress, nutrition_question, nutrition_top)

    form_progress.score_category_value_sum()

    form_progress.refresh_from_db()
    assert form_progress.scores == {
        "Wellbeing": {
            "score": 15,
            "max_score": 15,
            "sub_categories": {
                "Physical Health": {
                    "score": 15,
                    "max_score": 15,
                    "sub_categories": {
                        "Exercise": {
                            "score": 5,
                            "max_score": 5,
                            "sub_categories": {},
                        },
                        "Nutrition": {
                            "score": 10,
                            "max_score": 10,
                            "sub_categories": {},
                        },
                    },
                }
            },
        }
    }
