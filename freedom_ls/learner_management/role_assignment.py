"""Checked entry points for granting, removing and suspending role access.

The raw utilities in `role_based_permissions/utils.py` stay available for QA
commands, fixtures and the Django admin, which have their own reasons to
bypass these checks. Anything reached by a person -- an educator or admin
acting on another user's access -- goes through here instead, so a grantor
can never remove their own access, hand out a role they don't hold, or leave
an organisation without anyone able to administer it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.audit_log.writer import record_entry
from freedom_ls.learner_management.capabilities import (
    _active_role_assignments,
    _organisation_of,
    can,
)
from freedom_ls.learner_management.models import Cohort, StaffMember
from freedom_ls.learner_management.queries import (
    ADD_STAFF_MEMBER,
    ORGANISATION_ROLES,
    STAFF_ROLES,
    active_organisation_admins,
    cohorts_visible_to,
    has_staff_assignments,
    site_level_admins,
)
from freedom_ls.learner_management.utils import get_or_create_staff_member
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    deactivate_object_role,
    deactivate_site_role,
)

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User

ASSIGN = "freedom_ls_role_based_permissions.assign_{role}"
CHANGE_STAFF_MEMBER = "freedom_ls_learner_management.change_staffmember"


def _refuse_unless(
    grantor: User,
    user: User,
    capability: str,
    target: Site | Organisation | Cohort,
    *,
    assigning: bool,
    may_act_on_self: bool = False,
) -> None:
    """The checks every entry point below runs, in this order:
    a grantor can't act on themselves (unless `may_act_on_self`), can't hand out access to an inactive
    account, and needs the capability itself. Removal skips the
    inactive-account check, since taking access away from a deactivated
    account is still allowed.
    """
    if grantor == user and not may_act_on_self:
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


def _may_act_on_self(target: Site | Organisation | Cohort) -> bool:
    """Whether a grantor may change their own role on `target`: on an
    organisation or a cohort in it, never on the site. The capability check
    that follows still decides, so a person changes their own role exactly
    when they may assign that role there."""
    return _organisation_of(target) is not None


def _holds_organisation_admin(user: User, organisation: Organisation) -> bool:
    """Whether `user` holds an active organisation_admin assignment on
    `organisation`, regardless of their StaffMember state."""
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
    concurrent deactivation of someone else's StaffMember. The caller
    must already be inside transaction.atomic().
    """
    if not _holds_organisation_admin(user, organisation):
        return
    Organisation.objects.select_for_update().get(pk=organisation.pk)
    if is_last_organisation_admin(organisation, user):
        raise RoleChangeRefused(RefusalReason.LAST_ORGANISATION_ADMIN)


def _target_suits_role(role: str, target: Site | Organisation | Cohort) -> bool:
    """A site role goes on a Site, an organisation role on an Organisation
    and a cohort role on a Cohort; anything else is a caller's mistake."""
    if isinstance(target, Site):
        return role not in STAFF_ROLES
    if isinstance(target, Organisation):
        return role in ORGANISATION_ROLES
    return role in STAFF_ROLES and role not in ORGANISATION_ROLES


def assign_role(
    grantor: User, user: User, role: str, target: Site | Organisation | Cohort
) -> None:
    """Grant `role` to `user` on `target`, on the grantor's behalf."""
    if not _target_suits_role(role, target):
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)
    _refuse_unless(
        grantor,
        user,
        ASSIGN.format(role=role),
        target,
        assigning=True,
        may_act_on_self=_may_act_on_self(target),
    )
    if isinstance(target, Site):
        assign_site_role(user, role, site=target, assigned_by=grantor)
    else:
        assign_object_role(user, target, role, assigned_by=grantor)


def deactivate_role(
    grantor: User,
    user: User,
    role: str,
    target: Site | Organisation | Cohort,
    *,
    reason: str = "",
) -> None:
    """Deactivate `user`'s `role` on `target`, on the grantor's behalf.

    Deactivating site_admin defers its last-admin lock to deactivate_site_role,
    which every caller of the raw utility also gets. Deactivating the
    organisation_admin an organisation depends on runs its own lock here,
    since that check has nowhere else to live.
    """
    _refuse_unless(
        grantor,
        user,
        ASSIGN.format(role=role),
        target,
        assigning=False,
        may_act_on_self=_may_act_on_self(target),
    )
    if isinstance(target, Site):
        deactivate_site_role(
            user, role, site=target, deactivated_by=grantor, reason=reason
        )
        return
    with transaction.atomic():
        if (
            role == "organisation_admin"
            and isinstance(target, Organisation)
            and not is_site_level_admin(grantor, target.site)
        ):
            _lock_and_refuse_last_organisation_admin(target, user)
        deactivate_object_role(
            user, target, role, deactivated_by=grantor, reason=reason
        )


def set_staff_member_active(
    actor: User, staff_member: StaffMember, is_active: bool, *, reason: str = ""
) -> None:
    """Reactivate or deactivate `staff_member`'s StaffMember row, on the
    actor's behalf. Deactivating one who is the organisation's last
    organisation_admin runs the same lock as deactivating that role, since it
    has the same effect: nobody left to administer the organisation.
    """
    _refuse_unless(
        actor,
        staff_member.user,
        CHANGE_STAFF_MEMBER,
        staff_member.organisation,
        assigning=is_active,
    )
    with transaction.atomic():
        if not is_active and not is_site_level_admin(actor, staff_member.site):
            _lock_and_refuse_last_organisation_admin(
                staff_member.organisation, staff_member.user
            )
        # The caller's instance may be stale: two overlapping requests would
        # each see the old state and each write an entry for the one change.
        stored = StaffMember._base_manager.select_for_update().get(pk=staff_member.pk)
        changed = stored.is_active != is_active
        staff_member.is_active = is_active
        staff_member.save(update_fields=["is_active"])
        if changed:
            record_entry(
                action="staff_member.deactivated"
                if not is_active
                else "staff_member.reactivated",
                actor=actor,
                target=staff_member,
                target_label=staff_member.user.display_name,
                organisation=staff_member.organisation,
                subjects=(staff_member.user,),
                reason=reason,
            )


@dataclass(frozen=True)
class GrantableRole:
    """A role the grantor may give here. `cohorts` is None for a role on the
    whole organisation, else the active cohorts it may be given on."""

    role: str
    cohorts: tuple[Cohort, ...] | None


def grantable_roles(grantor: User, organisation: Organisation) -> list[GrantableRole]:
    """The roles and cohorts a grantor may hand out in this organisation,
    in STAFF_ROLES order. The cohorts come from one queryset per role,
    built from the same grant builders can() reads, so the cost does not
    grow with the number of cohorts. This is the source of every choice
    offered and every submitted choice checked; assign_role and
    deactivate_role remain the authoritative check on each target."""
    result: list[GrantableRole] = []
    for role in STAFF_ROLES:
        capability = ASSIGN.format(role=role)
        if role in ORGANISATION_ROLES:
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


def add_staff_member(
    actor: User, user: User, organisation: Organisation
) -> StaffMember:
    """Put `user` on the organisation's staff with no role, on the actor's
    behalf. Only someone who may add staff here can do it; an account on
    another site never belongs here; an existing row, active or inactive,
    is refused so the caller can say which. Someone who holds roles here
    with no row is refused as inactive: those roles count for nothing until
    a row exists, and only reactivating them shows which roles come back."""
    if not can(actor, ADD_STAFF_MEMBER, organisation):
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)
    if user.site_id != organisation.site_id:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)
    if not user.is_active:
        raise RoleChangeRefused(RefusalReason.INACTIVE_USER)
    with transaction.atomic():
        staff_member, created = get_or_create_staff_member(user, organisation)
        if not created:
            raise RoleChangeRefused(
                RefusalReason.ALREADY_STAFF
                if staff_member.is_active
                else RefusalReason.INACTIVE_STAFF_MEMBER
            )
        if has_staff_assignments(user, organisation):
            # Raising here rolls the new row back.
            raise RoleChangeRefused(RefusalReason.INACTIVE_STAFF_MEMBER)
        record_entry(
            action="staff_member.added",
            actor=actor,
            target=staff_member,
            target_label=user.display_name,
            organisation=organisation,
            subjects=(user,),
        )
    return staff_member
