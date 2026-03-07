"""Tests for role_based_permissions utility functions."""

from collections.abc import Generator

import pytest
from guardian.shortcuts import get_objects_for_user, get_perms
from pytest_mock import MockerFixture

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    assign_system_role,
    check_role_name_in_config,
    get_object_roles,
    remove_object_role,
    remove_site_role,
    remove_system_role,
    sync_user_object_permissions,
)
from freedom_ls.student_management.factories import CohortFactory, StudentFactory


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    """Clear the loader and permission caches between tests."""
    clear_caches()
    yield
    clear_caches()


@pytest.fixture(autouse=True)
def _mock_get_current_site(mock_site_context: Site, mocker: MockerFixture) -> None:
    """Ensure Site.objects.get_current() returns the test site."""
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        return_value=mock_site_context,
    )


class TestCheckRoleNameInConfig:
    """Tests for check_role_name_in_config."""

    @pytest.mark.django_db
    def test_valid_role_passes(self) -> None:
        """Known role does not raise."""
        check_role_name_in_config("instructor")

    @pytest.mark.django_db
    def test_unknown_role_raises_value_error(self) -> None:
        """Unknown role raises ValueError."""
        with pytest.raises(ValueError, match="Unknown role"):
            check_role_name_in_config("nonexistent_role")


class TestAssignObjectRole:
    """Tests for assign_object_role."""

    @pytest.mark.django_db
    def test_creates_assignment_and_sets_guardian_permissions(self) -> None:
        """Assigning an object role creates the assignment and sets matching guardian perms."""
        user = UserFactory()
        cohort = CohortFactory()
        assignment = assign_object_role(user, cohort, "instructor")

        assert assignment.is_active is True
        assert assignment.role == "instructor"
        assert assignment.user == user

        # Guardian perms matching Cohort content type should be set
        perms = get_perms(user, cohort)
        assert "view_cohort" in perms

    @pytest.mark.django_db
    def test_sets_guardian_permissions_matching_target_content_type(self) -> None:
        """Only permissions matching the target's content type are synced."""
        user = UserFactory()
        student = StudentFactory()

        # Instructor has view_cohort, view_student, change_student
        # On a Student object, only view_student and change_student match
        assign_object_role(user, student, "instructor")
        perms = get_perms(user, student)
        assert "view_student" in perms
        assert "change_student" in perms
        assert "view_cohort" not in perms

    @pytest.mark.django_db
    def test_reactivates_inactive_assignment(self) -> None:
        """Assigning a previously deactivated role reactivates it."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an inactive assignment directly
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="instructor", is_active=False
        )

        # Re-assign should reactivate
        assignment = assign_object_role(user, cohort, "instructor")
        assert assignment.is_active is True

        # Guardian perms should be set
        perms = get_perms(user, cohort)
        assert "view_cohort" in perms

    @pytest.mark.django_db
    def test_invalid_role_raises_value_error_no_assignment(self) -> None:
        """Invalid role raises ValueError and creates no assignment."""
        user = UserFactory()
        cohort = CohortFactory()

        with pytest.raises(ValueError, match="Unknown role"):
            assign_object_role(user, cohort, "nonexistent_role")

        ct = ContentType.objects.get_for_model(cohort)
        assert not ObjectRoleAssignment.objects.filter(
            user=user, content_type=ct, object_id=str(cohort.pk)
        ).exists()


class TestRemoveObjectRole:
    """Tests for remove_object_role."""

    @pytest.mark.django_db
    def test_deactivates_assignment_and_removes_guardian_permissions(self) -> None:
        """Removing a role deactivates the assignment and removes guardian perms."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "instructor")

        remove_object_role(user, cohort, "instructor")

        ct = ContentType.objects.get_for_model(cohort)
        assignment = ObjectRoleAssignment.objects.get(
            user=user, content_type=ct, object_id=str(cohort.pk), role="instructor"
        )
        assert assignment.is_active is False
        assert get_perms(user, cohort) == []

    @pytest.mark.django_db
    def test_shared_permissions_preserved_by_other_roles(self) -> None:
        """When removing a role, permissions shared with other active roles are kept."""
        user = UserFactory()
        cohort = CohortFactory()

        # site_admin has all cohort perms, instructor has view_cohort
        assign_object_role(user, cohort, "site_admin")
        assign_object_role(user, cohort, "instructor")

        # Remove site_admin — instructor's view_cohort should remain
        remove_object_role(user, cohort, "site_admin")

        perms = get_perms(user, cohort)
        assert "view_cohort" in perms
        # site_admin-only cohort perms should be gone
        assert "add_cohort" not in perms
        assert "delete_cohort" not in perms


class TestSyncUserObjectPermissions:
    """Tests for sync_user_object_permissions."""

    @pytest.mark.django_db
    def test_computes_correct_diff(self) -> None:
        """sync returns correct added/removed sets for matching permissions."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an active role assignment
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="instructor", is_active=True
        )

        result = sync_user_object_permissions(user, cohort)

        # Only cohort-matching perms from instructor role should be added
        assert "freedom_ls_student_management.view_cohort" in result["added"]
        assert result["removed"] == set()

    @pytest.mark.django_db
    def test_dry_run_does_not_apply_changes(self) -> None:
        """dry_run=True reports changes without applying them."""
        user = UserFactory()
        cohort = CohortFactory()

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="instructor", is_active=True
        )

        result = sync_user_object_permissions(user, cohort, dry_run=True)

        # Should report additions
        assert len(result["added"]) > 0
        # But guardian should have no perms
        assert get_perms(user, cohort) == []

    @pytest.mark.django_db
    def test_no_roles_removes_all_permissions(self) -> None:
        """When user has no active roles, all permissions are removed."""
        user = UserFactory()
        cohort = CohortFactory()

        # Assign then remove
        assign_object_role(user, cohort, "instructor")
        assert len(get_perms(user, cohort)) > 0

        # Deactivate the assignment manually
        ct = ContentType.objects.get_for_model(cohort)
        ObjectRoleAssignment.objects.filter(
            user=user, content_type=ct, object_id=str(cohort.pk)
        ).update(is_active=False)

        result = sync_user_object_permissions(user, cohort)

        assert result["added"] == set()
        assert len(result["removed"]) > 0
        assert get_perms(user, cohort) == []


class TestSiteRoleFunctions:
    """Tests for assign_site_role and remove_site_role."""

    @pytest.mark.django_db
    def test_assign_site_role_creates_assignment(self, mock_site_context: Site) -> None:
        """assign_site_role creates a SiteRoleAssignment and syncs guardian."""
        user = UserFactory()
        assignment = assign_site_role(user, "site_admin")

        assert assignment.is_active is True
        assert assignment.role == "site_admin"
        assert assignment.site == mock_site_context
        assert SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_remove_site_role_deactivates_assignment(
        self, mock_site_context: Site
    ) -> None:
        """remove_site_role deactivates the assignment."""
        user = UserFactory()
        assign_site_role(user, "site_admin")
        remove_site_role(user, "site_admin")

        assert not SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_remove_site_role_preserves_other_active_roles(
        self, mock_site_context: Site
    ) -> None:
        """Removing one site role preserves other active site role assignments."""
        user = UserFactory()
        assign_site_role(user, "site_admin")
        assign_site_role(user, "instructor")

        remove_site_role(user, "site_admin")

        # site_admin should be deactivated, instructor should remain
        assert not SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()
        assert SiteRoleAssignment.objects.filter(
            user=user, role="instructor", is_active=True
        ).exists()


class TestSystemRoleFunctions:
    """Tests for assign_system_role and remove_system_role."""

    @pytest.mark.django_db
    def test_assign_system_role_creates_assignment(self) -> None:
        """assign_system_role creates a SystemRoleAssignment."""
        user = UserFactory()
        assignment = assign_system_role(user, "system_admin")

        assert assignment.is_active is True
        assert assignment.role == "system_admin"
        assert SystemRoleAssignment.objects.filter(
            user=user, role="system_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_remove_system_role_deactivates_assignment(self) -> None:
        """remove_system_role deactivates the assignment."""
        user = UserFactory()
        assign_system_role(user, "system_admin")
        remove_system_role(user, "system_admin")

        assert not SystemRoleAssignment.objects.filter(
            user=user, role="system_admin", is_active=True
        ).exists()
        assignment = SystemRoleAssignment.objects.get(user=user, role="system_admin")
        assert assignment.is_active is False


class TestGetObjectRoles:
    """Tests for get_object_roles."""

    @pytest.mark.django_db
    def test_returns_active_roles(self) -> None:
        """Returns set of active role names for user on object."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "instructor")
        assign_object_role(user, cohort, "ta")

        roles = get_object_roles(user, cohort)
        assert roles == {"instructor", "ta"}

    @pytest.mark.django_db
    def test_excludes_inactive_roles(self) -> None:
        """Inactive roles are not returned."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "instructor")
        remove_object_role(user, cohort, "instructor")

        roles = get_object_roles(user, cohort)
        assert roles == set()


class TestGuardianIntegration:
    """Integration test: proves guardian filtering works with role assignments."""

    @pytest.mark.django_db
    def test_get_objects_for_user_returns_cohort_after_role_assignment(self) -> None:
        """Assigning instructor role on a Cohort makes get_objects_for_user return it."""
        from freedom_ls.student_management.models import Cohort

        user = UserFactory()
        cohort: Cohort = CohortFactory()
        other_cohort: Cohort = CohortFactory()

        assign_object_role(user, cohort, "instructor")

        accessible = get_objects_for_user(
            user, "freedom_ls_student_management.view_cohort", klass=Cohort
        )
        assert cohort in accessible
        assert other_cohort not in accessible
