"""Tests for the course filter shared by the educator interface's cohort tables."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.panels.common.filters import VisibleCourseFilter
from freedom_ls.educator_interface.tests.helpers import (
    COURSE_REACH_ROWS,
    _any_request,
    _educator_request,
    course_per_reach_row,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.usefixtures("_site_context")


@pytest.mark.django_db
def test_visible_course_filter_offers_only_courses_visible_to_the_educator(
    site_aware_request,
):
    organisation = OrganisationFactory()
    published = CourseFactory(title="Published Course")
    CourseFactory(title="Hidden Course", visibility=CourseVisibility.HIDDEN)
    request = _educator_request(site_aware_request, organisation)

    choices = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).get_choices(request)

    assert choices == [(str(published.pk), "Published Course")]


@pytest.mark.django_db
def test_visible_course_filter_keeps_a_cohort_with_an_active_registration():
    course = CourseFactory()
    cohort = CohortFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)

    result = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).apply(_any_request(), Cohort.objects.all(), [str(course.pk)])

    assert list(result) == [cohort]


@pytest.mark.django_db
def test_visible_course_filter_drops_a_cohort_whose_registration_is_inactive():
    course = CourseFactory()
    CohortCourseRegistrationFactory(course=course, is_active=False)

    result = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).apply(_any_request(), Cohort.objects.all(), [str(course.pk)])

    assert list(result) == []


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "offered"), COURSE_REACH_ROWS)
def test_visible_course_filter_offers_a_course_only_when_it_reaches_the_organisation(
    site_aware_request, row: str, offered: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    request = _educator_request(site_aware_request, organisation)

    choices = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).get_choices(request)

    assert (str(courses[row].pk) in [pk for pk, _ in choices]) is offered


@pytest.mark.django_db
def test_course_filter_names_the_owner_of_a_course_another_organisation_owns(
    site_aware_request,
):
    """Two courses with one title stayed indistinguishable in the choices."""
    organisation = OrganisationFactory(name="Harbour College")
    own = CourseFactory(title="Workplace Safety Essentials", slug="safety-own")
    own.organisations.add(organisation)
    shared = CourseFactory(title="Workplace Safety Essentials", slug="safety-shared")
    shared.organisations.add(OrganisationFactory(name="Northwind Logistics"))
    shared.shared_with.add(organisation)
    request = _educator_request(site_aware_request, organisation)

    choices = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).get_choices(request)

    assert sorted(label for _, label in choices) == [
        "Workplace Safety Essentials",
        "Workplace Safety Essentials (Northwind Logistics)",
    ]
