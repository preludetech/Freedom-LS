"""Validate role permission configuration.

Run this command in CI or before deploying to catch configuration errors early.
It checks that:

- All role names are valid Python identifiers.
- All permissions referenced by roles exist in the permission registry.
- All role_type values are either 'standalone' or 'composable'. (in VALID_ROLE_TYPES)
- All assignment_scope values are 'system', 'site', or 'object'. (in VALID_ASSIGNMENT_SCOPES)
- No active role assignments in the database reference roles that have been
  removed from the configuration (orphaned assignments).

Usage:
    manage.py validate_role_permissions
"""

import djclick as click

from django.conf import settings

from freedom_ls.role_based_permissions.loader import get_role_config, load_base_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.registry import PERMISSIONS
from freedom_ls.role_based_permissions.types import (
    VALID_ASSIGNMENT_SCOPES,
    VALID_ROLE_TYPES,
    SiteRolesConfig,
)


def _get_permissions_modules() -> dict[str, str]:
    """Return the FREEDOMLS_PERMISSIONS_MODULES setting."""
    return getattr(settings, "FREEDOMLS_PERMISSIONS_MODULES", {})


@click.command()
def command() -> None:
    """Validate role permission configuration for CI."""
    errors: list[str] = []

    # Validate base config
    base_config = load_base_config()
    errors.extend(_validate_config(base_config, "base"))

    # Validate site-specific configs
    modules = _get_permissions_modules()
    for site_name in modules:
        site_config = get_role_config(site_name)
        errors.extend(_validate_config(site_config, f"site:{site_name}"))

    # Check for orphaned DB assignments
    errors.extend(_check_orphaned_assignments(base_config, modules))

    if errors:
        error_msg = "Validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise click.ClickException(error_msg)

    click.echo("All role configurations are valid.")


def _validate_config(config: SiteRolesConfig, label: str) -> list[str]:
    """Validate a single SiteRolesConfig. Returns list of error messages."""
    errors: list[str] = []

    for role_name, role in config.items():
        # Check: role name is valid Python identifier
        if not role_name.isidentifier():
            errors.append(
                f"[{label}] Role name '{role_name}' is not a valid Python identifier."
            )

        # Check: all permissions exist in registry
        for perm in role.permissions:
            if perm not in PERMISSIONS:
                errors.append(
                    f"[{label}] Role '{role_name}' references "
                    f"unknown permission '{perm}' (not in registry)."
                )

        # Check: role_type is valid
        if role.role_type not in VALID_ROLE_TYPES:
            errors.append(
                f"[{label}] Role '{role_name}' has invalid role_type "
                f"'{role.role_type}' (must be 'standalone' or 'composable')."
            )

        # Check: assignment_scope is valid
        if role.assignment_scope not in VALID_ASSIGNMENT_SCOPES:
            errors.append(
                f"[{label}] Role '{role_name}' has invalid assignment_scope "
                f"'{role.assignment_scope}' (must be one of {sorted(VALID_ASSIGNMENT_SCOPES)})."
            )

    return errors


def _check_orphaned_assignments(
    base_config: SiteRolesConfig, modules: dict[str, str]
) -> list[str]:
    """Check for role assignments in DB that don't exist in any config."""
    errors: list[str] = []

    # Collect all known role names across all configs
    all_role_names: set[str] = set(base_config.keys())
    for site_name in modules:
        site_config = get_role_config(site_name)
        all_role_names.update(site_config.keys())

    # Check ObjectRoleAssignment
    for role in (
        ObjectRoleAssignment.objects.filter(is_active=True)
        .values_list("role", flat=True)
        .distinct()
    ):
        if role not in all_role_names:
            errors.append(
                f"Orphaned ObjectRoleAssignment: role '{role}' not in any config."
            )

    # Check SiteRoleAssignment
    for role in (
        SiteRoleAssignment.objects.filter(is_active=True)
        .values_list("role", flat=True)
        .distinct()
    ):
        if role not in all_role_names:
            errors.append(
                f"Orphaned SiteRoleAssignment: role '{role}' not in any config."
            )

    # Check SystemRoleAssignment
    for role in (
        SystemRoleAssignment.objects.filter(is_active=True)
        .values_list("role", flat=True)
        .distinct()
    ):
        if role not in all_role_names:
            errors.append(
                f"Orphaned SystemRoleAssignment: role '{role}' not in any config."
            )

    return errors
