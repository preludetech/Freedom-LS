"""The two fragments a form page is built from, shared by the exam runner and
the application shell: the page's own children, and why a submission was
refused. They live here so the two shells cannot drift apart on either.
"""

from __future__ import annotations

import pytest

from django.template.loader import render_to_string

from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormPage


def _render_errors(required: str = "", rejected: str = "") -> str:
    return render_to_string(
        "form_engine/partials/answer_errors.html",
        {"required_answers_error": required, "rejected_answers_error": rejected},
    )


def _render_children(form_page: FormPage) -> str:
    return render_to_string(
        "form_engine/partials/page_children.html",
        {
            "form_page": form_page,
            "existing_answers": {},
            "rejected_answers": {},
            "read_only": False,
        },
    )


@pytest.mark.django_db
def test_no_errors_renders_nothing(mock_site_context):
    assert _render_errors().strip() == ""


@pytest.mark.django_db
def test_a_missing_required_answer_is_announced(mock_site_context):
    markup = _render_errors(required="Question 1 needs an answer.")

    assert 'data-testid="required-answers-error"' in markup
    assert 'role="alert"' in markup
    assert "Missing answers" in markup
    assert "Question 1 needs an answer." in markup


@pytest.mark.django_db
def test_an_invalid_answer_is_announced(mock_site_context):
    markup = _render_errors(rejected="Question 2 needs a valid answer.")

    assert 'data-testid="rejected-answers-error"' in markup
    assert "Invalid answers" in markup
    assert "Question 2 needs a valid answer." in markup


@pytest.mark.django_db
def test_one_error_does_not_draw_the_other(mock_site_context):
    markup = _render_errors(required="Question 1 needs an answer.")

    assert 'data-testid="rejected-answers-error"' not in markup


@pytest.mark.django_db
def test_both_errors_are_reported_together(mock_site_context):
    markup = _render_errors(required="Needs an answer.", rejected="Needs a valid one.")

    assert 'data-testid="required-answers-error"' in markup
    assert 'data-testid="rejected-answers-error"' in markup


@pytest.mark.django_db
def test_children_render_in_the_order_the_page_lays_them_out(mock_site_context):
    page: FormPage = FormPageFactory(order=0)
    FormContentFactory(form_page=page, content="Read this first.", order=0)
    question = FormQuestionFactory(
        form_page=page, type="short_text", order=1, question="Then answer this."
    )

    markup = _render_children(page)

    assert markup.index("Read this first.") < markup.index("Then answer this.")
    assert f'name="question_{question.id}"' in markup


@pytest.mark.django_db
def test_a_question_renders_as_a_fieldset(mock_site_context):
    page: FormPage = FormPageFactory(order=0)
    FormQuestionFactory(form_page=page, type="short_text", order=0)

    assert "<fieldset" in _render_children(page)


@pytest.mark.django_db
def test_a_page_with_no_children_renders_nothing(mock_site_context):
    page: FormPage = FormPageFactory(order=0)

    assert _render_children(page).strip() == ""
