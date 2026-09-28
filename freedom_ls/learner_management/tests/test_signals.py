"""Tests for the post_save receiver that keeps OrganisationMember in step
with every organisation or cohort grant.

Registered in LearnerManagementConfig.ready(); role_based_permissions never
imports learner_management, so the assignment utilities themselves stay
unaware this happens.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import OrganisationMember
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role


@pytest.mark.django_db
def test_assign_object_role_on_a_cohort_creates_an_active_member_for_its_organisation(
    mock_site_context,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()

    assign_object_role(user, cohort, "cohort_admin")

    assert OrganisationMember.objects.filter(
        user=user, organisation=organisation, is_active=True
    ).exists()


@pytest.mark.django_db
def test_a_grant_leaves_an_existing_inactive_member_inactive(
    mock_site_context,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    OrganisationMember.objects.create(
        user=user, organisation=organisation, is_active=False
    )

    assign_object_role(user, cohort, "cohort_admin")

    member = OrganisationMember.objects.get(user=user, organisation=organisation)
    assert member.is_active is False


@pytest.mark.django_db
def test_a_site_admin_assignment_creates_no_organisation_member(
    mock_site_context,
) -> None:
    user = UserFactory()

    assign_site_role(user, "site_admin")

    assert not OrganisationMember.objects.filter(user=user).exists()
