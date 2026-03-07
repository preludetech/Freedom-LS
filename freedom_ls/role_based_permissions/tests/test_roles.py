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

    def test_all_expected_roles_exist(self) -> None:
        """All 6 expected roles are defined."""
        expected = {
            "site_admin",
            "instructor",
            "ta",
            "system_admin",
            "student",
            "observer",
        }
        assert set(BASE_ROLES.keys()) == expected

    def test_site_admin_display_name(self) -> None:
        """site_admin has correct display_name."""
        assert BASE_ROLES["site_admin"].display_name == "Site Administrator"

    def test_site_admin_permissions(self) -> None:
        """site_admin has expected permission count and key permissions."""
        perms = BASE_ROLES["site_admin"].permissions
        assert len(perms) == 8
        assert "freedom_ls_student_management.view_cohort" in perms
        assert "freedom_ls_student_management.delete_cohort" in perms
        assert "freedom_ls_student_management.view_student" in perms
        assert "freedom_ls_student_management.delete_student" in perms

    def test_instructor_display_name(self) -> None:
        """instructor has correct display_name."""
        assert BASE_ROLES["instructor"].display_name == "Instructor"

    def test_instructor_permissions(self) -> None:
        """instructor has expected permission count and key permissions."""
        perms = BASE_ROLES["instructor"].permissions
        assert len(perms) == 3
        assert "freedom_ls_student_management.view_cohort" in perms
        assert "freedom_ls_student_management.view_student" in perms
        assert "freedom_ls_student_management.change_student" in perms

    def test_ta_display_name(self) -> None:
        """ta has correct display_name."""
        assert BASE_ROLES["ta"].display_name == "Teaching Assistant"

    def test_ta_permissions(self) -> None:
        """ta has expected permission count and key permissions."""
        perms = BASE_ROLES["ta"].permissions
        assert len(perms) == 2
        assert "freedom_ls_student_management.view_cohort" in perms
        assert "freedom_ls_student_management.view_student" in perms

    def test_system_admin_display_name(self) -> None:
        """system_admin has correct display_name."""
        assert BASE_ROLES["system_admin"].display_name == "System Administrator"

    def test_system_admin_permissions_empty(self) -> None:
        """system_admin has no permissions (placeholder)."""
        assert BASE_ROLES["system_admin"].permissions == frozenset()

    def test_student_display_name(self) -> None:
        """student has correct display_name."""
        assert BASE_ROLES["student"].display_name == "Student"

    def test_student_permissions_empty(self) -> None:
        """student has no permissions (placeholder)."""
        assert BASE_ROLES["student"].permissions == frozenset()

    def test_observer_display_name(self) -> None:
        """observer has correct display_name."""
        assert BASE_ROLES["observer"].display_name == "Observer"

    def test_observer_permissions_empty(self) -> None:
        """observer has no permissions (placeholder)."""
        assert BASE_ROLES["observer"].permissions == frozenset()

    def test_all_lti_roles_are_none(self) -> None:
        """All roles have lti_role=None in V1."""
        for role_name, role in BASE_ROLES.items():
            assert role.lti_role is None, f"{role_name} has non-None lti_role"
