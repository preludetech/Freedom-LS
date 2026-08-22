"""Page-jump navigation on the form runner: which page dots a learner can click."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import Form, FormStrategy
from freedom_ls.learner_progress.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)

from .conftest import course_with_form, register_user_for_course


def _survey_with_an_optional_first_question(*, page_count: int) -> Form:
    """A multi-page survey whose first page holds a question a learner may skip."""
    form: Form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    optional_page = FormPageFactory(form=form, order=0, title="Page 1")
    optional_question = FormQuestionFactory(
        form_page=optional_page,
        type="multiple_choice",
        question="How are you finding this so far?",
        required=False,
        order=0,
    )
    QuestionOptionFactory(question=optional_question, text="Fine", order=0)

    for order in range(1, page_count):
        page = FormPageFactory(form=form, order=order, title=f"Page {order + 1}")
        question = FormQuestionFactory(
            form_page=page, type="multiple_choice", question="Pick one", order=0
        )
        QuestionOptionFactory(question=question, text="Alpha", order=0)
    return form


def _accessibility_of_each_page(client, course, page_number: int) -> list[bool]:
    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )
    response = client.get(url)
    return [link["is_accessible"] for link in response.context["page_links"]]


@pytest.mark.django_db
def test_skipping_an_optional_question_keeps_the_reached_pages_clickable(
    mock_site_context, client
):
    """A skipped question stores no answer row, which must not lock the learner out."""
    form = _survey_with_an_optional_first_question(page_count=3)
    course = course_with_form(form)
    user = register_user_for_course(course)
    FormProgressFactory(user=user, form=form)
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=3)

    assert accessibility == [True, True, True]


@pytest.mark.django_db
def test_pages_beyond_the_one_being_viewed_stay_locked(mock_site_context, client):
    form = _survey_with_an_optional_first_question(page_count=4)
    course = course_with_form(form)
    user = register_user_for_course(course)
    FormProgressFactory(user=user, form=form)
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=2)

    assert accessibility == [True, True, False, False]


@pytest.mark.django_db
def test_an_answered_later_page_stays_clickable_from_the_first_page(
    mock_site_context, client
):
    """Progress already recorded still opens up the pages it reached."""
    form = _survey_with_an_optional_first_question(page_count=3)
    course = course_with_form(form)
    user = register_user_for_course(course)
    progress = FormProgressFactory(user=user, form=form)
    third_page_question = form.pages.get(order=2).questions.get(order=0)
    QuestionAnswerFactory(
        form_progress=progress, question=third_page_question
    ).selected_options.add(third_page_question.options.get(order=0))
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=1)

    assert accessibility == [True, True, True]
