"""Tests for the permission registry."""

import re

from freedom_ls.role_based_permissions.registry import PERMISSIONS

PERMISSION_FORMAT = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class TestPermissionsRegistry:
    """Tests for the PERMISSIONS dict."""

    def test_permissions_is_a_dict(self) -> None:
        """PERMISSIONS is a dict."""
        assert isinstance(PERMISSIONS, dict)

    def test_active_permissions_present(self) -> None:
        """The two active permissions are present with correct descriptions."""
        assert (
            PERMISSIONS["freedom_ls_student_management.view_cohort"]
            == "Can view cohort"
        )
        assert (
            PERMISSIONS["freedom_ls_student_management.view_student"]
            == "Can view student"
        )

    def test_all_permission_strings_follow_format(self) -> None:
        """All permission keys follow 'app_label.codename' format."""
        for perm_string in PERMISSIONS:
            assert PERMISSION_FORMAT.match(perm_string), (
                f"Permission '{perm_string}' does not match 'app_label.codename' format"
            )

    def test_all_descriptions_are_nonempty_strings(self) -> None:
        """All permission descriptions are non-empty strings."""
        for perm_string, description in PERMISSIONS.items():
            assert isinstance(description, str), (
                f"Description for '{perm_string}' is not a string"
            )
            assert description, f"Description for '{perm_string}' is empty"

    def test_has_at_least_two_permissions(self) -> None:
        """Registry has at least the two active permissions."""
        assert len(PERMISSIONS) >= 2
