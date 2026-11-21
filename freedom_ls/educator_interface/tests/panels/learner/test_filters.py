"""The learner list's table filters."""

from __future__ import annotations

from typing import cast

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.learner.filters import (
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
)
from freedom_ls.educator_interface.tests.helpers import (
    COURSE_REACH_ROWS,
    _any_request,
    _educator_request,
    course_per_reach_row,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.usefixtures("_site_context")


def _status_learners() -> dict[str, Learner]:
    organisation = OrganisationFactory()
    active = cast(Learner, LearnerFactory(organisation=organisation))
    pending = cast(Learner, LearnerFactory(organisation=organisation))
    pending.user.set_unusable_password()
    pending.user.save(update_fields=["password"])
    inactive = cast(Learner, LearnerFactory(organisation=organisation, is_active=False))
    return {"active": active, "pending": pending, "inactive": inactive}


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["active", "pending", "inactive"])
def test_status_filter_narrows_to_each_status(status: str) -> None:
    learners = _status_learners()

    result = LearnerStatusFilter().apply(
        _any_request(), Learner.objects.all(), [status]
    )

    assert list(result) == [learners[status]]


@pytest.mark.django_db
def test_status_filter_with_two_statuses_returns_both() -> None:
    learners = _status_learners()

    result = LearnerStatusFilter().apply(
        _any_request(), Learner.objects.all(), ["active", "pending"]
    )

    assert set(result) == {learners["active"], learners["pending"]}


@pytest.mark.django_db
def test_status_filter_defaults_to_active_and_pending() -> None:
    assert LearnerStatusFilter().default == ("active", "pending")


def _cohort_filter() -> LearnerCohortFilter:
    return LearnerCohortFilter("cohort", "Cohort", lookup="")


@pytest.mark.django_db
def test_learner_cohort_filter_labels_an_inactive_cohort_as_inactive(
    site_aware_request,
):
    organisation = OrganisationFactory()
    active = CohortFactory(organisation=organisation, name="Alpha")
    inactive = CohortFactory(organisation=organisation, name="Beta", is_active=False)
    request = _educator_request(site_aware_request, organisation)

    choices = _cohort_filter().get_choices(request)

    assert choices == [
        (str(active.pk), "Alpha"),
        (str(inactive.pk), "Beta (inactive)"),
    ]


@pytest.mark.django_db
def test_learner_cohort_filter_narrows_to_members_of_the_chosen_cohort():
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    member = LearnerFactory(organisation=organisation)
    LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    result = _cohort_filter().apply(
        _any_request(), Learner.objects.all(), [str(cohort.pk)]
    )

    assert list(result) == [member]


@pytest.mark.django_db
def test_learner_cohort_filter_drops_a_cohort_outside_the_organisation(
    site_aware_request,
):
    organisation = OrganisationFactory()
    outsider = CohortFactory(organisation=OrganisationFactory())
    request = _educator_request(site_aware_request, organisation)

    values = _cohort_filter().validate([str(outsider.pk)], request)

    assert values == []


def _course_filter() -> LearnerCourseFilter:
    return LearnerCourseFilter("course", "Course", lookup="")


@pytest.mark.django_db
def test_learner_course_filter_keeps_a_learner_registered_individually():
    course = CourseFactory()
    learner = LearnerFactory()
    LearnerFactory()
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == [learner]


@pytest.mark.django_db
def test_learner_course_filter_keeps_a_member_of_an_active_cohort_registered():
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
    member = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == [member]


@pytest.mark.django_db
def test_learner_course_filter_drops_a_member_of_an_inactive_cohort_registered():
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == []


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "offered"), COURSE_REACH_ROWS)
def test_learner_course_filter_offers_a_course_only_when_it_reaches_the_organisation(
    site_aware_request, row: str, offered: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    request = _educator_request(site_aware_request, organisation)

    choices = _course_filter().get_choices(request)

    assert (str(courses[row].pk) in [pk for pk, _ in choices]) is offered
