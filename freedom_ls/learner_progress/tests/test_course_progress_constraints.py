"""The uniqueness, check and PROTECT guarantees CourseProgress now carries.

These shapes are net-new: the previous unique_together on (user, course) made
"two records for one learner and one course" impossible to express at all.
"""

from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress

pytestmark = pytest.mark.django_db


def _cohort_grant(learner, course):
    """An active cohort registration for `course` with `learner` a member."""
    cohort = CohortFactory(organisation=learner.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return CohortCourseRegistrationFactory(cohort=cohort, collection=course)


class TestUniquenessPerRegistration:
    def test_second_record_for_one_learner_registration_is_rejected(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory()
        CourseProgressFactory(
            learner=registration.learner,
            course=registration.collection,
            learner_registration=registration,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=registration.learner,
                course=registration.collection,
                learner_registration=registration,
            )

    def test_second_record_for_one_cohort_registration_is_rejected(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=learner,
                course=course,
                learner_registration=None,
                cohort_registration=registration,
            )

    def test_many_cohort_granted_records_for_one_learner_coexist(
        self, mock_site_context
    ):
        """They all share a null learner_registration, and NULLs are distinct."""
        learner = LearnerFactory()
        first = _cohort_grant(learner, CourseFactory())
        second = _cohort_grant(learner, CourseFactory())

        CourseProgressFactory(
            learner=learner,
            course=first.collection,
            learner_registration=None,
            cohort_registration=first,
        )
        CourseProgressFactory(
            learner=learner,
            course=second.collection,
            learner_registration=None,
            cohort_registration=second,
        )

        assert CourseProgress.objects.filter(learner=learner).count() == 2

    def test_many_individually_granted_records_for_one_learner_coexist(
        self, mock_site_context
    ):
        """The mirror image: they all share a null cohort_registration."""
        learner = LearnerFactory()
        first = LearnerCourseRegistrationFactory(learner=learner)
        second = LearnerCourseRegistrationFactory(learner=learner)

        CourseProgressFactory(
            learner=learner, course=first.collection, learner_registration=first
        )
        CourseProgressFactory(
            learner=learner, course=second.collection, learner_registration=second
        )

        assert CourseProgress.objects.filter(learner=learner).count() == 2

    def test_one_learner_and_course_may_hold_one_record_per_grant(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort_registration = _cohort_grant(learner, course)
        learner_registration = LearnerCourseRegistrationFactory(
            learner=learner, collection=course
        )

        CourseProgressFactory(
            learner=learner, course=course, learner_registration=learner_registration
        )
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=cohort_registration,
        )

        assert (
            CourseProgress.objects.filter(learner=learner, course=course).count() == 2
        )


class TestExactlyOneGrant:
    def test_a_record_naming_both_grants_is_rejected(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort_registration = _cohort_grant(learner, course)
        learner_registration = LearnerCourseRegistrationFactory(
            learner=learner, collection=course
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(
                learner=learner,
                course=course,
                learner_registration=learner_registration,
                cohort_registration=cohort_registration,
            )

    def test_a_record_naming_no_grant_is_rejected(self, mock_site_context):
        with pytest.raises(IntegrityError), transaction.atomic():
            CourseProgressFactory(learner_registration=None, cohort_registration=None)


class TestGrantIsProtected:
    def test_deleting_a_learner_registration_that_granted_a_record_is_blocked(
        self, mock_site_context
    ):
        record = CourseProgressFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            record.learner_registration.delete()

    def test_deleting_a_cohort_registration_that_granted_a_record_is_blocked(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.delete()

    def test_deactivating_a_registration_leaves_the_record_alone(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        registration = record.learner_registration

        registration.is_active = False
        registration.save()

        record.refresh_from_db()
        assert record.learner_registration_id == registration.id


class TestCleanGuardsThePairing:
    def test_a_registration_for_another_course_is_rejected(self, mock_site_context):
        record = CourseProgressFactory()
        record.course = CourseFactory()

        with pytest.raises(ValidationError, match="for this course"):
            record.full_clean()

    def test_a_registration_belonging_to_another_learner_is_rejected(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        other = LearnerCourseRegistrationFactory(collection=record.course)
        record.learner_registration = other

        with pytest.raises(ValidationError, match="belong to this learner"):
            record.full_clean()

    def test_a_cohort_granted_record_survives_the_learner_leaving_the_cohort(
        self, mock_site_context
    ):
        """An unconditional membership check would make this row unsaveable."""
        learner = LearnerFactory()
        course = CourseFactory()
        registration = _cohort_grant(learner, course)
        record = CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        )
        CohortMembership.objects.filter(
            cohort=registration.cohort, learner=learner
        ).delete()

        record.full_clean()

        assert record.cohort_registration_id == registration.id

    def test_a_new_cohort_granted_record_needs_a_membership(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort = CohortFactory(organisation=learner.organisation)
        registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        record = CourseProgress(
            site=course.site,
            learner=learner,
            course=course,
            cohort_registration=registration,
        )

        with pytest.raises(ValidationError, match="not a member"):
            record.full_clean()

    def test_a_cohort_in_another_organisation_is_rejected(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        cohort = CohortFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        record = CourseProgress(
            site=course.site,
            learner=learner,
            course=course,
            cohort_registration=registration,
        )

        with pytest.raises(ValidationError, match="same organisation"):
            record.full_clean()
