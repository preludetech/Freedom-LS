"""Tests for the enrolment models repointed at Learner."""

from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import CohortMembership
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
