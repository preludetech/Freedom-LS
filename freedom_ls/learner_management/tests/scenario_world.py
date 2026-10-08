"""A scenario world for tests that compare the two directions of a relationship.

One site, two organisations and a user for every kind of learner row and role
holder, so a test can compare sets of (role holder, learner) pairs instead of
looping.

Roles are assigned through assign_object_role / assign_site_role rather than
guardian's assign_perm: the code under test reads role assignment rows, and a
guardian row would leave it nothing to read.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import NamedTuple, cast
from unittest.mock import patch

from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner, OrganisationMember
from freedom_ls.learner_management.queries import (
    VIEW_LEARNER,
    educators_of,
    learners_visible_to,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig

# Role assignment rows, not guardian's assign_perm: the code under test reads these rows.
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    remove_object_role,
)

CUSTOM_ROLES_MODULE = "fake_permissions_module_for_scenario_world"


class World(NamedTuple):
    site: Site
    organisations: dict[str, Organisation]
    cohorts: dict[str, Cohort]
    learners: dict[str, Learner]
    role_holders: dict[str, User]


@contextmanager
def custom_role_config(
    site: Site, settings: SettingsWrapper, *, without: frozenset[str] = frozenset()
) -> Iterator[SiteRolesConfig]:
    """Install a role config for `site` for the duration of the block: BASE_ROLES
    minus `without`, plus "custom_educator" (grants VIEW_LEARNER) and
    "custom_bystander" (grants nothing). Caches are cleared on entry and exit so
    the previous config cannot leak into the next test."""
    roles = {key: role for key, role in BASE_ROLES.items() if key not in without}
    roles["custom_educator"] = Role(
        display_name="Custom educator",
        permissions=frozenset({VIEW_LEARNER}),
        assignment_scope=SCOPE_OBJECT,
    )
    roles["custom_bystander"] = Role(
        display_name="Custom bystander",
        permissions=frozenset(),
        assignment_scope=SCOPE_OBJECT,
    )
    role_config = SiteRolesConfig(roles)
    fake_module = ModuleType(CUSTOM_ROLES_MODULE)
    fake_module.ROLES = role_config
    settings.FREEDOMLS_PERMISSIONS_MODULES = {site.name: CUSTOM_ROLES_MODULE}
    with patch(
        "freedom_ls.role_based_permissions.loader.import_module",
        return_value=fake_module,
    ):
        clear_caches()
        try:
            yield role_config
        finally:
            clear_caches()


def build_world(site: Site, *, scale: int = 1) -> World:
    """One site, two organisations, learners and role holders covering every row
    kind and gate state.

    Organisation "o1" holds cohorts "c1" and "c2"; "o2" holds cohort "c3".

    Learners: "no_cohort", "in_c1", "in_c1_and_c2", "inactive_in_c1",
    "in_o1_and_o2" (one user, two rows; this is the o1 row, in no cohort),
    "in_o1_and_o2_via_c3" (the same user's o2 row, in c3), "also_o1_admin"
    (its user is o1's organisation_admin).
    Role holders: "site_admin"; "o1_admin"; "o2_admin_deactivated_member";
    "c1_admin"; "c1_viewer"; "c1_c2_admin"; "c1_c2_viewer";
    "c1_admin_inactive_assignment"; "c1_admin_inactive_user"; "no_role";
    "custom_educator_c2" (a custom role granting VIEW_LEARNER);
    "custom_bystander_o1" (a custom role granting nothing).

    `scale` adds that many extra cohorts, learners and registrations per
    organisation so query-count tests can grow the world without changing its shape.
    The extras are not named in the returned mappings.
    """
    o1 = cast(Organisation, OrganisationFactory())
    o2 = cast(Organisation, OrganisationFactory())
    c1 = cast(Cohort, CohortFactory(organisation=o1))
    c2 = cast(Cohort, CohortFactory(organisation=o1))
    c3 = cast(Cohort, CohortFactory(organisation=o2))

    for organisation in (o1, o2):
        for _ in range(scale):
            extra_cohort = CohortFactory(organisation=organisation)
            CohortMembershipFactory(
                cohort=extra_cohort, learner=LearnerFactory(organisation=organisation)
            )

    no_cohort = cast(Learner, LearnerFactory(organisation=o1))
    in_c1 = cast(Learner, LearnerFactory(organisation=o1))
    CohortMembershipFactory(cohort=c1, learner=in_c1)
    in_c1_and_c2 = cast(Learner, LearnerFactory(organisation=o1))
    CohortMembershipFactory(cohort=c1, learner=in_c1_and_c2)
    CohortMembershipFactory(cohort=c2, learner=in_c1_and_c2)
    inactive_in_c1 = cast(Learner, LearnerFactory(organisation=o1, is_active=False))
    CohortMembershipFactory(cohort=c1, learner=inactive_in_c1)
    shared_user = UserFactory()
    in_o1_and_o2 = cast(Learner, LearnerFactory(user=shared_user, organisation=o1))
    in_o1_and_o2_via_c3 = cast(
        Learner, LearnerFactory(user=shared_user, organisation=o2)
    )
    CohortMembershipFactory(cohort=c3, learner=in_o1_and_o2_via_c3)
    also_o1_admin = cast(Learner, LearnerFactory(organisation=o1))
    assign_object_role(also_o1_admin.user, o1, "organisation_admin")

    individual_course = LearnerCourseRegistrationFactory(learner=in_c1).course
    LearnerCourseRegistrationFactory(learner=no_cohort, course=individual_course)
    LearnerCourseRegistrationFactory(
        learner=inactive_in_c1, course=individual_course, is_active=False
    )
    cohort_course = CohortCourseRegistrationFactory(cohort=c1).course
    LearnerCourseRegistrationFactory(learner=in_c1_and_c2, course=cohort_course)
    cross_organisation_course = LearnerCourseRegistrationFactory(
        learner=in_o1_and_o2
    ).course
    LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=o2), course=cross_organisation_course
    )

    role_holders = {
        "site_admin": cast(User, UserFactory()),
        "o1_admin": cast(User, UserFactory()),
        "o2_admin_deactivated_member": cast(User, UserFactory()),
        "c1_admin": cast(User, UserFactory()),
        "c1_viewer": cast(User, UserFactory()),
        "c1_c2_admin": cast(User, UserFactory()),
        "c1_c2_viewer": cast(User, UserFactory()),
        "c1_admin_inactive_assignment": cast(User, UserFactory()),
        "c1_admin_inactive_user": cast(User, UserFactory(is_active=False)),
        "no_role": cast(User, UserFactory()),
        "custom_educator_c2": cast(User, UserFactory()),
        "custom_bystander_o1": cast(User, UserFactory()),
    }
    assign_site_role(role_holders["site_admin"], "site_admin", site=site)
    assign_object_role(role_holders["o1_admin"], o1, "organisation_admin")
    assign_object_role(
        role_holders["o2_admin_deactivated_member"], o2, "organisation_admin"
    )
    OrganisationMember.objects.filter(
        user=role_holders["o2_admin_deactivated_member"], organisation=o2
    ).update(is_active=False)
    assign_object_role(role_holders["c1_admin"], c1, "cohort_admin")
    assign_object_role(role_holders["c1_viewer"], c1, "cohort_viewer")
    for cohort in (c1, c2):
        assign_object_role(role_holders["c1_c2_admin"], cohort, "cohort_admin")
        assign_object_role(role_holders["c1_c2_viewer"], cohort, "cohort_viewer")
    assign_object_role(role_holders["c1_admin_inactive_assignment"], c1, "cohort_admin")
    remove_object_role(role_holders["c1_admin_inactive_assignment"], c1, "cohort_admin")
    assign_object_role(role_holders["c1_admin_inactive_user"], c1, "cohort_admin")
    assign_object_role(role_holders["custom_educator_c2"], c2, "custom_educator")
    assign_object_role(role_holders["custom_bystander_o1"], o1, "custom_bystander")

    return World(
        site=site,
        organisations={"o1": o1, "o2": o2},
        cohorts={"c1": c1, "c2": c2, "c3": c3},
        learners={
            "no_cohort": no_cohort,
            "in_c1": in_c1,
            "in_c1_and_c2": in_c1_and_c2,
            "inactive_in_c1": inactive_in_c1,
            "in_o1_and_o2": in_o1_and_o2,
            "in_o1_and_o2_via_c3": in_o1_and_o2_via_c3,
            "also_o1_admin": also_o1_admin,
        },
        role_holders=role_holders,
    )


def visible_pairs(world: World) -> set[tuple[str, str]]:
    """(role holder, learner) for every learner in learners_visible_to(holder, learner.organisation)."""
    return {
        (holder_name, learner_name)
        for holder_name, holder in world.role_holders.items()
        for learner_name, learner in world.learners.items()
        if learners_visible_to(holder, learner.organisation)
        .filter(pk=learner.pk)
        .exists()
    }


def educator_pairs(world: World) -> set[tuple[str, str]]:
    """(role holder, learner) for every holder in educators_of(learner)."""
    holder_names = {user.pk: name for name, user in world.role_holders.items()}
    return {
        (holder_names[user_pk], learner_name)
        for learner_name, learner in world.learners.items()
        for user_pk in educators_of(learner).values_list("pk", flat=True)
        if user_pk in holder_names
    }


def educator_names(
    world: World, learner_name: str, *, roles: frozenset[str] | None = None, **narrowing
) -> set[str]:
    """Names of the role holders in educators_of(that learner), passing `roles`
    and any narrowing keywords through."""
    holder_names = {user.pk: name for name, user in world.role_holders.items()}
    user_pks = educators_of(
        world.learners[learner_name], roles=roles, **narrowing
    ).values_list("pk", flat=True)
    return {holder_names[pk] for pk in user_pks if pk in holder_names}
