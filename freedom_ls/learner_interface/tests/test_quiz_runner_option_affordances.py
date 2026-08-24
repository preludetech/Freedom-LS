"""The quiz runner must let a learner tell a single-select question from a
multi-select one before they answer it. Under exact-set scoring a misread
multi-select scores zero, so the distinction is not decorative.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy

from .conftest import course_with_form, register_user_for_course


def _runner_page(client, question_type):
    """Render page 1 of a one-question quiz of the given question type."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type=question_type, order=0)
    QuestionOptionFactory(question=question, text="Alpha", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Beta", correct=False, order=1)

    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    return client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )


@pytest.mark.django_db
def test_multiple_choice_options_render_a_radio_indicator(mock_site_context, client):
    response = _runner_page(client, "multiple_choice")

    assert b'data-testid="radio-indicator"' in response.content
    assert b'data-testid="checkbox-indicator"' not in response.content


@pytest.mark.django_db
def test_checkbox_options_render_a_checkbox_indicator(mock_site_context, client):
    response = _runner_page(client, "checkboxes")

    assert b'data-testid="checkbox-indicator"' in response.content
    assert b'data-testid="radio-indicator"' not in response.content


@pytest.mark.django_db
def test_checkbox_question_carries_a_select_all_that_apply_hint(
    mock_site_context, client
):
    response = _runner_page(client, "checkboxes")

    assert "Select all that apply." in response.content.decode()


@pytest.mark.django_db
def test_multiple_choice_question_carries_no_select_all_hint(mock_site_context, client):
    response = _runner_page(client, "multiple_choice")

    assert "Select all that apply." not in response.content.decode()
