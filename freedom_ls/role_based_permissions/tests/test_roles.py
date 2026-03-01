"""Tests for base role configuration."""

import pytest

from freedom_ls.role_based_permissions.registry import PERMISSIONS
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SiteRolesConfig

EXPECTED_ROLES = {
    "site_admin": {
        "display_name": "Site Administrator",
        "permission_count": 8,
    },
    "instructor": {
        "display_name": "Instructor",
        "permission_count": 3,
    },
    "ta": {
        "display_name": "Teaching Assistant",
        "permission_count": 2,
    },
    "system_admin": {
        "display_name": "System Administrator",
        "permission_count": 0,
    },
    "student": {
        "display_name": "Student",
        "permission_count": 0,
    },
    "observer": {
        "display_name": "Observer",
        "permission_count": 0,
    },
}


class TestBaseRoles:
    """Tests for the BASE_ROLES configuration."""

    def test_base_roles_is_site_roles_config(self) -> None:
        """BASE_ROLES is an instance of SiteRolesConfig."""
        assert isinstance(BASE_ROLES, SiteRolesConfig)

    @pytest.mark.parametrize("role_name", EXPECTED_ROLES.keys())
    def test_role_exists(self, role_name: str) -> None:
        """All six expected roles exist in BASE_ROLES."""
        assert role_name in BASE_ROLES

    @pytest.mark.parametrize(
        ("role_name", "expected"),
        [(name, info["display_name"]) for name, info in EXPECTED_ROLES.items()],
    )
    def test_role_display_name(self, role_name: str, expected: str) -> None:
        """Each role has the correct display_name."""
        assert BASE_ROLES[role_name].display_name == expected

    @pytest.mark.parametrize(
        ("role_name", "expected_count"),
        [(name, info["permission_count"]) for name, info in EXPECTED_ROLES.items()],
    )
    def test_role_permission_count(self, role_name: str, expected_count: int) -> None:
        """Each role has the expected number of permissions."""
        assert len(BASE_ROLES[role_name].permissions) == expected_count

    def test_all_role_permissions_exist_in_registry(self) -> None:
        """Every permission used in any role exists in the PERMISSIONS registry."""
        all_perms = BASE_ROLES.all_permission_strings()
        missing = all_perms - set(PERMISSIONS.keys())
        assert missing == set(), f"Permissions not in registry: {missing}"

    @pytest.mark.parametrize("role_name", EXPECTED_ROLES.keys())
    def test_all_lti_roles_are_none(self, role_name: str) -> None:
        """All lti_role values are None (LTI not yet implemented)."""
        assert BASE_ROLES[role_name].lti_role is None

    def test_site_admin_permissions(self) -> None:
        """site_admin has the full student_management CRUD permission set."""
        expected = frozenset(
            {
                "freedom_ls_student_management.view_cohort",
                "freedom_ls_student_management.add_cohort",
                "freedom_ls_student_management.change_cohort",
                "freedom_ls_student_management.delete_cohort",
                "freedom_ls_student_management.view_student",
                "freedom_ls_student_management.add_student",
                "freedom_ls_student_management.change_student",
                "freedom_ls_student_management.delete_student",
            }
        )
        assert BASE_ROLES["site_admin"].permissions == expected

    def test_instructor_permissions(self) -> None:
        """instructor has view_cohort, view_student, change_student."""
        expected = frozenset(
            {
                "freedom_ls_student_management.view_cohort",
                "freedom_ls_student_management.view_student",
                "freedom_ls_student_management.change_student",
            }
        )
        assert BASE_ROLES["instructor"].permissions == expected

    def test_ta_permissions(self) -> None:
        """ta has view_cohort and view_student."""
        expected = frozenset(
            {
                "freedom_ls_student_management.view_cohort",
                "freedom_ls_student_management.view_student",
            }
        )
        assert BASE_ROLES["ta"].permissions == expected
