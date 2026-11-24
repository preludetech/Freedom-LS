from typing import cast

import lxml.html
import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.learner_interface.tests.helpers import course_with_form
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.tests.retire import retire


@pytest.fixture
def survey_with_retirements(
    mock_site_context: object, client: Client
) -> tuple[Course, list[FormQuestion], QuestionOption]:
    """A one-page survey of four questions whose second one has retired, and whose
    first question has a retired option. A learner is registered and logged in."""
    form: Form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    page = FormPageFactory(form=form, order=0)
    questions: list[FormQuestion] = [
        FormQuestionFactory(form_page=page, type="multiple_choice", order=order)
        for order in range(4)
    ]
    for question in questions:
        QuestionOptionFactory(question=question, order=0)
    retired_option = retire(
        cast("QuestionOption", QuestionOptionFactory(question=questions[0], order=1))
    )
    retire(questions[1])
    course = course_with_form(form)
    user = UserFactory()
    register_user_for_course(course, user)
    client.force_login(user)
    return course, questions, retired_option


def _fill_page(client: Client, course: Course) -> bytes:
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    response = client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )
    return response.content


@pytest.mark.django_db
def test_survey_fill_page_does_not_render_a_retired_question_or_option(
    survey_with_retirements, client
):
    course, questions, retired_option = survey_with_retirements

    content = _fill_page(client, course)

    document = lxml.html.fromstring(content)
    rendered_names = {
        node.get("name") for node in document.xpath("//*[@name]") if node.get("name")
    }
    rendered_values = {node.get("value") for node in document.xpath("//input[@value]")}
    assert f"question_{questions[1].id}" not in rendered_names
    assert {f"question_{questions[i].id}" for i in (0, 2, 3)} <= rendered_names
    assert str(retired_option.id) not in rendered_values


@pytest.mark.django_db
def test_survey_fill_page_numbers_the_live_questions_without_a_gap(
    survey_with_retirements, client
):
    course, _questions, _option = survey_with_retirements

    content = _fill_page(client, course)

    document = lxml.html.fromstring(content)
    numbers = [
        fieldset.xpath(".//legend/span")[0].text_content().strip()
        for fieldset in document.xpath(
            "//fieldset[.//*[starts-with(@name, 'question_')]]"
        )
    ]
    assert numbers == ["1.", "2.", "3."]
