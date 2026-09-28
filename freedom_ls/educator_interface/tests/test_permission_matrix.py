"""The permission matrix: can() answers exactly what the spec's table allows.

MATRIX is a hand-written transcription of the spec's table, reviewed against
it and never parsed from it. This slice wires only the rows it touches --
the organisation dashboard's view row, and cohort create/edit/delete.
Slices 6 and 7 widen MATRIX and CAPABILITY_SCOPE_KINDS to the rest of the
table.

The world: site A has organisation O1 (cohorts C1 granted and C2, learners L1
in C1 and L2 in C2) and O2 (C3, L3). Site B has O3 (C4, L4). Grants:
site_admin on site A, organisation_admin on O1, cohort_admin and
cohort_viewer on C1.
"""

from __future__ import annotations

from typing import NamedTuple, cast

import pytest
from guardian.shortcuts import get_perms

from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedAction,
    walk_interface,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner, OrganisationMember
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learners_visible_to,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

#: Roles whose grants are gated on an active OrganisationMember. site_admin's
#: grant is a SiteRoleAssignment, which _site_grants never gates.
GATED_ROLES = ("organisation_admin", "cohort_admin", "cohort_viewer")

ROLES = ("site_admin", "organisation_admin", "cohort_admin", "cohort_viewer")

OWN = "own"
OTHER_COHORT = "other_cohort"
OTHER_ORGANISATION = "other_organisation"
OTHER_SITE = "other_site"

#: Which relations make sense for a scope object of this kind -- an
#: organisation has no "other cohort" position to test.
RELATIONS_FOR_KIND: dict[str, tuple[str, ...]] = {
    "organisation": (OWN, OTHER_ORGANISATION, OTHER_SITE),
    "cohort": (OWN, OTHER_COHORT, OTHER_ORGANISATION, OTHER_SITE),
    "learner": (OWN, OTHER_COHORT, OTHER_ORGANISATION, OTHER_SITE),
}

VIEW_ORGANISATION = "freedom_ls_organisations.view_organisation"
VIEW_COHORT = "freedom_ls_learner_management.view_cohort"
VIEW_LEARNER = "freedom_ls_learner_management.view_learner"
ADD_COHORT = "freedom_ls_learner_management.add_cohort"
CHANGE_COHORT = "freedom_ls_learner_management.change_cohort"
DELETE_COHORT = "freedom_ls_learner_management.delete_cohort"

# capability -> role -> the (scope kind, relation) pairs where can() is True.
MATRIX: dict[str, dict[str, set[tuple[str, str]]]] = {
    VIEW_ORGANISATION: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    VIEW_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "cohort_admin": {("cohort", OWN)},
        "cohort_viewer": {("cohort", OWN)},
    },
    VIEW_LEARNER: {
        "site_admin": {
            ("learner", OWN),
            ("learner", OTHER_COHORT),
            ("learner", OTHER_ORGANISATION),
        },
        "organisation_admin": {("learner", OWN), ("learner", OTHER_COHORT)},
        "cohort_admin": {("learner", OWN)},
        "cohort_viewer": {("learner", OWN)},
    },
    ADD_COHORT: {
        "site_admin": {("organisation", OWN), ("organisation", OTHER_ORGANISATION)},
        "organisation_admin": {("organisation", OWN)},
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    CHANGE_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
    DELETE_COHORT: {
        "site_admin": {
            ("cohort", OWN),
            ("cohort", OTHER_COHORT),
            ("cohort", OTHER_ORGANISATION),
        },
        "organisation_admin": {("cohort", OWN), ("cohort", OTHER_COHORT)},
        "cohort_admin": set(),
        "cohort_viewer": set(),
    },
}

#: Which scope kinds each capability is asked of.
CAPABILITY_SCOPE_KINDS: dict[str, tuple[str, ...]] = {
    VIEW_ORGANISATION: ("organisation",),
    VIEW_COHORT: ("cohort",),
    VIEW_LEARNER: ("learner",),
    ADD_COHORT: ("organisation",),
    CHANGE_COHORT: ("cohort",),
    DELETE_COHORT: ("cohort",),
}


class World(NamedTuple):
    """One grant holder per role, and one scope object per (kind, relation)."""

    users: dict[str, User]
    scopes: dict[tuple[str, str], Model]


def _build_world(site_a: Site) -> World:
    site_b = SiteFactory()

    o1 = OrganisationFactory()
    o2 = OrganisationFactory()
    o3 = OrganisationFactory(site=site_b)

    c1 = CohortFactory(organisation=o1)
    c2 = CohortFactory(organisation=o1)
    c3 = CohortFactory(organisation=o2)
    c4 = CohortFactory(organisation=o3, site=site_b)

    l1 = LearnerFactory(organisation=o1)
    l2 = LearnerFactory(organisation=o1)
    l3 = LearnerFactory(organisation=o2)
    l4 = LearnerFactory(organisation=o3)

    CohortMembershipFactory(cohort=c1, learner=l1)
    CohortMembershipFactory(cohort=c2, learner=l2)
    CohortMembershipFactory(cohort=c3, learner=l3)
    CohortMembershipFactory(cohort=c4, learner=l4, site=site_b)

    site_admin_user = UserFactory()
    assign_site_role(site_admin_user, "site_admin", site=site_a)

    organisation_admin_user = UserFactory()
    assign_object_role(organisation_admin_user, o1, "organisation_admin")

    cohort_admin_user = UserFactory()
    assign_object_role(cohort_admin_user, c1, "cohort_admin")

    cohort_viewer_user = UserFactory()
    assign_object_role(cohort_viewer_user, c1, "cohort_viewer")

    # factory_boy's metaclass makes mypy see these factories as returning the
    # factory class rather than the model, per pyproject's mypy override --
    # cast() back to the real return types at the one point they leave this
    # function.
    return World(
        users={
            "site_admin": cast(User, site_admin_user),
            "organisation_admin": cast(User, organisation_admin_user),
            "cohort_admin": cast(User, cohort_admin_user),
            "cohort_viewer": cast(User, cohort_viewer_user),
        },
        scopes={
            ("organisation", OWN): cast(Model, o1),
            ("organisation", OTHER_ORGANISATION): cast(Model, o2),
            ("organisation", OTHER_SITE): cast(Model, o3),
            ("cohort", OWN): cast(Model, c1),
            ("cohort", OTHER_COHORT): cast(Model, c2),
            ("cohort", OTHER_ORGANISATION): cast(Model, c3),
            ("cohort", OTHER_SITE): cast(Model, c4),
            ("learner", OWN): cast(Model, l1),
            ("learner", OTHER_COHORT): cast(Model, l2),
            ("learner", OTHER_ORGANISATION): cast(Model, l3),
            ("learner", OTHER_SITE): cast(Model, l4),
        },
    )


def _cases() -> list[tuple[str, str, str, str]]:
    """(capability, role, kind, relation) for every combination MATRIX and
    CAPABILITY_SCOPE_KINDS cover."""
    return [
        (capability, role, kind, relation)
        for capability, kinds in CAPABILITY_SCOPE_KINDS.items()
        for kind in kinds
        for relation in RELATIONS_FOR_KIND[kind]
        for role in ROLES
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(("capability", "role", "kind", "relation"), _cases())
def test_can_matches_the_matrix(
    mock_site_context: Site, capability: str, role: str, kind: str, relation: str
) -> None:
    world = _build_world(mock_site_context)
    user = world.users[role]
    scope = world.scopes[(kind, relation)]

    expected = (kind, relation) in MATRIX[capability][role]

    assert can(user, capability, scope) is expected


def test_every_capability_a_role_holds_has_a_matrix_entry() -> None:
    held_capabilities = {
        capability for role in ROLES for capability in BASE_ROLES[role].permissions
    }

    for capability in held_capabilities:
        assert capability in MATRIX, f"{capability!r} has no MATRIX entry"


def test_every_matrix_entry_names_all_four_roles() -> None:
    for capability, by_role in MATRIX.items():
        assert set(by_role) == set(ROLES), (
            f"{capability!r}'s MATRIX entry does not cover every role"
        )


@pytest.mark.parametrize("role", ROLES)
def test_a_roles_permissions_equal_the_capabilities_its_matrix_column_allows(
    role: str,
) -> None:
    from_matrix = {
        capability for capability, by_role in MATRIX.items() if by_role[role]
    }

    assert BASE_ROLES[role].permissions == from_matrix


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
def test_cohorts_visible_to_agrees_with_can_on_every_cohort(
    mock_site_context: Site, role: str
) -> None:
    """The queryset a list renders and the per-object check gating a row must
    never disagree about which cohorts this role can see."""
    world = _build_world(mock_site_context)
    user = world.users[role]

    for (kind, relation), scope in world.scopes.items():
        if kind != "cohort":
            continue
        cohort = cast(Cohort, scope)
        visible = (
            cohorts_visible_to(user, cohort.organisation).filter(pk=cohort.pk).exists()
        )
        assert visible is can(user, VIEW_COHORT, scope), (role, relation)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
def test_learners_visible_to_agrees_with_can_on_every_learner(
    mock_site_context: Site, role: str
) -> None:
    """Same agreement, on the learner side."""
    world = _build_world(mock_site_context)
    user = world.users[role]

    for (kind, relation), scope in world.scopes.items():
        if kind != "learner":
            continue
        learner = cast(Learner, scope)
        visible = (
            learners_visible_to(user, learner.organisation)
            .filter(pk=learner.pk)
            .exists()
        )
        assert visible is can(user, VIEW_LEARNER, scope), (role, relation)


def _gated_true_cases() -> list[tuple[str, str, str, str]]:
    """Every (capability, role, kind, relation) case _cases() covers where
    the role is one whose grant only counts through an active
    OrganisationMember, and the matrix says the answer is True."""
    return [
        (capability, role, kind, relation)
        for capability, role, kind, relation in _cases()
        if role in GATED_ROLES and (kind, relation) in MATRIX[capability][role]
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("capability", "role", "kind", "relation"), _gated_true_cases()
)
def test_deactivating_the_organisation_member_row_withdraws_the_grant(
    mock_site_context: Site, capability: str, role: str, kind: str, relation: str
) -> None:
    """The OrganisationMember gate: an organisation or cohort grant counts
    only while the grant holder's OrganisationMember row for that
    organisation is active. Deactivating it must withdraw exactly this
    answer, and reactivating it must restore exactly this answer, with the
    role assignment and guardian rows never touched."""
    world = _build_world(mock_site_context)
    user = world.users[role]
    scope = world.scopes[(kind, relation)]
    member = OrganisationMember.objects.get(user=user)

    def _assignment_snapshot() -> set[tuple[int, int, int, str, str, bool]]:
        return {
            (a.user_id, a.site_id, a.content_type_id, a.object_id, a.role, a.is_active)
            for a in ObjectRoleAssignment.objects.filter(user=user)
        }

    def _guardian_snapshot() -> frozenset[str]:
        return frozenset(get_perms(user, scope))

    assert can(user, capability, scope) is True
    before_assignments = _assignment_snapshot()
    before_guardian = _guardian_snapshot()

    member.is_active = False
    member.save(update_fields=["is_active"])

    assert can(user, capability, scope) is False
    assert _assignment_snapshot() == before_assignments
    assert _guardian_snapshot() == before_guardian

    member.is_active = True
    member.save(update_fields=["is_active"])

    assert can(user, capability, scope) is True
    assert _assignment_snapshot() == before_assignments
    assert _guardian_snapshot() == before_guardian


@pytest.mark.django_db
def test_every_capability_reachable_from_the_interface_is_in_matrix(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    capabilities = {
        item.action.get_capability(item.ctx)
        for item in walk_interface(organisation)
        if isinstance(item, WalkedAction)
    }
    capabilities.discard(None)

    assert capabilities <= set(MATRIX)
