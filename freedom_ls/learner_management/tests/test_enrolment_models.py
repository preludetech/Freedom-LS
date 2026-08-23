"""Tests for the enrolment models repointed at Learner."""

from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
class TestCohortMembershipClean:
    def test_rejects_a_learner_and_cohort_in_different_organisations(
        self, mock_site_context
    ):
        learner = LearnerFactory(organisation=OrganisationFactory())
        cohort = CohortFactory(
            organisation=OrganisationFactory(), name="Year 10 Science"
        )

        membership = CohortMembership(learner=learner, cohort=cohort)

        with pytest.raises(ValidationError):
            membership.clean()

    def test_permits_a_learner_and_cohort_in_the_same_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 10 Maths")

        membership = CohortMembership(learner=learner, cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_learner_is_unset(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory())

        membership = CohortMembership(cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_cohort_is_unset(self, mock_site_context):
        learner = LearnerFactory(organisation=OrganisationFactory())

        membership = CohortMembership(learner=learner)

        membership.clean()


@pytest.mark.django_db
class TestCohortNameUniqueness:
    """Cohort names are unique per organisation, not per site -- a name that
    used to clash across the whole site is now allowed once per organisation."""

    def test_two_cohorts_with_one_name_in_one_organisation_are_rejected(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        CohortFactory(organisation=organisation, name="Year 10 Science")

        with pytest.raises(IntegrityError):
            CohortFactory(organisation=organisation, name="Year 10 Science")

    def test_the_same_cohort_name_in_two_organisations_is_permitted(
        self, mock_site_context
    ):
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")

        assert Cohort.objects.filter(name="Year 10 Science").count() == 2


@pytest.mark.django_db
class TestLearnerCourseRegistrationUniqueness:
    """One learner per organisation, one registration each -- the same user
    can hold a registration in two organisations because each organisation
    gives them a distinct Learner row."""

    def test_two_registrations_for_one_learner_and_course_are_rejected(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, collection=course)

        with pytest.raises(IntegrityError):
            LearnerCourseRegistrationFactory(learner=learner, collection=course)

    def test_one_user_may_register_for_one_course_through_two_organisations(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        learner_a = LearnerFactory(user=user, organisation=OrganisationFactory())
        learner_b = LearnerFactory(user=user, organisation=OrganisationFactory())
        LearnerCourseRegistrationFactory(learner=learner_a, collection=course)
        LearnerCourseRegistrationFactory(learner=learner_b, collection=course)

        assert (
            LearnerCourseRegistration.objects.filter(
                learner__user=user, collection=course
            ).count()
            == 2
        )


@pytest.mark.django_db
class TestDeactivatingALearnerPreservesRecords:
    """Removal is soft and never cascades: every enrolment and progress row a
    removed learner held stays exactly as it was. Only access is suspended."""

    def test_the_course_registration_stays_active(self, mock_site_context):
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner)

        learner.is_active = False
        learner.save()

        registration.refresh_from_db()
        assert registration.is_active is True

    def test_the_cohort_membership_survives(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        membership = CohortMembershipFactory(
            learner=learner, cohort=CohortFactory(organisation=organisation)
        )

        learner.is_active = False
        learner.save()

        assert CohortMembership.objects.filter(pk=membership.pk).exists()

    def test_the_progress_rows_survive(self, mock_site_context):
        learner = LearnerFactory()
        progress = TopicProgressFactory(user=learner.user)

        learner.is_active = False
        learner.save()

        assert TopicProgress.objects.filter(pk=progress.pk).exists()

    def test_access_to_the_registered_course_is_suspended(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, collection=course)

        learner.is_active = False
        learner.save()

        assert is_registered_for_course(learner.user, course) is False
