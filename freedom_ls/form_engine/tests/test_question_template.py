"""`form_engine/question.html` is the one rendering of a question, shared by the
exam runner and the application shell. These pin the type ladder: each type gets
its own input, and an unhandled type is called out rather than rendering blank.
"""

from __future__ import annotations

import pytest

from django.template.loader import render_to_string

from freedom_ls.form_engine.factories import (
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormQuestion


def _render(question: FormQuestion) -> str:
    return render_to_string(
        "form_engine/question.html", {"question": question, "existing_answers": {}}
    )


@pytest.mark.django_db
def test_number_question_renders_a_number_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="number", order=0)

    markup = _render(question)

    assert 'type="number"' in markup


@pytest.mark.django_db
def test_short_text_question_renders_a_text_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="short_text", order=0
    )

    markup = _render(question)

    assert 'type="text"' in markup


@pytest.mark.django_db
def test_unhandled_question_type_is_called_out(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="not_a_real_type", order=0
    )

    markup = _render(question)

    assert "ERROR! UNHANDLED FORM TYPE" in markup
