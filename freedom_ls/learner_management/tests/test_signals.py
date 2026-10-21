"""Tests for the post_save receiver that keeps OrganisationMember in step
with every organisation or cohort grant.

Registered in LearnerManagementConfig.ready(); role_based_permissions never
imports learner_management, so the assignment utilities themselves stay
unaware this happens.
"""

from __future__ import annotations

import pytest
from guardian.models import UserObjectPermission

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Model
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort, OrganisationMember
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.factories import ObjectRoleAssignmentFactory
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role
from freedom_ls.tests.site_context import site_context


def _role_rows_on(target: Model) -> tuple[int, int]:
    """Counts of (assignments, guardian rows) on `target`, whatever the site."""
    target_type = ContentType.objects.get_for_model(target)
    return (
        ObjectRoleAssignment._base_manager.filter(
            content_type=target_type, object_id=str(target.pk)
        ).count(),
        UserObjectPermission.objects.filter(
            content_type=target_type, object_pk=str(target.pk)
        ).count(),
    )


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


@pytest.mark.django_db
def test_deleting_a_cohort_removes_its_active_and_inactive_assignments(
    mock_site_context,
) -> None:
    cohort = CohortFactory()
    assign_object_role(UserFactory(), cohort, "cohort_admin")
    ObjectRoleAssignmentFactory(
        target_object=cohort, role="cohort_viewer", is_active=False
    )

    cohort.delete()

    assert ObjectRoleAssignment._base_manager.count() == 0


@pytest.mark.django_db
def test_deleting_a_cohort_removes_its_guardian_rows(mock_site_context) -> None:
    cohort = CohortFactory()
    cohort_type = ContentType.objects.get_for_model(cohort)
    cohort_pk = str(cohort.pk)
    assign_object_role(UserFactory(), cohort, "cohort_admin")

    cohort.delete()

    assert not UserObjectPermission.objects.filter(
        content_type=cohort_type, object_pk=cohort_pk
    ).exists()


@pytest.mark.django_db
def test_deleting_a_cohort_leaves_another_cohorts_rows_alone(
    mock_site_context,
) -> None:
    cohort = CohortFactory()
    other = CohortFactory()
    assign_object_role(UserFactory(), other, "cohort_admin")
    before = _role_rows_on(other)

    cohort.delete()

    assert _role_rows_on(other) == before


@pytest.mark.django_db
def test_deleting_a_cohort_leaves_its_organisations_rows_alone(
    mock_site_context,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    assign_object_role(UserFactory(), organisation, "organisation_admin")
    before = _role_rows_on(organisation)

    cohort.delete()

    assert _role_rows_on(organisation) == before


@pytest.mark.django_db
def test_deleting_a_cohort_with_no_site_context_removes_its_rows(site: Site) -> None:
    with site_context(site):
        cohort = CohortFactory()
        cohort_type = ContentType.objects.get_for_model(cohort)
        cohort_pk = str(cohort.pk)
        assign_object_role(UserFactory(), cohort, "cohort_admin")

    Cohort._base_manager.get(pk=cohort_pk).delete()

    assert (
        ObjectRoleAssignment._base_manager.filter(
            content_type=cohort_type, object_id=cohort_pk
        ).count()
        == 0
    )
    assert not UserObjectPermission.objects.filter(
        content_type=cohort_type, object_pk=cohort_pk
    ).exists()


@pytest.mark.django_db
def test_deleting_a_cohort_from_the_interface_removes_its_rows(
    mock_site_context, logged_in_client
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    assign_object_role(UserFactory(), cohort, "cohort_admin")
    cohort_type = ContentType.objects.get_for_model(cohort)
    cohort_pk = str(cohort.pk)
    client: Client = logged_in_client(UserFactory(superuser=True))
    url = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort_pk}/__tabs/settings/__actions/delete",
        },
    )

    response = client.delete(url)

    assert response.status_code == 204
    assert (
        ObjectRoleAssignment._base_manager.filter(
            content_type=cohort_type, object_id=cohort_pk
        ).count()
        == 0
    )
    assert not UserObjectPermission.objects.filter(
        content_type=cohort_type, object_pk=cohort_pk
    ).exists()
