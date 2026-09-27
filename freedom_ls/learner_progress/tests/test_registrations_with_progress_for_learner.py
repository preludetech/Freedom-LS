"""``registrations_with_progress_for_learner``: the learner quick view's feed.

Covers both grant shapes (individual and through a cohort), a registration
with no ``CourseProgress`` record yet, and that the helper stays cheap
however many registrations there are.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.queries import (
    LearnerRegistrationProgress,
    registrations_with_progress_for_learner,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_an_individual_registration_reports_its_course_and_no_cohort(
    mock_site_context,
):
    learner = LearnerFactory()
    course: Course = CourseFactory()
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=True
    )
    record = ensure_course_progress_record(learner, course, registration)
    record.progress_percentage = 40
    record.save(update_fields=["progress_percentage"])

    result = registrations_with_progress_for_learner(learner)

    assert result == [
        LearnerRegistrationProgress(
            course=course,
            cohort=None,
            progress_percentage=40,
            last_accessed_time=record.last_accessed_time,
        )
    ]


@pytest.mark.django_db
def test_a_registration_through_a_cohort_reports_the_cohort(mock_site_context):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    course: Course = CourseFactory()
    registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=True
    )
    record = ensure_course_progress_record(learner, course, registration)

    result = registrations_with_progress_for_learner(learner)

    assert result == [
        LearnerRegistrationProgress(
            course=course,
            cohort=cohort,
            progress_percentage=record.progress_percentage,
            last_accessed_time=record.last_accessed_time,
        )
    ]


@pytest.mark.django_db
def test_a_registration_with_no_progress_record_reports_none_fields(
    mock_site_context,
):
    learner = LearnerFactory()
    course: Course = CourseFactory()
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)

    result = registrations_with_progress_for_learner(learner)

    assert result == [
        LearnerRegistrationProgress(
            course=course,
            cohort=None,
            progress_percentage=None,
            last_accessed_time=None,
        )
    ]


@pytest.mark.django_db
def test_an_inactive_registration_is_excluded(mock_site_context):
    learner = LearnerFactory()
    course: Course = CourseFactory()
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)

    assert registrations_with_progress_for_learner(learner) == []


@pytest.mark.django_db
def test_a_second_organisations_learner_for_the_same_user_is_ignored(
    mock_site_context,
):
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=OrganisationFactory())
    other_learner = LearnerFactory(user=user, organisation=OrganisationFactory())
    course: Course = CourseFactory()
    LearnerCourseRegistrationFactory(
        learner=other_learner, course=course, is_active=True
    )

    assert registrations_with_progress_for_learner(learner) == []


@pytest.mark.django_db
class TestQueryCost:
    """Three queries whatever the number of registrations -- the loop below
    must never issue one more per row."""

    @pytest.mark.parametrize("registration_count", [1, 5])
    def test_query_count_stays_at_three(
        self, mock_site_context, django_assert_num_queries, registration_count
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        for n in range(registration_count):
            individual_course: Course = CourseFactory(
                title=f"Individual {n}", slug=f"individual-{n}"
            )
            individual_registration = LearnerCourseRegistrationFactory(
                learner=learner, course=individual_course, is_active=True
            )
            ensure_course_progress_record(
                learner, individual_course, individual_registration
            )
            cohort_course: Course = CourseFactory(
                title=f"Cohort {n}", slug=f"cohort-{n}"
            )
            cohort_registration = CohortCourseRegistrationFactory(
                cohort=cohort, course=cohort_course, is_active=True
            )
            ensure_course_progress_record(learner, cohort_course, cohort_registration)

        with django_assert_num_queries(3):
            result = registrations_with_progress_for_learner(learner)

        assert len(result) == registration_count * 2
