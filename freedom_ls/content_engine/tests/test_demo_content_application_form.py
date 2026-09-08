"""The shipped demo content has to include a working application-gated course,
so the flow can be walked without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.models import Form, FormQuestion, FormStrategy

pytestmark = pytest.mark.fls_internal

GATED_COURSE_TITLE = "Functionality Demo - Application gated course"
APPLICATION_FORM_TITLE = "Application form"


@pytest.fixture
def loaded_demo_content(site, mock_site_context) -> None:
    save_content_to_db(settings.BASE_DIR / "demo_content", site.name)


@pytest.mark.django_db
def test_the_gated_demo_course_is_application_gated(site, loaded_demo_content):
    course = Course.objects.get(title=GATED_COURSE_TITLE, site=site)

    assert course.access_config == {
        "access_type": "application_gated",
        "application_form": "../functionality_demo_application_form/form.md",
    }


@pytest.mark.django_db
def test_the_gated_demo_course_names_the_demo_application_form(
    site, loaded_demo_content
):
    course = Course.objects.get(title=GATED_COURSE_TITLE, site=site)

    assert course.application_form.title == APPLICATION_FORM_TITLE


@pytest.mark.django_db
def test_the_demo_application_form_is_unscored(site, loaded_demo_content):
    form = Form.objects.get(title=APPLICATION_FORM_TITLE, site=site)

    assert form.strategy == FormStrategy.UNSCORED


@pytest.mark.django_db
def test_the_demo_application_form_asks_for_a_file(site, loaded_demo_content):
    form = Form.objects.get(title=APPLICATION_FORM_TITLE, site=site)

    assert FormQuestion.objects.filter(
        form_page__form=form, type="file_upload"
    ).exists()


@pytest.mark.django_db
def test_the_demo_application_form_asks_a_number_question(site, loaded_demo_content):
    form = Form.objects.get(title=APPLICATION_FORM_TITLE, site=site)

    assert FormQuestion.objects.filter(form_page__form=form, type="number").exists()


@pytest.mark.django_db
def test_the_demo_application_form_is_content_of_no_course(site, loaded_demo_content):
    """An application form is not coursework, so it must not appear in any
    course's contents -- only as the form a course points at.
    """
    form = Form.objects.get(title=APPLICATION_FORM_TITLE, site=site)

    assert (
        ContentCollectionItem.objects.filter(
            child_type=ContentType.objects.get_for_model(Form), child_id=form.id
        ).count()
        == 0
    )
