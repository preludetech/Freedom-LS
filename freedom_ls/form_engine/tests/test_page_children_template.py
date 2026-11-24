"""form_engine/partials/page_children.html: the reviewer additions are off by default."""

from __future__ import annotations

from typing import cast

import pytest

from django.template import Template
from django.template.loader import render_to_string

from freedom_ls.form_engine.factories import (
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormQuestion, QuestionAnswer

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mock_site_context")]


def _answered(question_type: str) -> tuple[FormQuestion, QuestionAnswer]:
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=FormPageFactory(), type=question_type, question="Pick one"
        ),
    )
    QuestionOptionFactory(question=question, text="Alpha", order=1)
    chosen = QuestionOptionFactory(question=question, text="Beta", order=2)
    answer = cast(QuestionAnswer, QuestionAnswerFactory(question=question))
    answer.selected_options.add(chosen)
    return question, answer


def _render(question: FormQuestion, answer: QuestionAnswer, **extra: object) -> str:
    return render_to_string(
        "form_engine/partials/page_children.html",
        {
            "page_children": [question],
            "question_positions": {question.id: 1},
            "existing_answers": {question.id: answer},
            "rejected_answers": {},
            "read_only": True,
            **extra,
        },
    )


@pytest.mark.parametrize("question_type", ["multiple_choice", "checkboxes", "dropdown"])
def test_without_the_reviewer_flags_nothing_extra_is_drawn(question_type):
    question, answer = _answered(question_type)

    html = _render(question, answer)

    assert "Learner's answer" not in html
    assert 'font-normal text-muted">' not in html
    assert "VERDICT" not in html


@pytest.mark.parametrize("question_type", ["multiple_choice", "checkboxes", "dropdown"])
def test_the_learners_option_carries_the_learner_answer_mark(question_type):
    question, answer = _answered(question_type)

    html = _render(question, answer, show_learner_answer=True)

    assert html.count("Learner's answer") == 1


def test_the_question_id_shows_when_asked_for():
    question, answer = _answered("multiple_choice")

    html = _render(question, answer, show_question_id=True)

    assert f'font-normal text-muted">{question.id}</span>' in html


def test_a_per_question_template_is_included_after_each_question():
    question, answer = _answered("multiple_choice")

    html = _render(
        question,
        answer,
        per_question_template=Template("VERDICT"),
    )

    assert "VERDICT" in html
