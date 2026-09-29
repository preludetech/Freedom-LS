"""Tests for the checked assignment utilities: assign_role, remove_role and
set_organisation_member_active."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch

import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.test.utils import CaptureQueriesContext

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    OrganisationMemberFactory,
)
from freedom_ls.learner_management.models import OrganisationMember
from freedom_ls.learner_management.role_assignment import (
    CHANGE_MEMBER,
    assign_role,
    remove_role,
    set_organisation_member_active,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
)
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role


@pytest.fixture(autouse=True)
def _clear_role_caches():
    """Every test here assigns roles or reads role config; keep them isolated."""
    clear_caches()
    yield
    clear_caches()


@pytest.mark.django_db
def test_a_grantor_cannot_change_their_own_role(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, grantor, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.SELF
    assert not ObjectRoleAssignment.objects.filter(
        user=grantor, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_assigning_to_an_inactive_user_is_refused(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")
    inactive_user = UserFactory(is_active=False)

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, inactive_user, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.INACTIVE_USER
    assert not ObjectRoleAssignment.objects.filter(
        user=inactive_user, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_a_grantor_without_the_capability_is_refused(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    user = UserFactory()

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, user, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED
    assert not ObjectRoleAssignment.objects.filter(
        user=user, role="organisation_admin"
    ).exists()


@pytest.mark.django_db
def test_an_organisation_admin_assigning_in_another_organisation_is_refused(
    mock_site_context: Site,
) -> None:
    own_organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_object_role(grantor, own_organisation, "organisation_admin")
    cohort = CohortFactory(organisation=other_organisation)
    user = UserFactory()

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, user, "cohort_viewer", cohort)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_a_cohort_admin_assigning_anything_is_refused(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")
    user = UserFactory()

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, user, "cohort_viewer", cohort)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_a_site_admin_removing_the_last_organisation_admin_succeeds(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")

    remove_role(grantor, admin, "organisation_admin", organisation)

    assert not ObjectRoleAssignment.objects.filter(
        user=admin, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_the_last_organisation_admin_removing_themselves_is_refused_as_self(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        remove_role(admin, admin, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.SELF
    assert ObjectRoleAssignment.objects.filter(
        user=admin, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_deactivating_the_last_organisation_admins_membership_is_refused(
    mock_site_context: Site, settings
) -> None:
    """A custom role can carry change_organisationmember without counting
    toward the quorum active_organisation_admins tracks -- the lock keys off
    the organisation_admin role specifically, not off whoever holds the
    capability, so an org_helper-style role never lets an org empty out."""
    organisation = OrganisationFactory()
    admin = UserFactory()
    actor = UserFactory()

    module_path = "fake_permissions_module_for_test_role_assignment"
    fake_module = ModuleType(module_path)
    fake_module.ROLES = SiteRolesConfig(
        {
            "organisation_admin": Role(
                display_name="Organisation admin",
                permissions=frozenset(),
                assignment_scope=SCOPE_OBJECT,
            ),
            "org_helper": Role(
                display_name="Org helper",
                permissions=frozenset({CHANGE_MEMBER}),
                assignment_scope=SCOPE_OBJECT,
            ),
        }
    )
    settings.FREEDOMLS_PERMISSIONS_MODULES = {mock_site_context.name: module_path}

    with patch(
        "freedom_ls.role_based_permissions.loader.import_module",
        return_value=fake_module,
    ):
        clear_caches()
        assign_object_role(admin, organisation, "organisation_admin")
        assign_object_role(actor, organisation, "org_helper")
        member = OrganisationMember.objects.get(user=admin, organisation=organisation)

        with pytest.raises(RoleChangeRefused) as exc_info:
            set_organisation_member_active(actor, member, False)

    assert exc_info.value.reason == RefusalReason.LAST_ORGANISATION_ADMIN
    member.refresh_from_db()
    assert member.is_active is True


@pytest.mark.django_db
def test_assigning_to_a_user_with_an_inactive_organisation_member_leaves_it_inactive(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    OrganisationMemberFactory(organisation=organisation, user=user, is_active=False)

    assign_role(grantor, user, "cohort_viewer", cohort)

    assert ObjectRoleAssignment.objects.filter(
        user=user, role="cohort_viewer", is_active=True
    ).exists()
    member = OrganisationMember.objects.get(user=user, organisation=organisation)
    assert member.is_active is False


@pytest.mark.django_db
def test_removing_site_admin_through_remove_role_surfaces_last_site_admin(
    mock_site_context: Site,
) -> None:
    grantor = UserFactory(superuser=True)
    sole_admin = UserFactory()
    assign_site_role(sole_admin, "site_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        remove_role(grantor, sole_admin, "site_admin", mock_site_context)

    assert exc_info.value.reason == RefusalReason.LAST_SITE_ADMIN
    assert SiteRoleAssignment.objects.filter(
        user=sole_admin, role="site_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_removing_an_organisation_admin_locks_the_organisation_row(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")
    other_admin = UserFactory()
    assign_object_role(other_admin, organisation, "organisation_admin")

    with CaptureQueriesContext(connection) as captured:
        remove_role(grantor, other_admin, "organisation_admin", organisation)

    assert any(
        "freedom_ls_organisations_organisation" in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )
