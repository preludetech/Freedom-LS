"""Checked entry points for granting, removing and suspending role access.

The raw utilities in `role_based_permissions/utils.py` stay available for QA
commands, fixtures and the Django admin, which have their own reasons to
bypass these checks. Anything reached by a person -- an educator or admin
acting on another user's access -- goes through here instead, so a grantor
can never remove their own access, hand out a role they don't hold, or leave
an organisation without anyone able to administer it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.learner_management.capabilities import _active_role_assignments, can
from freedom_ls.learner_management.models import Cohort, OrganisationMember
from freedom_ls.learner_management.queries import active_organisation_admins
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.models import SiteRoleAssignment
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


def _is_site_level_admin(user: User, site: Site) -> bool:
    """Whether `user` may bypass the last-organisation-admin lock: a
    superuser, or an active site_admin on `site`, always has another way to
    reach the organisation, so the lock only protects organisation admins
    from locking each other out.
    """
    if user.is_superuser:
        return True
    return SiteRoleAssignment.objects.filter(
        user=user, site=site, role="site_admin", is_active=True
    ).exists()


def _holds_organisation_admin(user: User, organisation: Organisation) -> bool:
    """Whether `user` holds an active organisation_admin assignment on
    `organisation`, regardless of their OrganisationMember state."""
    return (
        _active_role_assignments(Organisation, frozenset({"organisation_admin"}))
        .filter(user=user, object_id=str(organisation.pk))
        .exists()
    )


def _lock_and_refuse_last_organisation_admin(
    organisation: Organisation, user: User
) -> None:
    """Refuse when `user` is the only organisation_admin left standing.

    Locks the organisation row rather than the assignment rows: an empty set
    of rows locks nothing, and locking the assignment being removed still
    leaves a race against a concurrent deactivation of someone else's
    OrganisationMember. The caller must already be inside
    transaction.atomic().
    """
    Organisation.objects.select_for_update().get(pk=organisation.pk)
    if not active_organisation_admins(organisation).exclude(pk=user.pk).exists():
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
            and _holds_organisation_admin(user, target)
            and not _is_site_level_admin(grantor, target.site)
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
        if (
            not is_active
            and _holds_organisation_admin(member.user, member.organisation)
            and not _is_site_level_admin(actor, member.site)
        ):
            _lock_and_refuse_last_organisation_admin(member.organisation, member.user)
        member.is_active = is_active
        member.save(update_fields=["is_active"])
