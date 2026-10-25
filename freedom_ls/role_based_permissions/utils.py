"""Utility functions for role assignment, permission sync, and queries."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, TypedDict

from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm, remove_perm

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from freedom_ls.audit_log.writer import record_entry
from freedom_ls.organisations.utils import organisation_of
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.types import AssignmentScope
from freedom_ls.site_aware_models.models import SiteAwareModelBase, site_of

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)


def delete_role_rows_for(
    target: Site | SiteAwareModelBase,
    *,
    removed_by: User | None = None,
    reason: str = "",
) -> None:
    """Delete every object role assignment on `target`, active or not, and
    the guardian rows that go with them, recording a removal for each active
    one so the log says whose access went with the target.

    For a target that is about to be deleted: deactivating would leave
    guardian rows behind and assignments whose target resolves to None.
    _base_manager, because a delete from the admin or a management command
    may run with no request site in scope, where the site-aware manager would
    match nothing and leave the rows behind.
    """
    target_type = ContentType.objects.get_for_model(target)
    rows = ObjectRoleAssignment._base_manager.filter(
        content_type=target_type, object_id=str(target.pk)
    )
    with transaction.atomic():
        for row in rows.filter(is_active=True).select_related("user"):
            _record_role_change(
                "role.removed", removed_by, row.user, target, row.role, reason
            )
        rows.delete()
    UserObjectPermission.objects.filter(
        content_type=target_type, object_pk=str(target.pk)
    ).delete()


def clear_permission_cache() -> None:
    """Clear the permission codename cache. Intended for use in tests."""
    _get_valid_codenames_for_content_type.cache_clear()


class SyncResult(TypedDict):
    user: int
    object: str
    roles: list[str]
    added: set[str]
    removed: set[str]


def check_role_name_in_config(role_name: str, site_name: str | None = None) -> None:
    """Raise ValueError if role_name is not in the role config.

    Args:
        role_name: The role name to validate.
        site_name: Site name to load config for. If not provided, uses the current site.
    """
    config = get_role_config(site_name)
    if role_name not in config:
        raise ValueError(f"Unknown role: {role_name!r}")


def _check_assignment_scope(
    role_name: str, expected_scope: AssignmentScope, site_name: str | None = None
) -> None:
    """Raise ValueError if the role's assignment_scope doesn't match expected_scope."""
    config = get_role_config(site_name)
    role = config[role_name]
    if role.assignment_scope != expected_scope:
        raise ValueError(
            f"Role {role_name!r} has assignment_scope={role.assignment_scope!r}, "
            f"but {expected_scope!r} is required for this assignment type."
        )


def get_object_roles(user: User, obj: Model) -> set[str]:
    """Return set of active role names for user on the given object."""
    ct = ContentType.objects.get_for_model(obj)
    return set(
        ObjectRoleAssignment.objects.filter(
            user=user,
            content_type=ct,
            object_id=str(obj.pk),
            is_active=True,
        ).values_list("role", flat=True)
    )


def _get_active_roles_for_user_on_site(user: User, site: Site) -> set[str]:
    """Return set of active site role names for user on the given site."""
    return set(
        SiteRoleAssignment.objects.filter(
            user=user,
            site=site,
            is_active=True,
        ).values_list("role", flat=True)
    )


def _get_guardian_perms_as_full_strings(user: User, obj: Model) -> set[str]:
    """Return current guardian permissions as 'app_label.codename' strings."""
    ct = ContentType.objects.get_for_model(obj)
    tuples = (
        UserObjectPermission.objects.filter(
            user=user,
            content_type=ct,
            object_pk=str(obj.pk),
        )
        .select_related("permission__content_type")
        .values_list(
            "permission__content_type__app_label",
            "permission__codename",
        )
        .distinct()
    )
    return {f"{app_label}.{codename}" for app_label, codename in tuples}


@lru_cache(maxsize=64)
def _get_valid_codenames_for_content_type(ct_pk: int) -> frozenset[str]:
    """Return the set of valid permission codenames for a content type pk.

    Cached to avoid repeated DB queries for the same content type.
    """
    return frozenset(
        Permission.objects.filter(content_type_id=ct_pk).values_list(
            "codename", flat=True
        )
    )


def _filter_perms_for_content_type(perms: set[str], ct: ContentType) -> set[str]:
    """Filter permission strings to only those matching the given content type.

    Guardian requires that a permission's content_type matches the object's
    content_type when using assign_perm/remove_perm and when querying with
    get_perms/get_objects_for_user. This filters out permissions that belong
    to a different model's content type.
    """
    valid_codenames = _get_valid_codenames_for_content_type(ct.pk)
    result = set()
    for perm in perms:
        app_label, codename = perm.split(".", 1)
        if app_label == ct.app_label and codename in valid_codenames:
            result.add(perm)
    return result


def sync_user_object_permissions(
    user: User, obj: Model, dry_run: bool = False, site_name: str | None = None
) -> SyncResult:
    """Sync guardian object permissions to match user's active roles on obj.

    Only permissions whose content type matches the object's content type
    are synced, as guardian requires this for its permission queries to work.

    Args:
        site_name: Site name to load config for. If not provided, resolves
            from the object's site, or falls back to the current site.

    Returns a dict describing the changes made (or that would be made).
    """
    if site_name is None and isinstance(obj, Site | SiteAwareModelBase):
        site_name = site_of(obj).name
    config = get_role_config(site_name)

    if isinstance(obj, Site):
        roles = _get_active_roles_for_user_on_site(user, obj)
    else:
        roles = get_object_roles(user, obj)

    all_desired: set[str] = set()
    for role_name in roles:
        if role_name in config:
            all_desired |= config[role_name].permissions

    ct = ContentType.objects.get_for_model(obj)
    desired = _filter_perms_for_content_type(all_desired, ct)

    current = _get_guardian_perms_as_full_strings(user, obj)

    to_add = desired - current
    to_remove = current - desired

    if not dry_run:
        with transaction.atomic():
            for perm in to_add:
                assign_perm(perm, user, obj)
            for perm in to_remove:
                remove_perm(perm, user, obj)

    return {
        "user": user.pk,
        "object": repr(obj),
        "roles": list(roles),
        "added": to_add,
        "removed": to_remove,
    }


def _refresh_assignment(
    assignment: ObjectRoleAssignment | SiteRoleAssignment | SystemRoleAssignment,
    assigned_by: User | None,
    *,
    stamp: bool,
) -> list[str]:
    """Reactivate the row and record the grantor; with `stamp`, the grant
    time moves too, so "added on" is the time of the grant that set
    "added by".

    Returns the fields changed on the instance, for the caller to save. Empty
    when nothing changed.
    """
    fields_to_update: list[str] = []
    if not assignment.is_active:
        assignment.is_active = True
        fields_to_update.append("is_active")
    if assignment.assigned_by != assigned_by:
        assignment.assigned_by = assigned_by
        fields_to_update.append("assigned_by")
    if fields_to_update and stamp:
        assignment.assigned_at = timezone.now()
        fields_to_update.append("assigned_at")
    return fields_to_update


def _record_role_change(
    action: str,
    actor: User | None,
    user: User,
    target: Site | SiteAwareModelBase,
    role: str,
    reason: str = "",
) -> None:
    """One audit entry for a role granted to or removed from `user` on
    `target`. The target's own name is the scope label; every role target
    (an organisation, a cohort, a site, a course) stringifies to its name or
    title. The role's display name is stored with the entry, like the other
    labels, so it reads after the role is renamed or retired."""
    site = site_of(target)
    config = get_role_config(site.name)
    role_label = config[role].display_name if role in config else role
    record_entry(
        action=action,
        actor=actor,
        target=user,
        target_label=user.display_name,
        organisation=organisation_of(target),
        subjects=(target,),
        details={"role": role, "role_label": role_label, "scope": str(target)},
        reason=reason,
        site=site,
    )


def assign_object_role(
    user: User,
    target: SiteAwareModelBase,
    role: str,
    assigned_by: User | None = None,
) -> ObjectRoleAssignment:
    """Assign an object-level role to a user on a target object.

    Creates or reactivates an ObjectRoleAssignment, then syncs guardian
    permissions. Records a grant whenever the row changed, so a re-grant
    that moved "added by" to another grantor is in the log too.
    """
    site_name = site_of(target).name
    check_role_name_in_config(role, site_name=site_name)
    _check_assignment_scope(role, "object", site_name=site_name)
    ct = ContentType.objects.get_for_model(target)
    assignment: ObjectRoleAssignment
    with transaction.atomic():
        assignment, created = ObjectRoleAssignment.objects.get_or_create(
            user=user,
            content_type=ct,
            object_id=str(target.pk),
            role=role,
            defaults={"assigned_by": assigned_by, "is_active": True},
        )
        fields_to_update: list[str] = []
        if not created:
            fields_to_update = _refresh_assignment(assignment, assigned_by, stamp=True)
            if fields_to_update:
                assignment.save(update_fields=fields_to_update)

        sync_user_object_permissions(user, target)
        if created or fields_to_update:
            _record_role_change("role.granted", assigned_by, user, target, role)
    return assignment


def remove_object_role(
    user: User,
    target: SiteAwareModelBase,
    role: str,
    removed_by: User | None = None,
    *,
    reason: str = "",
) -> None:
    """Remove an object-level role from a user on a target object.

    Deactivates the ObjectRoleAssignment, resyncs guardian permissions and
    records the removal when an active assignment was deactivated.
    """
    check_role_name_in_config(role, site_name=site_of(target).name)
    ct = ContentType.objects.get_for_model(target)
    with transaction.atomic():
        removed = ObjectRoleAssignment.objects.filter(
            user=user,
            content_type=ct,
            object_id=str(target.pk),
            role=role,
            is_active=True,
        ).update(is_active=False, updated_at=timezone.now())
        sync_user_object_permissions(user, target)
        if removed:
            _record_role_change("role.removed", removed_by, user, target, role, reason)


def assign_site_role(
    user: User,
    role: str,
    assigned_by: User | None = None,
    site: Site | None = None,
) -> SiteRoleAssignment:
    """Assign a site-level role to a user on a site.

    Creates or reactivates a SiteRoleAssignment, then syncs guardian permissions
    on the Site object. Records a grant whenever the row changed, so a
    re-grant that moved "added by" to another grantor is in the log too.

    Args:
        site: The site to assign the role on. Defaults to the current site.
    """
    if site is None:
        site = Site.objects.get_current()
    check_role_name_in_config(role, site_name=site.name)
    _check_assignment_scope(role, "site", site_name=site.name)
    assignment: SiteRoleAssignment
    with transaction.atomic():
        assignment, created = SiteRoleAssignment.objects.get_or_create(
            user=user,
            site=site,
            role=role,
            defaults={"assigned_by": assigned_by, "is_active": True},
        )
        fields_to_update: list[str] = []
        if not created:
            fields_to_update = _refresh_assignment(assignment, assigned_by, stamp=True)
            if fields_to_update:
                assignment.save(update_fields=fields_to_update)

        sync_user_object_permissions(user, site)
        if created or fields_to_update:
            _record_role_change("role.granted", assigned_by, user, site, role)
    return assignment


def remove_site_role(
    user: User,
    role: str,
    site: Site | None = None,
    removed_by: User | None = None,
    *,
    reason: str = "",
) -> None:
    """Remove a site-level role from a user on a site.

    Deactivates the SiteRoleAssignment, then resyncs guardian permissions
    on the Site object. Refuses to remove a user's last active site_admin
    assignment on a site, so a site is never left without one.

    Args:
        site: The site to remove the role from. Defaults to the current site.
        removed_by: The user performing the removal, recorded as the actor of
            the audit entry; none logs as the system.
        reason: Free text stored on the audit entry.
    """
    if site is None:
        site = Site.objects.get_current()
    check_role_name_in_config(role, site_name=site.name)
    with transaction.atomic():
        if (
            role == "site_admin"
            and SiteRoleAssignment.objects.filter(
                user=user, site=site, role="site_admin", is_active=True
            ).exists()
        ):
            site = Site.objects.select_for_update().get(pk=site.pk)
            other_active_admins = SiteRoleAssignment.objects.filter(
                site=site,
                role="site_admin",
                is_active=True,
                user__is_active=True,
            ).exclude(user=user)
            if not other_active_admins.exists():
                raise RoleChangeRefused(RefusalReason.LAST_SITE_ADMIN)
        removed = SiteRoleAssignment.objects.filter(
            user=user,
            site=site,
            role=role,
            is_active=True,
        ).update(is_active=False, updated_at=timezone.now())
        if removed:
            _record_role_change("role.removed", removed_by, user, site, role, reason)
    sync_user_object_permissions(user, site)


def assign_system_role(
    user: User,
    role: str,
    assigned_by: User | None = None,
) -> SystemRoleAssignment:
    """Assign a system-level role to a user.

    Creates or reactivates a SystemRoleAssignment. No guardian sync
    (system roles have no object to scope to).
    """
    check_role_name_in_config(role)
    _check_assignment_scope(role, "system")
    assignment: SystemRoleAssignment
    assignment, created = SystemRoleAssignment.objects.get_or_create(
        user=user,
        role=role,
        defaults={"assigned_by": assigned_by, "is_active": True},
    )
    if not created:
        fields_to_update = _refresh_assignment(assignment, assigned_by, stamp=False)
        if fields_to_update:
            assignment.save(update_fields=fields_to_update)

    # TODO: AuditLog entry for system role assignment
    return assignment


def remove_system_role(
    user: User,
    role: str,
    removed_by: User | None = None,
) -> None:
    """Remove a system-level role from a user.

    Deactivates the SystemRoleAssignment. No guardian sync.
    """
    check_role_name_in_config(role)
    SystemRoleAssignment.objects.filter(
        user=user,
        role=role,
    ).update(is_active=False, updated_at=timezone.now())
    # TODO: AuditLog entry for system role removal (use removed_by)


def get_course_roles(user: User, course: Model) -> set[str]:
    """Return set of active role names for user on the given course."""
    return get_object_roles(user, course)


def get_cohort_roles(user: User, cohort: Model) -> set[str]:
    """Return set of active role names for user on the given cohort."""
    return get_object_roles(user, cohort)
