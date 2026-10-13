"""Tests for the educator interface's forms."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.forms import (
    AddLearnersForm,
    CohortCourseRegistrationForm,
    LearnerPickerForm,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import LearnerEntry
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.queries import registerable_courses_for


@pytest.mark.django_db
def test_registration_form_offers_only_the_registerable_courses(mock_site_context):
    cohort = CohortFactory()
    CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)
    open_course = CourseFactory()

    form = CohortCourseRegistrationForm(cohort=cohort)

    assert list(form.fields["course"].queryset) == [open_course]
    assert list(form.fields["course"].queryset) == list(
        registerable_courses_for(cohort)
    )


@pytest.mark.django_db
def test_registration_form_rejects_a_coming_soon_course(mock_site_context):
    cohort = CohortFactory()
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    form = CohortCourseRegistrationForm({"course": str(course.pk)}, cohort=cohort)

    assert form.is_valid() is False
    assert "course" in form.errors


@pytest.mark.django_db
def test_registration_form_accepts_a_published_course(mock_site_context):
    cohort = CohortFactory()
    course = CourseFactory()

    form = CohortCourseRegistrationForm({"course": str(course.pk)}, cohort=cohort)

    assert form.is_valid() is True


def _add_form(entries: str) -> AddLearnersForm:
    return AddLearnersForm({"entries": entries}, cohorts=Cohort.objects.none())


@pytest.mark.django_db
def test_add_learners_form_parses_email_first_and_last_name():
    form = _add_form("ada@example.com, Ada, Lovelace\n\nbob@example.com")

    assert form.is_valid()
    assert form.cleaned_data["entries"] == [
        LearnerEntry("ada@example.com", "Ada", "Lovelace"),
        LearnerEntry("bob@example.com"),
    ]


@pytest.mark.django_db
def test_add_learners_form_refuses_fifty_one_lines():
    form = _add_form("\n".join(f"u{n}@example.com" for n in range(51)))

    assert form.is_valid() is False
    assert "Add up to 50 at a time" in form.errors["entries"][0]


@pytest.mark.django_db
def test_add_learners_form_accepts_fifty_lines():
    form = _add_form("\n".join(f"u{n}@example.com" for n in range(50)))

    assert form.is_valid()


@pytest.mark.django_db
def test_add_learners_form_refuses_an_empty_textarea():
    form = _add_form(" \n\n")

    assert form.is_valid() is False
    assert "entries" in form.errors


@pytest.mark.django_db
def test_add_learners_form_keeps_an_invalid_address_for_the_results():
    form = _add_form("not-an-email")

    assert form.is_valid()
    assert form.cleaned_data["entries"] == [LearnerEntry("not-an-email")]


@pytest.mark.django_db
def test_learner_picker_labels_each_learner_by_display_name(mock_site_context):
    named = LearnerFactory(
        user__first_name="Ada",
        user__last_name="Lovelace",
        user__email="ada@example.com",
    )
    unnamed = LearnerFactory(
        user__first_name="", user__last_name="", user__email="pick@example.com"
    )

    form = LearnerPickerForm(
        queryset=Learner.objects.filter(pk__in=[named.pk, unnamed.pk])
    )

    labels = {label for _, label in form.fields["learners"].choices}
    assert labels == {"Ada Lovelace", "pick@example.com"}
