"""Management command to sync guardian permissions with role assignments."""

import djclick as click
from guardian.models import UserObjectPermission

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.types import SiteRolesConfig
from freedom_ls.role_based_permissions.utils import sync_user_object_permissions


@click.command()
@click.option("--dry-run", is_flag=True, help="Report changes without writing.")
@click.option(
    "--report-orphans",
    is_flag=True,
    help="Detect guardian perms with no matching role assignment.",
)
def command(dry_run: bool, report_orphans: bool) -> None:
    """Sync guardian permissions with role assignments and detect drift."""
    config = get_role_config()

    # Phase 1: Ensure permission objects exist
    _ensure_permissions_exist(config)

    # Phase 2: Sync ObjectRoleAssignments
    drifted = 0
    drifted += _sync_object_assignments(config, dry_run)

    # Phase 3: Sync SiteRoleAssignments
    drifted += _sync_site_assignments(config, dry_run)

    # Phase 4: Validate SystemRoleAssignments
    _validate_system_assignments(config)

    # Phase 5: Report orphans
    if report_orphans:
        orphan_count = _report_orphans(config)
        click.echo(f"Found {orphan_count} orphan permission(s).")

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}{drifted} drifted assignment(s) found.")


def _ensure_permissions_exist(config: SiteRolesConfig) -> None:
    """Ensure all permissions in config exist in auth_permission table."""
    for perm_string in config.all_permission_strings():
        app_label, codename = perm_string.split(".", 1)

        exists = Permission.objects.filter(
            content_type__app_label=app_label,
            codename=codename,
        ).exists()
        if exists:
            continue

        # Derive model name from codename (e.g. "view_cohort" -> "cohort")
        # Django's default permission codenames follow the pattern: action_modelname
        parts = codename.split("_", 1)
        model_name = parts[1] if len(parts) > 1 else None

        ct = None
        if model_name:
            ct = ContentType.objects.filter(
                app_label=app_label, model=model_name
            ).first()
        if ct is None:
            click.echo(
                f"Warning: No ContentType found for permission '{perm_string}' "
                f"(tried app_label='{app_label}', model='{model_name}'). "
                f"Skipping.",
                err=True,
            )
            continue
        Permission.objects.create(
            content_type=ct,
            codename=codename,
            name=f"Can {codename}",
        )


def _sync_object_assignments(config: SiteRolesConfig, dry_run: bool) -> int:
    """Sync guardian perms for all active ObjectRoleAssignments. Returns drift count."""
    drifted = 0
    pairs_seen: set[tuple[int, int, str]] = set()

    for assignment in (
        ObjectRoleAssignment.objects.filter(is_active=True)
        .select_related("user", "content_type")
        .iterator()
    ):
        pair_key = (
            assignment.user_id,
            assignment.content_type_id,
            assignment.object_id,
        )
        if pair_key in pairs_seen:
            continue
        pairs_seen.add(pair_key)

        model_class = assignment.content_type.model_class()
        if model_class is None:
            continue
        try:
            # Use _base_manager to avoid site-filtering from SiteAwareModel's default manager
            obj = model_class._base_manager.get(pk=assignment.object_id)
        except model_class.DoesNotExist:
            click.echo(
                f"Warning: Target object "
                f"{assignment.content_type}:{assignment.object_id} "
                f"not found, skipping.",
                err=True,
            )
            continue

        result = sync_user_object_permissions(assignment.user, obj, dry_run=dry_run)
        if result["added"] or result["removed"]:
            drifted += 1

    return drifted


def _sync_site_assignments(config: SiteRolesConfig, dry_run: bool) -> int:
    """Sync guardian perms for all active SiteRoleAssignments. Returns drift count."""
    drifted = 0
    pairs_seen: set[tuple[int, int]] = set()

    for assignment in (
        SiteRoleAssignment.objects.filter(is_active=True)
        .select_related("user", "site")
        .iterator()
    ):
        pair_key = (assignment.user_id, assignment.site_id)
        if pair_key in pairs_seen:
            continue
        pairs_seen.add(pair_key)

        result = sync_user_object_permissions(
            assignment.user, assignment.site, dry_run=dry_run
        )
        if result["added"] or result["removed"]:
            drifted += 1

    return drifted


def _validate_system_assignments(config: SiteRolesConfig) -> None:
    """Validate that all active SystemRoleAssignments have roles in config."""
    for assignment in SystemRoleAssignment.objects.filter(
        is_active=True
    ).select_related("user"):
        if assignment.role not in config:
            click.echo(
                f"Warning: SystemRoleAssignment for user {assignment.user} "
                f"has unknown role '{assignment.role}'.",
                err=True,
            )


def _report_orphans(config: SiteRolesConfig) -> int:
    """Scan UserObjectPermission for rows not traceable to any active role assignment."""
    # Prefetch all active assignments to avoid N+1 queries
    # Key: (user_id, content_type_id, object_id) -> set of role names
    object_role_lookup: dict[tuple[int, int, str], set[str]] = {}
    for assignment in ObjectRoleAssignment.objects.filter(is_active=True):
        key = (assignment.user_id, assignment.content_type_id, assignment.object_id)
        object_role_lookup.setdefault(key, set()).add(assignment.role)

    # Key: (user_id, site_id) -> set of role names
    site_role_lookup: dict[tuple[int, int], set[str]] = {}
    for assignment in SiteRoleAssignment.objects.filter(is_active=True):
        site_key = (assignment.user_id, assignment.site_id)
        site_role_lookup.setdefault(site_key, set()).add(assignment.role)

    site_ct = ContentType.objects.get_for_model(Site)

    orphan_count = 0
    for uop in UserObjectPermission.objects.select_related(
        "permission__content_type", "user"
    ).iterator():
        perm_string = (
            f"{uop.permission.content_type.app_label}.{uop.permission.codename}"
        )

        # Check object role assignments
        obj_key = (uop.user_id, uop.content_type_id, uop.object_pk)
        obj_roles = object_role_lookup.get(obj_key, set())
        if any(
            role in config and perm_string in config[role].permissions
            for role in obj_roles
        ):
            continue

        # Check site role assignments
        if uop.content_type_id == site_ct.id:
            try:
                site_id = int(uop.object_pk)
            except (ValueError, TypeError):
                pass
            else:
                site_roles = site_role_lookup.get((uop.user_id, site_id), set())
                if any(
                    role in config and perm_string in config[role].permissions
                    for role in site_roles
                ):
                    continue

        orphan_count += 1
        click.echo(
            f"  Orphan: user={uop.user}, perm={perm_string}, "
            f"object={uop.content_type}:{uop.object_pk}"
        )

    return orphan_count
