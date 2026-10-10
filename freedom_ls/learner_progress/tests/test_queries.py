from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from django.utils import timezone

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
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.queries import (
    LearnerRegistrationProgress,
    course_progress_by_course_for,
    course_progress_for,
    registrations_with_progress_for_learner,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record

# The bulk resolver must agree with the single-course one, course for course.
#
# ``course_progress_by_course_for`` restates ``learner_for_course``'s resolution
# order in Python so a listing does not pay two queries per course. Restating an
# order is how two read paths drift apart, so the tests below pin the bulk answer
# to the single-course answer rather than to a hand-written expectation.


def _backdate(
    registration: CohortCourseRegistration | LearnerCourseRegistration,
    when: datetime,
) -> None:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    type(registration).objects.filter(pk=registration.pk).update(registered_at=when)


@pytest.mark.django_db
class TestAgreesWithCourseProgressFor:
    def test_no_registration_leaves_the_course_out(self, mock_site_context):
        course: Course = CourseFactory()
        user = UserFactory()

        assert course_progress_by_course_for(user, [course]) == {}

    def test_a_registration_with_no_record_leaves_the_course_out(
        self, mock_site_context
    ):
        course: Course = CourseFactory()
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner=LearnerFactory(user=user), course=course
        )

        assert course_progress_by_course_for(user, [course]) == {}

    def test_an_individual_registration_yields_its_record(self, mock_site_context):
        course: Course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)
        record = ensure_course_progress_record(learner, course, registration)

        assert course_progress_by_course_for(user, [course]) == {course.id: record}

    def test_a_mixed_set_of_courses_matches_the_single_course_resolver(
        self, mock_site_context
    ):
        """Four courses, four different shapes, one call: every answer agrees."""
        user = UserFactory()
        learner = LearnerFactory(user=user)
        cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)

        cohort_only: Course = CourseFactory(title="Cohort only", slug="cohort-only")
        individual_only: Course = CourseFactory(
            title="Individual only", slug="individual-only"
        )
        both_grants: Course = CourseFactory(title="Both grants", slug="both-grants")
        unregistered: Course = CourseFactory(title="Unregistered", slug="unregistered")

        ensure_course_progress_record(
            learner,
            cohort_only,
            CohortCourseRegistrationFactory(cohort=cohort, course=cohort_only),
        )
        ensure_course_progress_record(
            learner,
            individual_only,
            LearnerCourseRegistrationFactory(learner=learner, course=individual_only),
        )
        ensure_course_progress_record(
            learner,
            both_grants,
            CohortCourseRegistrationFactory(cohort=cohort, course=both_grants),
        )
        ensure_course_progress_record(
            learner,
            both_grants,
            LearnerCourseRegistrationFactory(learner=learner, course=both_grants),
        )

        courses = [cohort_only, individual_only, both_grants, unregistered]
        bulk = course_progress_by_course_for(user, courses)

        assert bulk == {
            course.id: course_progress_for(user, course)
            for course in courses
            if course_progress_for(user, course) is not None
        }

    def test_an_inactive_cohort_is_skipped_and_the_individual_record_wins(
        self, mock_site_context
    ):
        course: Course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        cohort = CohortFactory(organisation=learner.organisation, is_active=False)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        ensure_course_progress_record(
            learner,
            course,
            CohortCourseRegistrationFactory(cohort=cohort, course=course),
        )
        individual_record = ensure_course_progress_record(
            learner,
            course,
            LearnerCourseRegistrationFactory(learner=learner, course=course),
        )

        assert course_progress_by_course_for(user, [course]) == {
            course.id: individual_record
        }

    def test_the_cohort_record_wins_over_the_individual_one(self, mock_site_context):
        course: Course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        cohort_record = ensure_course_progress_record(
            learner,
            course,
            CohortCourseRegistrationFactory(cohort=cohort, course=course),
        )
        ensure_course_progress_record(
            learner,
            course,
            LearnerCourseRegistrationFactory(learner=learner, course=course),
        )

        assert course_progress_by_course_for(user, [course]) == {
            course.id: cohort_record
        }

    def test_the_newest_cohort_registration_decides(self, mock_site_context):
        course: Course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        older_cohort = CohortFactory(organisation=learner.organisation)
        newer_cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=older_cohort)
        CohortMembershipFactory(learner=learner, cohort=newer_cohort)
        older_registration = CohortCourseRegistrationFactory(
            cohort=older_cohort, course=course
        )
        _backdate(older_registration, timezone.now() - timedelta(days=7))
        newer_registration = CohortCourseRegistrationFactory(
            cohort=newer_cohort, course=course
        )
        ensure_course_progress_record(learner, course, older_registration)
        newer_record = ensure_course_progress_record(
            learner, course, newer_registration
        )

        assert course_progress_by_course_for(user, [course]) == {
            course.id: newer_record
        }

    def test_a_lapsed_registration_loses_to_an_active_one_in_another_organisation(
        self, mock_site_context
    ):
        """An active registration wins on recency's own terms, not despite them.

        One person studying through two organisations holds two Learner rows and
        so can hold two individual registrations for one course.
        """
        course: Course = CourseFactory()
        user = UserFactory()
        lapsed_learner = LearnerFactory(user=user)
        current_learner = LearnerFactory(user=user)
        lapsed = LearnerCourseRegistrationFactory(
            learner=lapsed_learner, course=course, is_active=False
        )
        ensure_course_progress_record(lapsed_learner, course, lapsed)
        current = LearnerCourseRegistrationFactory(
            learner=current_learner, course=course, is_active=True
        )
        _backdate(current, timezone.now() - timedelta(days=30))
        current_record = ensure_course_progress_record(current_learner, course, current)

        assert course_progress_by_course_for(user, [course]) == {
            course.id: current_record
        }
        assert course_progress_for(user, course) == current_record

    def test_another_learners_record_is_never_returned(self, mock_site_context):
        course: Course = CourseFactory()
        stranger = UserFactory()
        stranger_learner = LearnerFactory(user=stranger)
        ensure_course_progress_record(
            stranger_learner,
            course,
            LearnerCourseRegistrationFactory(learner=stranger_learner, course=course),
        )

        assert course_progress_by_course_for(UserFactory(), [course]) == {}


@pytest.mark.django_db
class TestCourseProgressByCourseForQueryCount:
    """Three queries whatever the course count -- that is the whole point of it.

    A resolver that quietly looped over ``course_progress_for`` would pass every
    agreement test above and still put two queries per course on the dashboard.
    """

    @pytest.mark.parametrize("course_count", [1, 8])
    def test_cost_does_not_grow_with_the_number_of_courses(
        self, mock_site_context, django_assert_max_num_queries, course_count
    ):
        user = UserFactory()
        learner = LearnerFactory(user=user)
        cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        courses: list[Course] = []
        for n in range(course_count):
            course: Course = CourseFactory(title=f"Course {n}", slug=f"course-{n}")
            ensure_course_progress_record(
                learner,
                course,
                CohortCourseRegistrationFactory(cohort=cohort, course=course),
            )
            LearnerCourseRegistrationFactory(learner=learner, course=course)
            courses.append(course)

        with django_assert_max_num_queries(3):
            resolved = course_progress_by_course_for(user, courses)

        assert len(resolved) == course_count

    def test_other_cohort_members_records_are_not_fetched(
        self, mock_site_context, django_assert_max_num_queries
    ):
        """A cohort registration grants a record to every member, so filtering
        on the registration alone hydrates the whole cohort and discards all
        but one row -- an O(members) cost on every dashboard render."""
        cohort = CohortFactory()
        course: Course = CourseFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)

        user = UserFactory()
        learner = LearnerFactory(user=user, organisation=cohort.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        own_record = ensure_course_progress_record(learner, course, registration)

        for n in range(5):
            classmate = LearnerFactory(
                user=UserFactory(email=f"classmate-{n}@email.com"),
                organisation=cohort.organisation,
            )
            CohortMembershipFactory(learner=classmate, cohort=cohort)
            ensure_course_progress_record(classmate, course, registration)

        with django_assert_max_num_queries(3) as captured:
            assert course_progress_by_course_for(user, [course]) == {
                course.id: own_record
            }

        # The records read must name the learner, not just the registration.
        records_query = captured.captured_queries[-1]["sql"]
        assert learner.pk.hex in records_query.replace("-", "")


# Tests for course_progress_for, the single read path from a User to their
# live CourseProgress record for a course.


def _backdate_cohort_registration(
    registration: CohortCourseRegistration, when: datetime
) -> CohortCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    CohortCourseRegistration.objects.filter(pk=registration.pk).update(
        registered_at=when
    )
    registration.refresh_from_db()
    return registration


@pytest.mark.django_db
class TestCourseProgressFor:
    def test_no_registration_returns_none(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()

        assert course_progress_for(user, course) is None

    def test_registration_with_no_record_yet_returns_none(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner=LearnerFactory(user=user), course=course
        )

        assert course_progress_for(user, course) is None

    def test_resolves_to_the_cohort_record_when_a_learner_holds_both_grants(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        cohort_registration = CohortCourseRegistrationFactory(
            cohort=cohort, course=course
        )
        individual_registration = LearnerCourseRegistrationFactory(
            learner=learner, course=course
        )
        cohort_record = CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=cohort_registration,
        )
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=individual_registration,
        )

        assert course_progress_for(user, course) == cohort_record

    def test_the_newest_cohort_registration_decides_for_a_learner_in_two_cohorts(
        self, mock_site_context
    ):
        """Two cohorts both granting the course is a tie the ordering has to
        break the same way every call, or the learner's figures flip about."""
        course = CourseFactory()
        user = UserFactory()
        learner = LearnerFactory(user=user)
        older_cohort = CohortFactory(organisation=learner.organisation)
        newer_cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=older_cohort)
        CohortMembershipFactory(learner=learner, cohort=newer_cohort)
        older_registration = CohortCourseRegistrationFactory(
            cohort=older_cohort, course=course
        )
        _backdate_cohort_registration(
            older_registration, timezone.now() - timedelta(days=7)
        )
        newer_registration = CohortCourseRegistrationFactory(
            cohort=newer_cohort, course=course
        )
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=older_registration,
        )
        newer_record = CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=newer_registration,
        )

        assert course_progress_for(user, course) == newer_record


# ``registrations_with_progress_for_learner``: the learner quick view's feed.
#
# Covers both grant shapes (individual and through a cohort), a registration
# with no ``CourseProgress`` record yet, and that the helper stays cheap
# however many registrations there are.


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
    learner = LearnerFactory()
    cohort = CohortFactory(organisation=learner.organisation)
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
def test_an_inactive_cohorts_registration_is_skipped_and_the_individual_one_reported(
    mock_site_context,
):
    learner = LearnerFactory()
    cohort = CohortFactory(organisation=learner.organisation, is_active=False)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    course: Course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
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
    learner = LearnerFactory(user=user)
    other_learner = LearnerFactory(user=user)
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
        self, mock_site_context, django_assert_max_num_queries, registration_count
    ):
        learner = LearnerFactory()
        cohort = CohortFactory(organisation=learner.organisation)
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

        with django_assert_max_num_queries(3):
            result = registrations_with_progress_for_learner(learner)

        assert len(result) == registration_count * 2
