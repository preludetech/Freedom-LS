"""Tests for course_progress_for, the single read path from a User to their
live CourseProgress record for a course."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.organisations.factories import OrganisationFactory


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
            learner=LearnerFactory(user=user), collection=course
        )

        assert course_progress_for(user, course) is None

    def test_resolves_to_the_cohort_record_when_a_learner_holds_both_grants(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        organisation = OrganisationFactory()
        learner = LearnerFactory(user=user, organisation=organisation)
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        cohort_registration = CohortCourseRegistrationFactory(
            cohort=cohort, collection=course
        )
        individual_registration = LearnerCourseRegistrationFactory(
            learner=learner, collection=course
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
        organisation = OrganisationFactory()
        learner = LearnerFactory(user=user, organisation=organisation)
        older_cohort = CohortFactory(organisation=organisation)
        newer_cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=older_cohort)
        CohortMembershipFactory(learner=learner, cohort=newer_cohort)
        older_registration = CohortCourseRegistrationFactory(
            cohort=older_cohort, collection=course
        )
        _backdate_cohort_registration(
            older_registration, timezone.now() - timedelta(days=7)
        )
        newer_registration = CohortCourseRegistrationFactory(
            cohort=newer_cohort, collection=course
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
