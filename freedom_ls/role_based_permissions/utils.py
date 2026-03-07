"""Utility functions for role assignment, permission sync, and queries."""

from functools import lru_cache
from typing import TypedDict

from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm, remove_perm

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Model

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.student_management.models import Cohort


class SyncResult(TypedDict):
    user: int
    object: str
    roles: list[str]
    added: set[str]
    removed: set[str]


def check_role_name_in_config(role_name: str) -> None:
    """Raise ValueError if role_name is not in the current site's role config."""
    config = get_role_config()
    if role_name not in config:
        raise ValueError(f"Unknown role: {role_name!r}")


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
    return {perm for perm in perms if perm.split(".", 1)[1] in valid_codenames}


def sync_user_object_permissions(
    user: User, obj: Model, dry_run: bool = False
) -> SyncResult:
    """Sync guardian object permissions to match user's active roles on obj.

    Only permissions whose content type matches the object's content type
    are synced, as guardian requires this for its permission queries to work.

    Returns a dict describing the changes made (or that would be made).
    """
    config = get_role_config()

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


def assign_object_role(
    user: User,
    target: Model,
    role: str,
    assigned_by: User | None = None,
) -> ObjectRoleAssignment:
    """Assign an object-level role to a user on a target object.

    Creates or reactivates an ObjectRoleAssignment, then syncs guardian permissions.
    """
    check_role_name_in_config(role)
    ct = ContentType.objects.get_for_model(target)
    assignment: ObjectRoleAssignment
    assignment, created = ObjectRoleAssignment.objects.get_or_create(
        user=user,
        content_type=ct,
        object_id=str(target.pk),
        role=role,
        defaults={"assigned_by": assigned_by, "is_active": True},
    )
    if not created and not assignment.is_active:
        assignment.is_active = True
        assignment.assigned_by = assigned_by
        assignment.save(update_fields=["is_active", "assigned_by"])

    sync_user_object_permissions(user, target)
    # TODO: AuditLog entry for role assignment
    return assignment


def remove_object_role(
    user: User,
    target: Model,
    role: str,
) -> None:
    """Remove an object-level role from a user on a target object.

    Deactivates the ObjectRoleAssignment, then resyncs guardian permissions.
    """
    ct = ContentType.objects.get_for_model(target)
    ObjectRoleAssignment.objects.filter(
        user=user,
        content_type=ct,
        object_id=str(target.pk),
        role=role,
    ).update(is_active=False)
    sync_user_object_permissions(user, target)
    # TODO: AuditLog entry for role removal


def assign_site_role(
    user: User,
    role: str,
    assigned_by: User | None = None,
) -> SiteRoleAssignment:
    """Assign a site-level role to a user on the current site.

    Creates or reactivates a SiteRoleAssignment, then syncs guardian permissions
    on the Site object.
    """
    check_role_name_in_config(role)
    site = Site.objects.get_current()
    assignment: SiteRoleAssignment
    assignment, created = SiteRoleAssignment.objects.get_or_create(
        user=user,
        site=site,
        role=role,
        defaults={"assigned_by": assigned_by, "is_active": True},
    )
    if not created and not assignment.is_active:
        assignment.is_active = True
        assignment.assigned_by = assigned_by
        assignment.save(update_fields=["is_active", "assigned_by"])

    sync_user_object_permissions(user, site)
    # TODO: AuditLog entry for site role assignment
    return assignment


def remove_site_role(
    user: User,
    role: str,
) -> None:
    """Remove a site-level role from a user on the current site.

    Deactivates the SiteRoleAssignment, then resyncs guardian permissions
    on the Site object.
    """
    site = Site.objects.get_current()
    SiteRoleAssignment.objects.filter(
        user=user,
        site=site,
        role=role,
    ).update(is_active=False)
    sync_user_object_permissions(user, site)
    # TODO: AuditLog entry for site role removal


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
    assignment: SystemRoleAssignment
    assignment, created = SystemRoleAssignment.objects.get_or_create(
        user=user,
        role=role,
        defaults={"assigned_by": assigned_by, "is_active": True},
    )
    if not created and not assignment.is_active:
        assignment.is_active = True
        assignment.assigned_by = assigned_by
        assignment.save(update_fields=["is_active", "assigned_by"])

    # TODO: AuditLog entry for system role assignment
    return assignment


def remove_system_role(
    user: User,
    role: str,
) -> None:
    """Remove a system-level role from a user.

    Deactivates the SystemRoleAssignment. No guardian sync.
    """
    SystemRoleAssignment.objects.filter(
        user=user,
        role=role,
    ).update(is_active=False)
    # TODO: AuditLog entry for system role removal


def get_course_roles(user: User, course: Course) -> set[str]:
    """Convenience wrapper: return active roles for user on a Course."""
    return get_object_roles(user, course)


def get_cohort_roles(user: User, cohort: Cohort) -> set[str]:
    """Convenience wrapper: return active roles for user on a Cohort."""
    return get_object_roles(user, cohort)
