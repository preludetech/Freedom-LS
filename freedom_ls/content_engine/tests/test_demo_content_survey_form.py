"""The demo form the course player's own runner serves.

`test_demo_content_application_form.py` covers the application shell's form;
this covers the in-course survey. Its shape is what the frontend QA plan drives
directly, and each fact pinned here is a one-word authoring detail that would
otherwise be undone without anyone noticing.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.form_engine.models import Form, FormQuestion

pytestmark = pytest.mark.fls_internal

SURVEY_TITLE = "Course Feedback Survey"


@pytest.mark.django_db
def test_the_demo_survey_requires_its_checkbox_group(site, loaded_demo_content):
    """A checkbox group is the one question the browser cannot validate itself,
    so the runner reveals its own "Select at least one option." message. Without
    a required group shipped in demo content, nothing exercises that path.
    """
    survey = Form.objects.get(title=SURVEY_TITLE, site=site)

    assert FormQuestion.objects.filter(
        form_page__form=survey, type="checkboxes", required=True
    ).exists()


@pytest.mark.django_db
def test_the_demo_survey_submits_on_exit(site, loaded_demo_content):
    """`form_submit_and_exit` refuses any form that does not set this, and a
    save-on-exit form's "Leave and save" is a GET carrying no answers. So this
    is the only demo form on which leaving mid-attempt posts a page of answers.
    """
    survey = Form.objects.get(title=SURVEY_TITLE, site=site)

    assert survey.submit_on_exit is True


@pytest.mark.django_db
@pytest.mark.parametrize("question_type", ["date", "email", "url"])
def test_the_demo_survey_asks_a_typed_question(
    site, loaded_demo_content, question_type
):
    """The typed question types are otherwise demonstrated only in the
    application shell, leaving the course player's runner unexercised.
    """
    survey = Form.objects.get(title=SURVEY_TITLE, site=site)

    assert FormQuestion.objects.filter(
        form_page__form=survey, type=question_type
    ).exists()


@pytest.mark.django_db
def test_the_demo_survey_asks_no_dropdown_question(site, loaded_demo_content):
    """`score_category_value_sum` reads option values from `multiple_choice`
    and `dropdown` questions alone. A dropdown here would join the survey's
    `max_value` and move every score this form has ever stored.
    """
    survey = Form.objects.get(title=SURVEY_TITLE, site=site)

    assert not FormQuestion.objects.filter(
        form_page__form=survey, type="dropdown"
    ).exists()
