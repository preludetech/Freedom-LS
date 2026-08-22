"""Free-text questions inside a ``strategy: QUIZ`` form.

Authored content is not supposed to put a ``short_text``/``long_text`` question
in a scored quiz — no demo course does. When it happens anyway, such a question
has no options at all, so it can be neither matched against a correct set nor
echoed back through ``selected_options``: it must not produce a review card.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.student_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)


def _quiz_with_free_text(question_type):
    """A quiz with one answered-correctly choice question and one free-text question."""
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, order=0)
    choice_question = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0
    )
    correct_option = QuestionOptionFactory(question=choice_question, correct=True)
    QuestionOptionFactory(question=choice_question, correct=False)
    free_text_question = FormQuestionFactory(
        form_page=page, type=question_type, question="Explain your reasoning", order=1
    )
    return form, choice_question, correct_option, free_text_question


@pytest.mark.parametrize("question_type", ["short_text", "long_text"])
@pytest.mark.django_db
def test_free_text_question_produces_no_incorrect_answer_card(
    mock_site_context, question_type
):
    user = UserFactory()
    form, choice_question, correct_option, free_text_question = _quiz_with_free_text(
        question_type
    )
    form_progress = FormProgressFactory(user=user, form=form)
    choice_answer = QuestionAnswerFactory(
        form_progress=form_progress, question=choice_question
    )
    choice_answer.selected_options.add(correct_option)
    QuestionAnswerFactory(
        form_progress=form_progress,
        question=free_text_question,
        text_answer="Because the current has nowhere else to go.",
    )

    incorrect = form_progress.get_incorrect_quiz_answers()

    assert incorrect == []


@pytest.mark.django_db
def test_free_text_question_still_counts_toward_the_quiz_max_score(mock_site_context):
    """The score ceiling is deliberately left alone: an unscoreable question
    still raises max_score, so such a quiz cannot reach 100%."""
    user = UserFactory()
    form, choice_question, correct_option, _free_text = _quiz_with_free_text(
        "short_text"
    )
    form_progress = FormProgressFactory(user=user, form=form)
    answer = QuestionAnswerFactory(
        form_progress=form_progress, question=choice_question
    )
    answer.selected_options.add(correct_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 2}
