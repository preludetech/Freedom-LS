"""Tests for the educator interface's forms."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.forms import CohortCourseRegistrationForm
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
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
