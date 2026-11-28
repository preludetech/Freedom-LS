"""pin_to_latest_versions records each answer's question's latest version."""

from __future__ import annotations

from typing import cast

import pytest

from freedom_ls.form_engine.factories import (
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    FormQuestion,
    QuestionAnswer,
    save_question_version,
)
from freedom_ls.qa_helpers.answers import pin_to_latest_versions

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


def _answer(question: FormQuestion) -> QuestionAnswer:
    return cast(QuestionAnswer, QuestionAnswerFactory(question=question))


def test_answers_are_pinned_to_the_latest_version(mock_site_context) -> None:
    question = cast(FormQuestion, FormQuestionFactory())
    save_question_version(question, [], "c1")
    question.question = "Changed"
    question.save()
    latest = save_question_version(question, [], "c2").version
    answer = _answer(question)

    pin_to_latest_versions([answer])

    answer.refresh_from_db()
    assert answer.question_version == latest


def test_an_answer_whose_question_has_no_version_stays_none(mock_site_context) -> None:
    answer = _answer(cast(FormQuestion, FormQuestionFactory()))

    pin_to_latest_versions([answer])

    answer.refresh_from_db()
    assert answer.question_version is None
