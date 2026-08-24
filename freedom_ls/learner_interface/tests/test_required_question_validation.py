"""Required questions must actually be required. Submitting a runner page with a
required question left blank re-renders the page with an error instead of
advancing to the next page or completing (and scoring) the attempt.
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
from freedom_ls.learner_progress.models import FormProgress

from .conftest import course_with_form, register_user_for_course


def _question_with_options(page, *, question_type, order, required=True):
    question = FormQuestionFactory(
        form_page=page, type=question_type, order=order, required=required
    )
    QuestionOptionFactory(question=question, text="Alpha", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Beta", correct=False, order=1)
    return question


def _start_form(client, form):
    """Register a learner for a course holding `form` and start an attempt."""
    user = UserFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    return user, course


def _page_url(course, page_number):
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )


def _single_page_quiz():
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    answered = _question_with_options(page, question_type="multiple_choice", order=0)
    blank = _question_with_options(page, question_type="checkboxes", order=1)
    return form, answered, blank


@pytest.mark.django_db
def test_final_page_with_blank_required_question_returns_422(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    _user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_final_page_with_blank_required_question_does_not_complete_the_attempt(
    mock_site_context, client
):
    form, answered, _blank = _single_page_quiz()
    user, course = _start_form(client, form)

    client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert (
        FormProgress.objects.filter(
            user=user, form=form, completed_time__isnull=False
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_blank_required_question_is_reported_to_the_learner(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    _user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert b'data-testid="required-answers-error"' in response.content


@pytest.mark.django_db
def test_blank_required_question_leaves_no_answer_row_behind(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    user, course = _start_form(client, form)

    client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    form_progress = FormProgress.get_latest_incomplete(user=user, form=form)
    assert list(form_progress.answers.values_list("question_id", flat=True)) == [
        answered.id
    ]


@pytest.mark.django_db
def test_answering_every_required_question_completes_the_attempt(
    mock_site_context, client
):
    form, answered, blank = _single_page_quiz()
    user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {
            f"question_{answered.id}": str(answered.options.first().id),
            f"question_{blank.id}": str(blank.options.first().id),
        },
    )

    assert response.status_code == 302
    assert FormProgress.objects.filter(
        user=user, form=form, completed_time__isnull=False
    ).exists()


@pytest.mark.django_db
def test_blank_required_question_does_not_advance_to_the_next_page(
    mock_site_context, client
):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page_1 = FormPageFactory(form=form, order=0)
    _question_with_options(page_1, question_type="multiple_choice", order=0)
    page_2 = FormPageFactory(form=form, order=1)
    _question_with_options(page_2, question_type="multiple_choice", order=0)
    _user, course = _start_form(client, form)

    response = client.post(_page_url(course, 1), {})

    assert response.status_code == 422


@pytest.mark.django_db
def test_optional_question_left_blank_still_advances(mock_site_context, client):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    _question_with_options(page, question_type="checkboxes", order=0, required=False)
    _user, course = _start_form(client, form)

    response = client.post(_page_url(course, 1), {})

    assert response.status_code == 302
