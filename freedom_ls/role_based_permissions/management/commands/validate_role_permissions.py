"""Management command to validate role permission configuration."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.registry import PERMISSIONS
from freedom_ls.role_based_permissions.types import SiteRolesConfig


def _get_permissions_modules() -> dict[str, str]:
    """Return the FREEDOMLS_PERMISSIONS_MODULES setting."""
    return getattr(settings, "FREEDOMLS_PERMISSIONS_MODULES", {})


class Command(BaseCommand):
    help = "Validate role permission configuration for CI."

    def handle(self, *args: object, **options: object) -> None:
        errors: list[str] = []

        # Validate base config
        base_config = get_role_config()
        errors.extend(self._validate_config(base_config, "base"))

        # Validate site-specific configs
        modules = _get_permissions_modules()
        for site_name in modules:
            site_config = get_role_config(site_name)
            errors.extend(self._validate_config(site_config, f"site:{site_name}"))

        # Check for orphaned DB assignments
        errors.extend(self._check_orphaned_assignments(base_config, modules))

        if errors:
            error_msg = "Validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise CommandError(error_msg)

        self.stdout.write("All role configurations are valid.")

    def _validate_config(self, config: SiteRolesConfig, label: str) -> list[str]:
        """Validate a single SiteRolesConfig. Returns list of error messages."""
        errors: list[str] = []

        for role_name, role in config.items():
            # Check: role name is valid Python identifier
            if not role_name.isidentifier():
                errors.append(
                    f"[{label}] Role name '{role_name}' "
                    f"is not a valid Python identifier."
                )

            # Check: all permissions exist in registry
            for perm in role.permissions:
                if perm not in PERMISSIONS:
                    errors.append(
                        f"[{label}] Role '{role_name}' references "
                        f"unknown permission '{perm}' (not in registry)."
                    )

            # Check: ui_hint is valid
            if role.ui_hint not in ("standalone", "composable"):
                errors.append(
                    f"[{label}] Role '{role_name}' has invalid ui_hint "
                    f"'{role.ui_hint}' (must be 'standalone' or 'composable')."
                )

        return errors

    def _check_orphaned_assignments(
        self, base_config: SiteRolesConfig, modules: dict[str, str]
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
