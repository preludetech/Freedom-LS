"""Tests for base role configuration."""

from freedom_ls.role_based_permissions.registry import PERMISSIONS
from freedom_ls.role_based_permissions.roles import BASE_ROLES


class TestBaseRoles:
    """Tests for the BASE_ROLES configuration."""

    def test_all_role_permissions_exist_in_registry(self) -> None:
        """Every permission used in any role exists in the PERMISSIONS registry."""
        all_perms = BASE_ROLES.all_permission_strings()
        missing = all_perms - set(PERMISSIONS.keys())
        assert missing == set(), f"Permissions not in registry: {missing}"
