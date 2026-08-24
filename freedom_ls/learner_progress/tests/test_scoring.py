"""Tests for the bulk correctness helper.

It must classify each (attempt, question) pair identically to score_quiz().
"""

from uuid import uuid4

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.learner_progress.models import FormProgress, QuestionAnswer
from freedom_ls.learner_progress.scoring import evaluate_quiz_answers


@pytest.mark.django_db
def test_evaluate_quiz_answers_agrees_with_score_quiz_per_question(mock_site_context):
    """evaluate_quiz_answers, fed the same selections score_quiz() saw, must agree question by
    question — not just on the aggregate score."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)

    # Q1: ticks all four (2 correct, 2 incorrect) - should be incorrect.
    question_1 = FormQuestionFactory(
        form_page=page, question="Q1", type="checkboxes", order=0
    )
    q1_correct_1 = QuestionOptionFactory(
        question=question_1, text="A", value="1", order=0, correct=True
    )
    q1_correct_2 = QuestionOptionFactory(
        question=question_1, text="B", value="2", order=1, correct=True
    )
    q1_wrong_1 = QuestionOptionFactory(
        question=question_1, text="C", value="3", order=2, correct=False
    )
    q1_wrong_2 = QuestionOptionFactory(
        question=question_1, text="D", value="4", order=3, correct=False
    )

    # Q2: ticks exactly the correct option - should be correct.
    question_2 = FormQuestionFactory(
        form_page=page, question="Q2", type="checkboxes", order=1
    )
    q2_correct = QuestionOptionFactory(
        question=question_2, text="A", value="1", order=0, correct=True
    )
    q2_wrong = QuestionOptionFactory(
        question=question_2, text="B", value="2", order=1, correct=False
    )

    form_progress: FormProgress = FormProgressFactory(user=user, form=form)
    answer_1: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question_1
    )
    answer_1.selected_options.add(q1_correct_1, q1_correct_2, q1_wrong_1, q1_wrong_2)
    answer_2: QuestionAnswer = QuestionAnswerFactory(
        form_progress=form_progress, question=question_2
    )
    answer_2.selected_options.add(q2_correct)

    form_progress.score_quiz()
    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 2}

    options_by_question = {
        question_1.id: [q1_correct_1, q1_correct_2, q1_wrong_1, q1_wrong_2],
        question_2.id: [q2_correct, q2_wrong],
    }
    answer_rows = [
        (
            form_progress.id,
            question_1.id,
            {q1_correct_1.id, q1_correct_2.id, q1_wrong_1.id, q1_wrong_2.id},
        ),
        (form_progress.id, question_2.id, {q2_correct.id}),
    ]

    result = evaluate_quiz_answers(answer_rows, options_by_question)

    assert result == {
        (form_progress.id, question_1.id): False,
        (form_progress.id, question_2.id): True,
    }


@pytest.mark.django_db
def test_evaluate_quiz_answers_issues_no_queries(
    mock_site_context, django_assert_num_queries
):
    """The batched equivalent operates on pre-fetched data only — it must issue no queries."""
    question = FormQuestionFactory(type="checkboxes")
    correct_option = QuestionOptionFactory(question=question, correct=True)
    wrong_option = QuestionOptionFactory(question=question, correct=False)
    options_by_question = {question.id: [correct_option, wrong_option]}
    attempt_id = uuid4()
    answer_rows = [(attempt_id, question.id, {correct_option.id})]

    with django_assert_num_queries(0):
        result = evaluate_quiz_answers(answer_rows, options_by_question)

    assert result == {(attempt_id, question.id): True}
