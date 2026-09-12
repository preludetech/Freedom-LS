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
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.form_engine.typed_answers import RejectedAnswer


def _render(
    question: FormQuestion,
    rejected_answers: dict | None = None,
) -> str:
    return render_to_string(
        "form_engine/question.html",
        {
            "question": question,
            "existing_answers": {},
            "rejected_answers": rejected_answers or {},
        },
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


@pytest.mark.django_db
def test_date_question_renders_a_date_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="date", order=0)

    markup = _render(question)

    assert 'type="date"' in markup


@pytest.mark.django_db
def test_time_question_renders_a_time_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="time", order=0)

    markup = _render(question)

    assert 'type="time"' in markup


@pytest.mark.django_db
def test_email_question_renders_an_email_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="email", order=0)

    markup = _render(question)

    assert 'type="email"' in markup


@pytest.mark.django_db
def test_url_question_renders_a_url_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="url", order=0)

    markup = _render(question)

    assert 'type="url"' in markup


@pytest.mark.django_db
def test_phone_question_renders_a_tel_input(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="phone", order=0)

    markup = _render(question)

    assert 'type="tel"' in markup


@pytest.mark.django_db
def test_dropdown_question_renders_a_select_with_its_options(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="dropdown", order=0
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0)
    QuestionOptionFactory(question=question, text="Beta", order=1)

    markup = _render(question)

    assert f'<select id="question_{question.id}"' in markup
    assert ">Alpha</option>" in markup
    assert ">Beta</option>" in markup


@pytest.mark.django_db
def test_number_question_with_bounds_renders_min_and_max_attributes(
    mock_site_context,
):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="number", order=0, min="0", max="70"
    )

    markup = _render(question)

    assert 'min="0"' in markup
    assert 'max="70"' in markup


@pytest.mark.django_db
def test_rejected_answer_renders_error_with_matching_aria_attributes(
    mock_site_context,
):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="email", order=0)
    rejected = RejectedAnswer(
        text="not-an-email", message="Enter a valid email address."
    )

    markup = _render(question, rejected_answers={question.id: rejected})

    error_id = f"question_{question.id}_error"
    assert f'aria-describedby="{error_id}"' in markup
    assert 'aria-invalid="true"' in markup
    assert f'id="{error_id}"' in markup
    assert rejected.message in markup


@pytest.mark.django_db
def test_rejected_answer_text_comes_back_in_the_input_value(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="email", order=0)
    rejected = RejectedAnswer(
        text="not-an-email", message="Enter a valid email address."
    )

    markup = _render(question, rejected_answers={question.id: rejected})

    assert 'value="not-an-email"' in markup


@pytest.mark.django_db
def test_no_error_rendered_when_rejected_answers_is_empty(mock_site_context):
    page = FormPageFactory(order=0)
    question: FormQuestion = FormQuestionFactory(form_page=page, type="email", order=0)

    markup = _render(question, rejected_answers={})

    assert "aria-invalid" not in markup
    assert f"question_{question.id}_error" not in markup
