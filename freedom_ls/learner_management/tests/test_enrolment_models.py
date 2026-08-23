"""Tests for the enrolment models repointed at Learner."""

from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.factories import OrganisationFactory

# Cohort is created directly rather than through CohortFactory: factories.py
# still imports the pre-rename model names, so importing it here would break
# collection of this file.


@pytest.mark.django_db
class TestCohortMembershipClean:
    def test_rejects_a_learner_and_cohort_in_different_organisations(
        self, mock_site_context
    ):
        learner = Learner.objects.create(
            user=UserFactory(), organisation=OrganisationFactory()
        )
        cohort = Cohort.objects.create(
            organisation=OrganisationFactory(), name="Year 10 Science"
        )

        membership = CohortMembership(learner=learner, cohort=cohort)

        with pytest.raises(ValidationError):
            membership.clean()

    def test_permits_a_learner_and_cohort_in_the_same_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = Learner.objects.create(user=UserFactory(), organisation=organisation)
        cohort = Cohort.objects.create(organisation=organisation, name="Year 10 Maths")

        membership = CohortMembership(learner=learner, cohort=cohort)

        membership.clean()
