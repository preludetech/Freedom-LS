"""Checked entry points for granting, removing and suspending role access.

The raw utilities in `role_based_permissions/utils.py` stay available for QA
commands, fixtures and the Django admin, which have their own reasons to
bypass these checks. Anything reached by a person -- an educator or admin
acting on another user's access -- goes through here instead, so a grantor
can never remove their own access, hand out a role they don't hold, or leave
an organisation without anyone able to administer it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.learner_management.capabilities import _active_role_assignments, can
from freedom_ls.learner_management.models import Cohort, OrganisationMember
from freedom_ls.learner_management.queries import (
    MEMBER_ROLES,
    active_organisation_admins,
    cohorts_visible_to,
    site_level_admins,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.types import Role
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    remove_object_role,
    remove_site_role,
)

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User

ASSIGN = "freedom_ls_role_based_permissions.assign_{role}"
CHANGE_MEMBER = "freedom_ls_learner_management.change_organisationmember"


def _refuse_unless(
    grantor: User,
    user: User,
    capability: str,
    target: Site | Organisation | Cohort,
    *,
    assigning: bool,
) -> None:
    """The checks every entry point below runs, in this order:
    a grantor can't act on themselves, can't hand out access to an inactive
    account, and needs the capability itself. Removal skips the
    inactive-account check, since taking access away from a deactivated
    account is still allowed.
    """
    if grantor == user:
        raise RoleChangeRefused(RefusalReason.SELF)
    if assigning and not user.is_active:
        raise RoleChangeRefused(RefusalReason.INACTIVE_USER)
    if not can(grantor, capability, target):
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)


def is_site_level_admin(user: User, site: Site) -> bool:
    """Whether `user` may bypass the last-organisation-admin lock: a
    superuser, or an active site_admin on `site`, always has another way to
    reach the organisation, so the lock only protects organisation admins
    from locking each other out.
    """
    return site_level_admins(site).filter(pk=user.pk).exists()


def _holds_organisation_admin(user: User, organisation: Organisation) -> bool:
    """Whether `user` holds an active organisation_admin assignment on
    `organisation`, regardless of their OrganisationMember state."""
    return (
        _active_role_assignments(Organisation, frozenset({"organisation_admin"}))
        .filter(user=user, object_id=str(organisation.pk))
        .exists()
    )


def is_last_organisation_admin(organisation: Organisation, user: User) -> bool:
    """Whether removing or suspending `user` would leave the organisation
    with no active organisation admin. The dialogs preview this and the
    lock enforces it, from the one expression."""
    return _holds_organisation_admin(user, organisation) and not (
        active_organisation_admins(organisation).exclude(pk=user.pk).exists()
    )


def _lock_and_refuse_last_organisation_admin(
    organisation: Organisation, user: User
) -> None:
    """Refuse when `user` is the only organisation_admin left standing.

    Someone who holds no organisation_admin here cannot be the last one, so
    the lock is skipped for them. Otherwise it locks the organisation row
    rather than the assignment rows: an empty set of rows locks nothing, and
    locking the assignment being removed still leaves a race against a
    concurrent deactivation of someone else's OrganisationMember. The caller
    must already be inside transaction.atomic().
    """
    if not _holds_organisation_admin(user, organisation):
        return
    Organisation.objects.select_for_update().get(pk=organisation.pk)
    if is_last_organisation_admin(organisation, user):
        raise RoleChangeRefused(RefusalReason.LAST_ORGANISATION_ADMIN)


def assign_role(
    grantor: User, user: User, role: str, target: Site | Organisation | Cohort
) -> None:
    """Grant `role` to `user` on `target`, on the grantor's behalf."""
    _refuse_unless(grantor, user, ASSIGN.format(role=role), target, assigning=True)
    if isinstance(target, Site):
        assign_site_role(user, role, site=target, assigned_by=grantor)
    else:
        assign_object_role(user, target, role, assigned_by=grantor)


def remove_role(
    grantor: User, user: User, role: str, target: Site | Organisation | Cohort
) -> None:
    """Remove `role` from `user` on `target`, on the grantor's behalf.

    Removing site_admin defers its last-admin lock to remove_site_role,
    which every caller of the raw utility also gets. Removing the
    organisation_admin an organisation depends on runs its own lock here,
    since that check has nowhere else to live.
    """
    _refuse_unless(grantor, user, ASSIGN.format(role=role), target, assigning=False)
    if isinstance(target, Site):
        remove_site_role(user, role, site=target, removed_by=grantor)
        return
    with transaction.atomic():
        if (
            role == "organisation_admin"
            and isinstance(target, Organisation)
            and not is_site_level_admin(grantor, target.site)
        ):
            _lock_and_refuse_last_organisation_admin(target, user)
        remove_object_role(user, target, role, removed_by=grantor)


def set_organisation_member_active(
    actor: User, member: OrganisationMember, is_active: bool
) -> None:
    """Activate or suspend `member`'s OrganisationMember row, on the actor's
    behalf. Suspending one who is the organisation's last organisation_admin
    runs the same lock as removing that role outright, since it has the same
    effect: nobody left to administer the organisation.
    """
    _refuse_unless(
        actor, member.user, CHANGE_MEMBER, member.organisation, assigning=is_active
    )
    with transaction.atomic():
        if not is_active and not is_site_level_admin(actor, member.site):
            _lock_and_refuse_last_organisation_admin(member.organisation, member.user)
        member.is_active = is_active
        member.save(update_fields=["is_active"])


@dataclass(frozen=True)
class GrantableRole:
    """A role the grantor may give here. `cohorts` is None for a role on the
    whole organisation, else the active cohorts it may be given on."""

    role: str
    cohorts: tuple[Cohort, ...] | None


def grantable_roles(grantor: User, organisation: Organisation) -> list[GrantableRole]:
    """The roles and cohorts a grantor may hand out in this organisation,
    in MEMBER_ROLES order. The cohorts come from one queryset per role,
    built from the same grant builders can() reads, so the cost does not
    grow with the number of cohorts. This is the source of every choice
    offered and every submitted choice checked; assign_role and
    remove_role remain the authoritative check on each target."""
    result: list[GrantableRole] = []
    for role in MEMBER_ROLES:
        capability = ASSIGN.format(role=role)
        if role == "organisation_admin":
            if can(grantor, capability, organisation):
                result.append(GrantableRole(role, None))
            continue
        cohorts = tuple(
            cohorts_visible_to(grantor, organisation, capability=capability)
            .filter(is_active=True)
            .order_by("name")
        )
        if cohorts:
            result.append(GrantableRole(role, cohorts))
    return result


def _permissions_by_target(
    pairs: set[tuple[str, str]], roles: Mapping[str, Role]
) -> dict[str, frozenset[str]]:
    """The permissions held on each target key, from its (role, key) pairs."""
    held: dict[str, frozenset[str]] = {}
    for role, key in pairs:
        held[key] = held.get(key, frozenset()) | roles[role].permissions
    return held


def is_widening(
    before: set[tuple[str, str]],
    after: set[tuple[str, str]],
    roles: Mapping[str, Role],
    organisation_key: str,
) -> bool:
    """Whether `after` lets the person do anything `before` did not. Each
    pair is a role and the key of its target (the organisation's pk or a
    cohort's pk). Roles are compared by the permissions they carry, not by
    name, so a weaker role on a cohort already held with a stronger one is
    no widening, and a role on the organisation covers every cohort in it."""
    none: frozenset[str] = frozenset()
    before_held = _permissions_by_target(before, roles)
    after_held = _permissions_by_target(after, roles)
    before_organisation = before_held.get(organisation_key, none)
    after_organisation = after_held.get(organisation_key, none)
    for key, permissions in after_held.items():
        had = before_held.get(key, none) | before_organisation
        if not (permissions | after_organisation) <= had:
            return True
    return False
