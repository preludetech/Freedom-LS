"""The organisation-scoped uniqueness constraints on Cohort and
UserCourseRegistration.

Both were widened to include organisation, so a name or a registration that
used to clash across the whole site is now allowed once per organisation.
The widening is only half the rule -- these pin that each constraint still
rejects a genuine duplicate *within* one organisation.
"""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import Cohort, UserCourseRegistration
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
class TestCohortNameUniqueness:
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
class TestRegistrationUniqueness:
    def test_two_registrations_for_one_user_course_and_organisation_are_rejected(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation = OrganisationFactory()
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation
        )

        with pytest.raises(IntegrityError):
            UserCourseRegistrationFactory(
                user=user, collection=course, organisation=organisation
            )

    def test_one_user_may_register_for_one_course_through_two_organisations(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=OrganisationFactory()
        )
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=OrganisationFactory()
        )

        assert (
            UserCourseRegistration.objects.filter(user=user, collection=course).count()
            == 2
        )
