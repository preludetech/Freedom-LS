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

    def test_site_admin_permissions_count(self) -> None:
        """site_admin has 8 permissions."""
        assert len(BASE_ROLES["site_admin"].permissions) == 8

    def test_instructor_display_name(self) -> None:
        """instructor has correct display_name."""
        assert BASE_ROLES["instructor"].display_name == "Instructor"

    def test_instructor_permissions_count(self) -> None:
        """instructor has 3 permissions."""
        assert len(BASE_ROLES["instructor"].permissions) == 3

    def test_ta_display_name(self) -> None:
        """ta has correct display_name."""
        assert BASE_ROLES["ta"].display_name == "Teaching Assistant"

    def test_ta_permissions_count(self) -> None:
        """ta has 2 permissions."""
        assert len(BASE_ROLES["ta"].permissions) == 2

    def test_system_admin_display_name(self) -> None:
        """system_admin has correct display_name."""
        assert BASE_ROLES["system_admin"].display_name == "System Administrator"

    def test_system_admin_has_no_permissions_yet(self) -> None:
        """system_admin has no permissions (placeholder)."""
        assert len(BASE_ROLES["system_admin"].permissions) == 0

    def test_student_display_name(self) -> None:
        """student has correct display_name."""
        assert BASE_ROLES["student"].display_name == "Student"

    def test_student_has_no_permissions_yet(self) -> None:
        """student has no permissions (placeholder)."""
        assert len(BASE_ROLES["student"].permissions) == 0

    def test_observer_display_name(self) -> None:
        """observer has correct display_name."""
        assert BASE_ROLES["observer"].display_name == "Observer"

    def test_observer_has_no_permissions_yet(self) -> None:
        """observer has no permissions (placeholder)."""
        assert len(BASE_ROLES["observer"].permissions) == 0

    def test_all_lti_roles_are_none(self) -> None:
        """All roles have lti_role=None (placeholder for future LTI implementation)."""
        for name, role in BASE_ROLES.items():
            assert role.lti_role is None, f"Role '{name}' has unexpected lti_role"

    def test_instructor_has_view_cohort(self) -> None:
        """instructor includes view_cohort permission."""
        assert (
            "freedom_ls_student_management.view_cohort"
            in BASE_ROLES["instructor"].permissions
        )

    def test_ta_has_view_cohort_and_view_student(self) -> None:
        """ta includes both view_cohort and view_student."""
        ta_perms = BASE_ROLES["ta"].permissions
        assert "freedom_ls_student_management.view_cohort" in ta_perms
        assert "freedom_ls_student_management.view_student" in ta_perms

    def test_site_admin_is_superset_of_instructor(self) -> None:
        """site_admin permissions are a superset of instructor permissions."""
        assert BASE_ROLES["instructor"].permissions.issubset(
            BASE_ROLES["site_admin"].permissions
        )
