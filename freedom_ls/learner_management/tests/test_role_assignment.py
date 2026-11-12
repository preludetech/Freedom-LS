"""Tests for the checked assignment utilities: assign_role, deactivate_role and
set_staff_member_active."""

from __future__ import annotations

from types import ModuleType
from typing import cast
from unittest.mock import patch

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries, SettingsWrapper

from django.contrib.sites.models import Site
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_management.factories import (
    CohortFactory,
    StaffMemberFactory,
)
from freedom_ls.learner_management.models import StaffMember
from freedom_ls.learner_management.role_assignment import (
    ASSIGN,
    CHANGE_STAFF_MEMBER,
    add_staff_member,
    assign_role,
    deactivate_role,
    grantable_roles,
    is_last_organisation_admin,
    is_site_level_admin,
    set_staff_member_active,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
)
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role
from freedom_ls.tests.audit_assertions import assert_entry
from freedom_ls.tests.factories import SiteFactory


@pytest.fixture(autouse=True)
def _clear_role_caches():
    """Every test here assigns roles or reads role config; keep them isolated."""
    clear_caches()
    yield
    clear_caches()


@pytest.mark.django_db
def test_a_cohort_admin_may_give_themselves_a_cohort_role_on_their_cohort(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")

    assign_role(grantor, grantor, "cohort_viewer", cohort)

    assert ObjectRoleAssignment.objects.filter(
        user=grantor, role="cohort_viewer", is_active=True
    ).exists()


@pytest.mark.django_db
def test_a_cohort_admin_may_not_give_themselves_a_role_they_cannot_give(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, grantor, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_a_site_role_cannot_be_changed_by_its_holder(mock_site_context: Site) -> None:
    grantor = UserFactory(superuser=True)

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, grantor, "site_admin", mock_site_context)

    assert exc_info.value.reason == RefusalReason.SELF


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
def test_a_cohort_admin_assigning_an_organisation_role_is_refused(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")
    user = UserFactory()

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, user, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_an_organisation_role_on_a_cohort_is_refused(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, UserFactory(), "organisation_staff_viewer", cohort)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_a_cohort_role_on_an_organisation_is_refused(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)

    with pytest.raises(RoleChangeRefused) as exc_info:
        assign_role(grantor, UserFactory(), "cohort_viewer", organisation)

    assert exc_info.value.reason == RefusalReason.NOT_PERMITTED


@pytest.mark.django_db
def test_an_organisation_admin_may_grant_the_viewer_roles_on_the_whole_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")

    grantable = {
        g.role: g.cohorts
        for g in grantable_roles(grantor, organisation)
        if g.role.startswith("organisation_staff")
    }

    assert grantable == {
        "organisation_staff_viewer": None,
        "organisation_staff_roles_viewer": None,
    }


@pytest.mark.django_db
def test_a_cohort_admin_may_not_grant_the_viewer_roles(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")

    roles = [g.role for g in grantable_roles(grantor, organisation)]

    assert not [role for role in roles if role.startswith("organisation_")]


@pytest.mark.django_db
def test_a_cohort_admin_may_grant_cohort_admin_on_their_own_cohorts(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Own")
    CohortFactory(organisation=organisation, name="Other")
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_admin")

    assert _grantable(grantor, organisation) == [
        ("cohort_admin", ["Own"]),
        ("cohort_viewer", ["Own"]),
    ]


@pytest.mark.django_db
def test_a_site_admin_removing_the_last_organisation_admin_succeeds(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")

    deactivate_role(grantor, admin, "organisation_admin", organisation)

    assert not ObjectRoleAssignment.objects.filter(
        user=admin, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_the_last_organisation_admin_removing_themselves_is_refused_by_the_lock(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        deactivate_role(admin, admin, "organisation_admin", organisation)

    assert exc_info.value.reason == RefusalReason.LAST_ORGANISATION_ADMIN
    assert ObjectRoleAssignment.objects.filter(
        user=admin, role="organisation_admin", is_active=True
    ).exists()


def _organisation_admin(organisation: Organisation) -> User:
    admin = cast(User, UserFactory())
    assign_object_role(admin, organisation, "organisation_admin")
    return admin


def _site_admin() -> User:
    admin = cast(User, UserFactory())
    assign_site_role(admin, "site_admin")
    return admin


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_grantor",
    [
        _organisation_admin,
        lambda organisation: _site_admin(),
        lambda organisation: UserFactory(superuser=True),
    ],
    ids=["organisation_admin", "site_admin", "superuser"],
)
def test_an_admin_adds_and_deactivates_their_own_roles(
    mock_site_context: Site, make_grantor
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    _organisation_admin(organisation)
    grantor = make_grantor(organisation)

    assign_role(grantor, grantor, "cohort_viewer", cohort)
    deactivate_role(grantor, grantor, "cohort_viewer", cohort)

    assert not ObjectRoleAssignment.objects.filter(
        user=grantor, role="cohort_viewer", is_active=True
    ).exists()


@pytest.mark.django_db
def test_an_organisation_admin_deactivates_their_own_role_while_another_remains(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = _organisation_admin(organisation)
    _organisation_admin(organisation)

    deactivate_role(admin, admin, "organisation_admin", organisation)

    assert not ObjectRoleAssignment.objects.filter(
        user=admin, role="organisation_admin", is_active=True
    ).exists()


@pytest.mark.django_db
def test_deactivating_ones_own_staff_member_row_is_refused_as_self(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = _organisation_admin(organisation)
    _organisation_admin(organisation)
    member = StaffMember.objects.get(user=admin, organisation=organisation)

    with pytest.raises(RoleChangeRefused) as exc_info:
        set_staff_member_active(admin, member, False)

    assert exc_info.value.reason == RefusalReason.SELF


@pytest.mark.django_db
def test_deactivating_the_last_organisation_admins_membership_is_refused(
    mock_site_context: Site, settings
) -> None:
    """A custom role can carry change_staffmember without counting
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
                permissions=frozenset({CHANGE_STAFF_MEMBER}),
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
        member = StaffMember.objects.get(user=admin, organisation=organisation)

        with pytest.raises(RoleChangeRefused) as exc_info:
            set_staff_member_active(actor, member, False)

    assert exc_info.value.reason == RefusalReason.LAST_ORGANISATION_ADMIN
    member.refresh_from_db()
    assert member.is_active is True


@pytest.mark.django_db
def test_assigning_to_a_user_with_an_inactive_staff_member_leaves_it_inactive(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin")
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    StaffMemberFactory(organisation=organisation, user=user, is_active=False)

    assign_role(grantor, user, "cohort_viewer", cohort)

    assert ObjectRoleAssignment.objects.filter(
        user=user, role="cohort_viewer", is_active=True
    ).exists()
    member = StaffMember.objects.get(user=user, organisation=organisation)
    assert member.is_active is False


@pytest.mark.django_db
def test_removing_site_admin_through_remove_role_surfaces_last_site_admin(
    mock_site_context: Site,
) -> None:
    grantor = UserFactory(superuser=True)
    sole_admin = UserFactory()
    assign_site_role(sole_admin, "site_admin")

    with pytest.raises(RoleChangeRefused) as exc_info:
        deactivate_role(grantor, sole_admin, "site_admin", mock_site_context)

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
        deactivate_role(grantor, other_admin, "organisation_admin", organisation)

    assert any(
        "freedom_ls_organisations_organisation" in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )


def _locks_the_organisation_row(captured: CaptureQueriesContext) -> bool:
    return any(
        "freedom_ls_organisations_organisation" in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )


@pytest.mark.django_db
def test_suspending_a_member_who_is_no_organisation_admin_takes_no_lock(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")
    viewer = UserFactory()
    assign_object_role(viewer, cohort, "cohort_viewer")
    member = StaffMember.objects.get(user=viewer, organisation=organisation)

    with CaptureQueriesContext(connection) as captured:
        set_staff_member_active(grantor, member, False)

    assert not _locks_the_organisation_row(captured)
    member.refresh_from_db()
    assert member.is_active is False


@pytest.mark.django_db
def test_removing_a_cohort_role_takes_no_lock(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")
    viewer = UserFactory()
    assign_object_role(viewer, cohort, "cohort_viewer")

    with CaptureQueriesContext(connection) as captured:
        deactivate_role(grantor, viewer, "cohort_viewer", cohort)

    assert not _locks_the_organisation_row(captured)


def _grantable(
    grantor: User, organisation: Organisation
) -> list[tuple[str, list[str] | None]]:
    return [
        (g.role, None if g.cohorts is None else [c.name for c in g.cohorts])
        for g in grantable_roles(grantor, organisation)
    ]


@pytest.mark.django_db
def test_a_superuser_may_grant_every_role_on_every_active_cohort(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort_b = CohortFactory(organisation=organisation, name="B")
    cohort_a = CohortFactory(organisation=organisation, name="A")

    result = _grantable(UserFactory(superuser=True), organisation)

    assert result == [
        ("organisation_admin", None),
        ("organisation_staff_viewer", None),
        ("organisation_staff_roles_viewer", None),
        ("cohort_admin", [cohort_a.name, cohort_b.name]),
        ("cohort_viewer", [cohort_a.name, cohort_b.name]),
    ]


@pytest.mark.django_db
def test_a_site_admin_may_grant_every_role_on_every_active_cohort(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_site_role(grantor, "site_admin", site=mock_site_context)

    result = _grantable(grantor, organisation)

    assert result == [
        ("organisation_admin", None),
        ("organisation_staff_viewer", None),
        ("organisation_staff_roles_viewer", None),
        ("cohort_admin", [cohort.name]),
        ("cohort_viewer", [cohort.name]),
    ]


@pytest.mark.django_db
def test_an_organisation_admin_may_grant_every_role_on_every_active_cohort(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")

    result = _grantable(grantor, organisation)

    assert result == [
        ("organisation_admin", None),
        ("organisation_staff_viewer", None),
        ("organisation_staff_roles_viewer", None),
        ("cohort_admin", [cohort.name]),
        ("cohort_viewer", [cohort.name]),
    ]


@pytest.mark.django_db
def test_a_cohort_viewer_may_grant_nothing(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, cohort, "cohort_viewer")

    assert grantable_roles(grantor, organisation) == []


@pytest.mark.django_db
def test_a_user_with_no_role_may_grant_nothing(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation)

    assert grantable_roles(UserFactory(), organisation) == []


@pytest.mark.django_db
def test_an_inactive_cohort_is_not_grantable(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    active = CohortFactory(organisation=organisation, name="Active")
    CohortFactory(organisation=organisation, name="Inactive", is_active=False)
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")

    result = _grantable(grantor, organisation)

    assert result[3:] == [
        ("cohort_admin", [active.name]),
        ("cohort_viewer", [active.name]),
    ]


@pytest.mark.django_db
def test_a_downstream_role_is_never_grantable(
    mock_site_context: Site, settings: SettingsWrapper
) -> None:
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    module_path = "fake_permissions_module_for_grantable_roles"
    fake_module = ModuleType(module_path)
    fake_module.ROLES = SiteRolesConfig(
        {
            **BASE_ROLES,
            "org_helper": Role(
                display_name="Org helper",
                permissions=frozenset({ASSIGN.format(role="org_helper")}),
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
        roles = [g.role for g in grantable_roles(grantor, organisation)]

    assert "org_helper" not in roles


@pytest.mark.django_db
def test_grantable_roles_query_count_does_not_grow_with_cohorts(
    mock_site_context: Site, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation)
    grantor = UserFactory()
    assign_object_role(grantor, organisation, "organisation_admin")
    with CaptureQueriesContext(connection) as one_cohort:
        grantable_roles(grantor, organisation)
    CohortFactory.create_batch(5, organisation=organisation)

    with django_assert_max_num_queries(len(one_cohort)):
        grantable_roles(grantor, organisation)


@pytest.mark.django_db
def test_a_superuser_is_a_site_level_admin(mock_site_context: Site) -> None:
    assert is_site_level_admin(UserFactory(superuser=True), mock_site_context)


@pytest.mark.django_db
def test_an_active_site_admin_is_a_site_level_admin(mock_site_context: Site) -> None:
    user = UserFactory()
    assign_site_role(user, "site_admin", site=mock_site_context)

    assert is_site_level_admin(user, mock_site_context)


@pytest.mark.django_db
def test_an_organisation_admin_is_not_a_site_level_admin(
    mock_site_context: Site,
) -> None:
    user = UserFactory()
    assign_object_role(user, OrganisationFactory(), "organisation_admin")

    assert not is_site_level_admin(user, mock_site_context)


@pytest.mark.django_db
def test_the_sole_active_admin_is_the_last_organisation_admin(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")

    assert is_last_organisation_admin(organisation, admin)


@pytest.mark.django_db
def test_an_admin_is_not_the_last_when_another_active_admin_exists(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = UserFactory()
    assign_object_role(admin, organisation, "organisation_admin")
    assign_object_role(UserFactory(), organisation, "organisation_admin")

    assert not is_last_organisation_admin(organisation, admin)


@pytest.mark.django_db
def test_a_user_without_the_admin_role_is_not_the_last_organisation_admin(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    assign_object_role(UserFactory(), organisation, "organisation_admin")

    assert not is_last_organisation_admin(organisation, UserFactory())


@pytest.mark.django_db
class TestMemberAndRoleAudit:
    def _member(self, organisation: Organisation) -> StaffMember:
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")
        member: StaffMember = StaffMember.objects.get(
            user=user, organisation=organisation
        )
        return member

    def test_suspending_writes_an_entry_with_the_user_as_a_subject(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        actor = UserFactory(superuser=True)
        member = StaffMemberFactory(organisation=organisation)

        set_staff_member_active(actor, member, False, reason="Left")

        assert_entry(
            action="staff_member.deactivated",
            actor=actor,
            target=member,
            target_label=member.user.display_name,
            organisation=organisation,
            subjects=(member.user,),
            reason="Left",
        )

    def test_suspending_a_suspended_member_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        actor = UserFactory(superuser=True)
        member = StaffMemberFactory(is_active=False)

        set_staff_member_active(actor, member, False)

        assert AuditLogEntry.unscoped.count() == 0

    def test_reactivating_writes_member_reactivated(
        self, mock_site_context: Site
    ) -> None:
        actor = UserFactory(superuser=True)
        member = StaffMemberFactory(is_active=False)

        set_staff_member_active(actor, member, True)

        assert AuditLogEntry.unscoped.get().action == "staff_member.reactivated"

    def test_a_change_already_made_by_another_request_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        """The stored row decides whether anything changed, not the caller's
        instance, which another request may have overtaken."""
        actor = UserFactory(superuser=True)
        member = StaffMemberFactory(is_active=False)
        StaffMember._base_manager.filter(pk=member.pk).update(is_active=True)

        set_staff_member_active(actor, member, True)

        assert AuditLogEntry.unscoped.count() == 0

    def test_a_refused_suspension_writes_nothing(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        member = self._member(organisation)
        before = AuditLogEntry.unscoped.count()

        with pytest.raises(RoleChangeRefused):
            set_staff_member_active(member.user, member, False)

        assert AuditLogEntry.unscoped.count() == before

    @pytest.mark.django_db(transaction=True)
    def test_a_rolled_back_outer_transaction_leaves_no_entry(
        self, mock_site_context: Site
    ) -> None:
        actor = UserFactory(superuser=True)
        member = StaffMemberFactory()

        def deactivate() -> None:
            with transaction.atomic():
                set_staff_member_active(actor, member, False)
                raise RuntimeError

        with pytest.raises(RuntimeError):
            deactivate()

        assert AuditLogEntry.unscoped.count() == 0

    def test_remove_role_passes_the_reason_through(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        grantor = UserFactory(superuser=True)
        user = UserFactory()
        assign_role(grantor, user, "cohort_admin", cohort)

        deactivate_role(grantor, user, "cohort_admin", cohort, reason="Moved teams")

        assert (
            AuditLogEntry.unscoped.get(action="role.deactivated").reason
            == "Moved teams"
        )


@pytest.mark.django_db
class TestAddStaffMember:
    def _admin(self, organisation: Organisation) -> User:
        admin = cast(User, UserFactory())
        assign_object_role(admin, organisation, "organisation_admin")
        return admin

    def test_an_organisation_admin_adds_a_staff_member_with_one_entry(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        admin = UserFactory(superuser=True)
        user = UserFactory()

        staff_member = add_staff_member(admin, user, organisation)

        assert staff_member.is_active is True
        assert StaffMember.objects.get(user=user, organisation=organisation) == (
            staff_member
        )
        assert_entry(
            action="staff_member.added",
            actor=admin,
            target=staff_member,
            target_label=user.display_name,
            organisation=organisation,
            subjects=(user,),
        )

    def test_a_cohort_admin_is_refused(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        cohort_admin = UserFactory()
        assign_object_role(
            cohort_admin, CohortFactory(organisation=organisation), "cohort_admin"
        )
        user = UserFactory()

        with pytest.raises(RoleChangeRefused) as exc_info:
            add_staff_member(cohort_admin, user, organisation)

        assert exc_info.value.reason == RefusalReason.NOT_PERMITTED
        assert not StaffMember.objects.filter(user=user).exists()

    @pytest.mark.parametrize(
        ("is_active", "reason"),
        [
            (True, RefusalReason.ALREADY_STAFF),
            (False, RefusalReason.INACTIVE_STAFF_MEMBER),
        ],
    )
    def test_an_existing_row_is_refused_by_its_state(
        self, mock_site_context: Site, is_active: bool, reason: RefusalReason
    ) -> None:
        organisation = OrganisationFactory()
        admin = self._admin(organisation)
        existing = StaffMemberFactory(organisation=organisation, is_active=is_active)

        with pytest.raises(RoleChangeRefused) as exc_info:
            add_staff_member(admin, existing.user, organisation)

        assert exc_info.value.reason == reason
        assert AuditLogEntry.unscoped.filter(action="staff_member.added").count() == 0

    def test_a_role_holder_with_no_row_is_refused_as_inactive(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        admin = self._admin(organisation)
        user = UserFactory()
        assign_object_role(
            user, CohortFactory(organisation=organisation), "cohort_admin"
        )
        StaffMember.objects.filter(user=user).delete()

        with pytest.raises(RoleChangeRefused) as exc_info:
            add_staff_member(admin, user, organisation)

        assert exc_info.value.reason == RefusalReason.INACTIVE_STAFF_MEMBER
        assert not StaffMember.objects.filter(user=user).exists()

    def test_an_inactive_account_is_refused(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        admin = self._admin(organisation)

        with pytest.raises(RoleChangeRefused) as exc_info:
            add_staff_member(admin, UserFactory(is_active=False), organisation)

        assert exc_info.value.reason == RefusalReason.INACTIVE_USER

    def test_a_user_on_another_site_is_refused(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        admin = self._admin(organisation)
        away = User._base_manager.create(site=SiteFactory(), email="away@example.com")

        with pytest.raises(RoleChangeRefused) as exc_info:
            add_staff_member(admin, away, organisation)

        assert exc_info.value.reason == RefusalReason.NOT_PERMITTED
        assert not StaffMember._base_manager.filter(user=away).exists()
