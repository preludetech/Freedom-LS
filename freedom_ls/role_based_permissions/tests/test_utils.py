"""Tests for role_based_permissions utility functions."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
import time_machine
from guardian.models import UserObjectPermission
from guardian.shortcuts import get_objects_for_user, get_perms
from pytest_mock import MockerFixture

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
    SiteRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.loader import clear_caches, get_role_config
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
    deactivate_object_role,
    deactivate_site_role,
    deactivate_system_role,
    delete_role_rows_for,
    get_cohort_roles,
    get_object_roles,
    sync_user_object_permissions,
)
from freedom_ls.tests.audit_assertions import assert_entry


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    """Clear the loader and permission caches between tests."""
    clear_caches()
    yield
    clear_caches()


@pytest.fixture(autouse=True)
def _site_context(mock_site_context: Site) -> None:
    """Every test here builds site-aware objects and assigns roles."""


class TestCheckRoleNameInConfig:
    """Tests for check_role_name_in_config."""

    @pytest.mark.django_db
    def test_valid_role_passes(self) -> None:
        """Known role does not raise."""
        check_role_name_in_config("cohort_admin")

    @pytest.mark.django_db
    def test_unknown_role_raises_value_error(self) -> None:
        """Unknown role raises ValueError."""
        with pytest.raises(ValueError, match="Unknown role"):
            check_role_name_in_config("nonexistent_role")


@pytest.fixture
def no_site_id(mocker: MockerFixture) -> None:
    """Make the ambient-site lookup fail as it does when SITE_ID is unset."""
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        side_effect=ImproperlyConfigured("SITE_ID not set"),
    )


class TestObjectRolesWithoutSiteId:
    """Object roles resolve their config from the target's site, not SITE_ID."""

    @pytest.mark.django_db
    def test_assign_object_role_works_without_site_id(self, no_site_id: None) -> None:
        """Assigning an object role used to crash when SITE_ID was unset."""
        user = UserFactory()
        cohort = CohortFactory()

        assignment = assign_object_role(user, cohort, "cohort_admin")

        assert assignment.is_active is True

    @pytest.mark.django_db
    def test_remove_object_role_works_without_site_id(
        self, mocker: MockerFixture
    ) -> None:
        """Removing an object role used to crash when SITE_ID was unset."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")
        mocker.patch(
            "django.contrib.sites.models.SiteManager.get_current",
            side_effect=ImproperlyConfigured("SITE_ID not set"),
        )

        deactivate_object_role(user, cohort, "cohort_admin")

        assert "view_cohort" not in get_perms(user, cohort)


class TestAssignObjectRole:
    """Tests for assign_object_role."""

    @pytest.mark.django_db
    def test_creates_assignment_and_sets_guardian_permissions(self) -> None:
        """Assigning an object role creates the assignment and sets matching guardian perms."""
        user = UserFactory()
        cohort = CohortFactory()
        assignment = assign_object_role(user, cohort, "cohort_admin")

        assert assignment.is_active is True
        assert assignment.role == "cohort_admin"
        assert assignment.user == user

        # Guardian perms matching Cohort content type should be set
        perms = get_perms(user, cohort)
        assert "view_cohort" in perms

    @pytest.mark.django_db
    def test_sets_guardian_permissions_matching_target_content_type(
        self, mock_site_context: Site
    ) -> None:
        """Only permissions matching the target's content type are synced."""
        user = UserFactory()

        # cohort_admin has cohort-scoped permissions (view_cohort, etc.)
        # When synced against a Site object, none of those match the Site content type.
        # Create assignment to bypass scope enforcement (testing content type filtering).
        ObjectRoleAssignmentFactory(
            user=user,
            target_object=mock_site_context,
            role="cohort_admin",
        )
        sync_user_object_permissions(user, mock_site_context)
        perms = get_perms(user, mock_site_context)
        assert "view_cohort" not in perms

        # But on a Cohort object, view_cohort should match
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")
        cohort_perms = get_perms(user, cohort)
        assert "view_cohort" in cohort_perms

    @pytest.mark.django_db
    def test_reactivates_inactive_assignment(self) -> None:
        """Assigning a previously deactivated role reactivates it."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an inactive assignment directly
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_admin", is_active=False
        )

        # Re-assign should reactivate
        assignment = assign_object_role(user, cohort, "cohort_admin")
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

    @pytest.mark.django_db
    def test_reassigning_active_role_updates_assigned_by(self) -> None:
        """Re-assigning an already-active role updates the assigned_by field."""
        user = UserFactory()
        original_assigner = UserFactory()
        new_assigner = UserFactory()
        cohort = CohortFactory()

        assignment = assign_object_role(
            user, cohort, "cohort_admin", assigned_by=original_assigner
        )
        assert assignment.assigned_by == original_assigner

        assignment = assign_object_role(
            user, cohort, "cohort_admin", assigned_by=new_assigner
        )
        assert assignment.assigned_by == new_assigner


class TestRemoveObjectRole:
    """Tests for deactivate_object_role."""

    @pytest.mark.django_db
    def test_deactivates_assignment_and_removes_guardian_permissions(self) -> None:
        """Removing a role deactivates the assignment and removes guardian perms."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")

        deactivate_object_role(user, cohort, "cohort_admin")

        ct = ContentType.objects.get_for_model(cohort)
        assignment = ObjectRoleAssignment.objects.get(
            user=user, content_type=ct, object_id=str(cohort.pk), role="cohort_admin"
        )
        assert assignment.is_active is False
        assert get_perms(user, cohort) == []

    @pytest.mark.django_db
    def test_shared_permissions_preserved_by_other_roles(self) -> None:
        """When removing a role, permissions shared with other active roles are kept."""
        user = UserFactory()
        cohort = CohortFactory()

        # cohort_admin and cohort_viewer both have view_cohort
        assign_object_role(user, cohort, "cohort_admin")
        assign_object_role(user, cohort, "cohort_viewer")

        # Remove cohort_admin — cohort_viewer's view_cohort should remain
        deactivate_object_role(user, cohort, "cohort_admin")

        perms = get_perms(user, cohort)
        assert "view_cohort" in perms

    @pytest.mark.django_db
    def test_removing_role_advances_updated_at(self) -> None:
        """Removing a role is a write: the assignment's updated_at moves with it."""
        user = UserFactory()
        cohort = CohortFactory()
        with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
            assign_object_role(user, cohort, "cohort_admin")

        with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
            deactivate_object_role(user, cohort, "cohort_admin")

        ct = ContentType.objects.get_for_model(cohort)
        assignment = ObjectRoleAssignment.objects.get(
            user=user, content_type=ct, object_id=str(cohort.pk), role="cohort_admin"
        )
        assert assignment.updated_at == datetime(2026, 2, 1, tzinfo=UTC)


class TestSyncUserObjectPermissions:
    """Tests for sync_user_object_permissions."""

    @pytest.mark.django_db
    def test_computes_correct_diff(self) -> None:
        """sync returns correct added/removed sets for matching permissions."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an active role assignment
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_admin", is_active=True
        )

        result = sync_user_object_permissions(user, cohort)

        # Only cohort-matching perms from cohort_admin role should be added
        assert "freedom_ls_learner_management.view_cohort" in result["added"]
        assert result["removed"] == set()

    @pytest.mark.django_db
    def test_dry_run_does_not_apply_changes(self) -> None:
        """dry_run=True reports changes without applying them."""
        user = UserFactory()
        cohort = CohortFactory()

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_admin", is_active=True
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
        assign_object_role(user, cohort, "cohort_admin")
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


class TestSyncUserObjectPermissionsSiteConfig:
    """Tests that sync_user_object_permissions uses the correct site config."""

    @pytest.mark.django_db
    def test_site_object_resolves_config_from_site_name(
        self, mock_site_context: Site, mocker: MockerFixture
    ) -> None:
        """When syncing a Site object, config is loaded for that site's name."""
        spy = mocker.patch(
            "freedom_ls.role_based_permissions.utils.get_role_config",
            wraps=get_role_config,
        )
        user = UserFactory()
        sync_user_object_permissions(user, mock_site_context)
        spy.assert_called_once_with(mock_site_context.name)

    @pytest.mark.django_db
    def test_explicit_site_name_overrides_auto_detection(
        self, mock_site_context: Site, mocker: MockerFixture
    ) -> None:
        """Explicit site_name parameter takes precedence."""
        spy = mocker.patch(
            "freedom_ls.role_based_permissions.utils.get_role_config",
            wraps=get_role_config,
        )
        user = UserFactory()
        sync_user_object_permissions(user, mock_site_context, site_name="custom_site")
        spy.assert_called_once_with("custom_site")


class TestSiteRoleFunctions:
    """Tests for assign_site_role and deactivate_site_role."""

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
        """deactivate_site_role deactivates the assignment."""
        user = UserFactory()
        assign_site_role(user, "site_admin")
        assign_site_role(UserFactory(), "site_admin")
        deactivate_site_role(user, "site_admin")

        assert not SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_removing_site_role_advances_updated_at(
        self, mock_site_context: Site
    ) -> None:
        """Removing a role is a write: the assignment's updated_at moves with it."""
        user = UserFactory()
        with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
            assign_site_role(user, "site_admin")
            assign_site_role(UserFactory(), "site_admin")

        with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
            deactivate_site_role(user, "site_admin")

        assignment = SiteRoleAssignment.objects.get(user=user, role="site_admin")
        assert assignment.updated_at == datetime(2026, 2, 1, tzinfo=UTC)

    @pytest.mark.django_db
    def test_reassigning_active_site_role_updates_assigned_by(
        self, mock_site_context: Site
    ) -> None:
        """Re-assigning an already-active site role updates the assigned_by field."""
        user = UserFactory()
        original_assigner = UserFactory()
        new_assigner = UserFactory()

        assignment = assign_site_role(user, "site_admin", assigned_by=original_assigner)
        assert assignment.assigned_by == original_assigner

        assignment = assign_site_role(user, "site_admin", assigned_by=new_assigner)
        assert assignment.assigned_by == new_assigner

    @pytest.mark.django_db
    def test_remove_site_role_preserves_other_active_roles(
        self, mock_site_context: Site
    ) -> None:
        """Removing one site role preserves other active site role assignments."""
        user = UserFactory()
        assign_site_role(user, "site_admin")
        assign_site_role(UserFactory(), "site_admin")

        # Create a second site role assignment to test preservation
        # (only site_admin has assignment_scope="site" in the base config)
        SiteRoleAssignmentFactory(user=user, role="other_role")

        deactivate_site_role(user, "site_admin")

        # site_admin should be deactivated, other_role should remain
        assert not SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()
        assert SiteRoleAssignment.objects.filter(
            user=user, role="other_role", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_removing_last_active_site_admin_is_refused(
        self, mock_site_context: Site
    ) -> None:
        """Removing the site's only active site_admin is refused and changes nothing."""
        user = UserFactory()
        assign_site_role(user, "site_admin")

        with pytest.raises(RoleChangeRefused) as exc_info:
            deactivate_site_role(user, "site_admin")

        assert exc_info.value.reason == RefusalReason.LAST_SITE_ADMIN
        assert SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_removing_site_admin_ignores_an_inactive_users_assignment(
        self, mock_site_context: Site
    ) -> None:
        """A second site_admin assignment held by an inactive user doesn't count."""
        user = UserFactory()
        inactive_admin = UserFactory(is_active=False)
        assign_site_role(user, "site_admin")
        assign_site_role(inactive_admin, "site_admin")

        with pytest.raises(RoleChangeRefused) as exc_info:
            deactivate_site_role(user, "site_admin")

        assert exc_info.value.reason == RefusalReason.LAST_SITE_ADMIN
        assert SiteRoleAssignment.objects.filter(
            user=user, role="site_admin", is_active=True
        ).exists()

    @pytest.mark.django_db
    def test_removing_a_site_admin_role_the_user_does_not_hold_is_unaffected(
        self, mock_site_context: Site
    ) -> None:
        """Removing a role the user never held is a no-op, not a refusal."""
        user = UserFactory()
        assign_site_role(UserFactory(), "site_admin")

        deactivate_site_role(user, "site_admin")

        assert not SiteRoleAssignment.objects.filter(
            user=user, role="site_admin"
        ).exists()

    @pytest.mark.django_db
    def test_removing_a_non_site_admin_site_role_is_unaffected_by_the_guard(
        self, mock_site_context: Site
    ) -> None:
        """The last-admin guard only applies to site_admin."""
        user = UserFactory()
        assign_site_role(user, "site_admin")
        SiteRoleAssignmentFactory(user=user, role="cohort_admin")

        deactivate_site_role(user, "cohort_admin")

        assert not SiteRoleAssignment.objects.filter(
            user=user, role="cohort_admin", is_active=True
        ).exists()


class TestSystemRoleFunctions:
    """Tests for assign_system_role and deactivate_system_role."""

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
    def test_reassigning_active_system_role_updates_assigned_by(self) -> None:
        """Re-assigning an already-active system role updates the assigned_by field."""
        user = UserFactory()
        original_assigner = UserFactory()
        new_assigner = UserFactory()

        assignment = assign_system_role(
            user, "system_admin", assigned_by=original_assigner
        )
        assert assignment.assigned_by == original_assigner

        assignment = assign_system_role(user, "system_admin", assigned_by=new_assigner)
        assert assignment.assigned_by == new_assigner

    @pytest.mark.django_db
    def test_remove_system_role_deactivates_assignment(self) -> None:
        """deactivate_system_role deactivates the assignment."""
        user = UserFactory()
        assign_system_role(user, "system_admin")
        deactivate_system_role(user, "system_admin")

        assert not SystemRoleAssignment.objects.filter(
            user=user, role="system_admin", is_active=True
        ).exists()
        assignment = SystemRoleAssignment.objects.get(user=user, role="system_admin")
        assert assignment.is_active is False

    @pytest.mark.django_db
    def test_removing_system_role_advances_updated_at(self) -> None:
        """Removing a role is a write: the assignment's updated_at moves with it."""
        user = UserFactory()
        with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
            assign_system_role(user, "system_admin")

        with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
            deactivate_system_role(user, "system_admin")

        assignment = SystemRoleAssignment.objects.get(user=user, role="system_admin")
        assert assignment.updated_at == datetime(2026, 2, 1, tzinfo=UTC)


class TestGetObjectRoles:
    """Tests for get_object_roles."""

    @pytest.mark.django_db
    def test_returns_active_roles(self) -> None:
        """Returns set of active role names for user on object."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")
        assign_object_role(user, cohort, "cohort_viewer")

        roles = get_object_roles(user, cohort)
        assert roles == {"cohort_admin", "cohort_viewer"}

    @pytest.mark.django_db
    def test_excludes_inactive_roles(self) -> None:
        """Inactive roles are not returned."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")
        deactivate_object_role(user, cohort, "cohort_admin")

        roles = get_object_roles(user, cohort)
        assert roles == set()


class TestGuardianIntegration:
    """Integration test: proves guardian filtering works with role assignments."""

    @pytest.mark.django_db
    def test_get_objects_for_user_returns_cohort_after_role_assignment(self) -> None:
        """Assigning cohort_admin role on a Cohort makes get_objects_for_user return it."""
        from freedom_ls.learner_management.models import Cohort

        user = UserFactory()
        cohort: Cohort = CohortFactory()
        other_cohort: Cohort = CohortFactory()

        assign_object_role(user, cohort, "cohort_admin")

        accessible = get_objects_for_user(
            user, "freedom_ls_learner_management.view_cohort", klass=Cohort
        )
        assert cohort in accessible
        assert other_cohort not in accessible


class TestDeleteRoleRowsFor:
    @pytest.mark.django_db
    def test_removes_active_and_inactive_assignments_on_the_target(self) -> None:
        cohort = CohortFactory()
        assign_object_role(UserFactory(), cohort, "cohort_admin")
        ObjectRoleAssignmentFactory(
            target_object=cohort, role="cohort_viewer", is_active=False
        )

        delete_role_rows_for(cohort)

        assert not ObjectRoleAssignment.objects.filter(
            content_type=ContentType.objects.get_for_model(cohort),
            object_id=str(cohort.pk),
        ).exists()

    @pytest.mark.django_db
    def test_removes_the_guardian_rows_on_the_target(self) -> None:
        cohort = CohortFactory()
        assign_object_role(UserFactory(), cohort, "cohort_admin")

        delete_role_rows_for(cohort)

        assert not UserObjectPermission.objects.filter(
            content_type=ContentType.objects.get_for_model(cohort),
            object_pk=str(cohort.pk),
        ).exists()

    @pytest.mark.django_db
    def test_records_a_removal_for_each_active_assignment(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory(name="Cohort A")
        admin = UserFactory()
        viewer = UserFactory()
        remover = UserFactory()
        ObjectRoleAssignmentFactory(
            user=admin, target_object=cohort, role="cohort_admin"
        )
        ObjectRoleAssignmentFactory(
            user=viewer, target_object=cohort, role="cohort_viewer"
        )

        delete_role_rows_for(cohort, removed_by=remover, reason="Cohort deleted")

        removed = AuditLogEntry.unscoped.filter(action="role.removed")
        assert sorted(removed.values_list("target_object_id", flat=True)) == sorted(
            [str(admin.pk), str(viewer.pk)]
        )
        assert set(removed.values_list("actor", flat=True)) == {remover.pk}
        assert set(removed.values_list("reason", flat=True)) == {"Cohort deleted"}

    @pytest.mark.django_db
    def test_records_nothing_for_an_inactive_assignment(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory()
        ObjectRoleAssignmentFactory(
            target_object=cohort, role="cohort_viewer", is_active=False
        )

        delete_role_rows_for(cohort)

        assert not AuditLogEntry.unscoped.filter(action="role.removed").exists()

    @pytest.mark.django_db
    def test_a_removal_with_no_actor_logs_as_the_system(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory(name="Cohort A")
        user = UserFactory()
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_admin", is_active=True
        )

        delete_role_rows_for(cohort)

        assert_entry(
            action="role.removed",
            actor=None,
            target=user,
            target_label=user.display_name,
            organisation=cohort.organisation,
            subjects=(cohort,),
            details={
                "role": "cohort_admin",
                "role_label": "Cohort admin",
                "scope": "Cohort A",
            },
        )

    @pytest.mark.django_db
    def test_a_role_no_longer_configured_is_labelled_by_its_code(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory()
        ObjectRoleAssignmentFactory(
            target_object=cohort, role="retired_role", is_active=True
        )

        delete_role_rows_for(cohort)

        entry = AuditLogEntry.unscoped.get(action="role.removed")
        assert entry.details["role_label"] == "retired_role"

    @pytest.mark.django_db
    def test_leaves_another_targets_rows_alone(self) -> None:
        cohort = CohortFactory()
        other = CohortFactory()
        assign_object_role(UserFactory(), other, "cohort_admin")

        delete_role_rows_for(cohort)

        other_type = ContentType.objects.get_for_model(other)
        assert ObjectRoleAssignment.objects.filter(
            content_type=other_type, object_id=str(other.pk)
        ).exists()
        assert UserObjectPermission.objects.filter(
            content_type=other_type, object_pk=str(other.pk)
        ).exists()


class TestAssignmentScopeEnforcement:
    """Tests that assignment functions enforce the role's assignment_scope."""

    @pytest.mark.django_db
    def test_assign_object_role_rejects_site_scoped_role(self) -> None:
        """Cannot use assign_object_role with a site-scoped role."""
        user = UserFactory()
        cohort = CohortFactory()
        with pytest.raises(ValueError, match="assignment_scope='site'"):
            assign_object_role(user, cohort, "site_admin")

    @pytest.mark.django_db
    def test_assign_object_role_rejects_system_scoped_role(self) -> None:
        """Cannot use assign_object_role with a system-scoped role."""
        user = UserFactory()
        cohort = CohortFactory()
        with pytest.raises(ValueError, match="assignment_scope='system'"):
            assign_object_role(user, cohort, "system_admin")

    @pytest.mark.django_db
    def test_assign_site_role_rejects_object_scoped_role(
        self, mock_site_context: Site
    ) -> None:
        """Cannot use assign_site_role with an object-scoped role."""
        user = UserFactory()
        with pytest.raises(ValueError, match="assignment_scope='object'"):
            assign_site_role(user, "cohort_admin")

    @pytest.mark.django_db
    def test_assign_system_role_rejects_object_scoped_role(self) -> None:
        """Cannot use assign_system_role with an object-scoped role."""
        user = UserFactory()
        with pytest.raises(ValueError, match="assignment_scope='object'"):
            assign_system_role(user, "cohort_admin")


class TestConvenienceRoleQueries:
    """Tests for get_cohort_roles convenience wrapper."""

    @pytest.mark.django_db
    def test_get_cohort_roles_returns_active_roles(self) -> None:
        """get_cohort_roles returns the same result as get_object_roles."""
        user = UserFactory()
        cohort = CohortFactory()
        assign_object_role(user, cohort, "cohort_admin")

        assert get_cohort_roles(user, cohort) == {"cohort_admin"}
        assert get_cohort_roles(user, cohort) == get_object_roles(user, cohort)


_JANUARY = datetime(2026, 1, 1, tzinfo=UTC)
_FEBRUARY = datetime(2026, 2, 1, tzinfo=UTC)


class TestAssignedAt:
    """assigned_at is the time of the grant that set assigned_by."""

    @pytest.mark.django_db
    def test_reactivating_an_object_assignment_moves_assigned_at(self) -> None:
        user = UserFactory()
        cohort = CohortFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_object_role(user, cohort, "cohort_admin")
        deactivate_object_role(user, cohort, "cohort_admin")

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_object_role(user, cohort, "cohort_admin")

        assignment.refresh_from_db()
        assert assignment.assigned_at == _FEBRUARY

    @pytest.mark.django_db
    def test_changing_the_grantor_of_an_object_assignment_moves_assigned_at(
        self,
    ) -> None:
        user = UserFactory()
        cohort = CohortFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_object_role(user, cohort, "cohort_admin", UserFactory())

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_object_role(user, cohort, "cohort_admin", UserFactory())

        assignment.refresh_from_db()
        assert assignment.assigned_at == _FEBRUARY

    @pytest.mark.django_db
    def test_an_unchanged_object_assignment_keeps_assigned_at(self) -> None:
        user = UserFactory()
        cohort = CohortFactory()
        grantor = UserFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_object_role(user, cohort, "cohort_admin", grantor)

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_object_role(user, cohort, "cohort_admin", grantor)

        assignment.refresh_from_db()
        assert assignment.assigned_at == _JANUARY

    @pytest.mark.django_db
    def test_reactivating_a_site_assignment_moves_assigned_at(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_site_role(user, "site_admin")
            assign_site_role(UserFactory(), "site_admin")
        deactivate_site_role(user, "site_admin")

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_site_role(user, "site_admin")

        assignment.refresh_from_db()
        assert assignment.assigned_at == _FEBRUARY

    @pytest.mark.django_db
    def test_changing_the_grantor_of_a_site_assignment_moves_assigned_at(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_site_role(user, "site_admin", UserFactory())

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_site_role(user, "site_admin", UserFactory())

        assignment.refresh_from_db()
        assert assignment.assigned_at == _FEBRUARY

    @pytest.mark.django_db
    def test_an_unchanged_site_assignment_keeps_assigned_at(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        grantor = UserFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_site_role(user, "site_admin", grantor)

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_site_role(user, "site_admin", grantor)

        assignment.refresh_from_db()
        assert assignment.assigned_at == _JANUARY

    @pytest.mark.django_db
    def test_reactivating_a_system_assignment_keeps_assigned_at(self) -> None:
        user = UserFactory()
        with time_machine.travel(_JANUARY, tick=False):
            assign_system_role(user, "system_admin")
        deactivate_system_role(user, "system_admin")

        with time_machine.travel(_FEBRUARY, tick=False):
            assignment = assign_system_role(user, "system_admin")

        assignment.refresh_from_db()
        assert assignment.is_active is True
        assert assignment.assigned_at == _JANUARY


def _change_then_fail(change: Callable[[], object]) -> None:
    """Run `change` in a transaction that then rolls back."""
    with transaction.atomic():
        change()
        raise RuntimeError


@pytest.mark.django_db
class TestRoleAuditEntries:
    """Each role utility writes one entry per change, inside the caller's
    transaction, and none for a call that changes nothing."""

    def test_granting_on_a_cohort_records_the_cohorts_organisation(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory(name="Cohort A")
        organisation = cohort.organisation
        user = UserFactory()
        grantor = UserFactory()

        assign_object_role(user, cohort, "cohort_admin", assigned_by=grantor)

        assert_entry(
            action="role.assigned",
            actor=grantor,
            target=user,
            target_label=user.display_name,
            organisation=organisation,
            subjects=(cohort,),
            details={
                "role": "cohort_admin",
                "role_label": "Cohort admin",
                "scope": "Cohort A",
            },
        )

    def test_granting_on_an_organisation_records_that_organisation(
        self, mock_site_context: Site
    ) -> None:
        organisation = CohortFactory().organisation
        user = UserFactory()

        assign_object_role(user, organisation, "organisation_admin")

        entry = AuditLogEntry.unscoped.get(action="role.assigned")
        assert entry.organisation == organisation
        assert entry.details["scope"] == str(organisation)

    def test_granting_on_a_course_records_no_organisation(
        self, mock_site_context: Site
    ) -> None:
        course = CohortCourseRegistrationFactory(course__title="Algebra").course

        assign_object_role(UserFactory(), course, "learner")

        entry = AuditLogEntry.unscoped.get()
        assert entry.organisation is None
        assert entry.details["scope"] == "Algebra"

    def test_regranting_an_active_role_by_another_grantor_writes_a_second_grant(
        self, mock_site_context: Site
    ) -> None:
        """The re-grant moves "added by" to the new grantor, so the log says who."""
        cohort = CohortFactory()
        user = UserFactory()
        second_grantor = UserFactory()
        assign_object_role(user, cohort, "cohort_admin", assigned_by=UserFactory())

        assign_object_role(user, cohort, "cohort_admin", assigned_by=second_grantor)

        actors = list(
            AuditLogEntry.unscoped.filter(action="role.assigned")
            .order_by("created_at")
            .values_list("actor", flat=True)
        )
        assert actors[1:] == [second_grantor.pk]
        assert len(actors) == 2

    def test_regranting_an_active_role_by_the_same_grantor_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory()
        user = UserFactory()
        grantor = UserFactory()
        assign_object_role(user, cohort, "cohort_admin", assigned_by=grantor)

        assign_object_role(user, cohort, "cohort_admin", assigned_by=grantor)

        assert AuditLogEntry.unscoped.count() == 1

    def test_reactivating_an_inactive_role_writes_an_entry(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory()
        user = UserFactory()
        assign_object_role(user, cohort, "cohort_admin")
        deactivate_object_role(user, cohort, "cohort_admin")

        assign_object_role(user, cohort, "cohort_admin")

        actions = list(
            AuditLogEntry.unscoped.order_by("created_at").values_list(
                "action", flat=True
            )
        )
        assert actions == ["role.assigned", "role.deactivated", "role.assigned"]

    def test_removing_an_object_role_writes_once_with_the_reason(
        self, mock_site_context: Site
    ) -> None:
        cohort = CohortFactory()
        user = UserFactory()
        remover = UserFactory()
        assign_object_role(user, cohort, "cohort_admin")

        deactivate_object_role(user, cohort, "cohort_admin", remover, reason="Left")
        deactivate_object_role(user, cohort, "cohort_admin", remover, reason="Left")

        entry = AuditLogEntry.unscoped.get(action="role.deactivated")
        assert entry.actor == remover
        assert entry.reason == "Left"

    def test_removing_a_role_never_held_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        deactivate_object_role(UserFactory(), CohortFactory(), "cohort_admin")

        assert AuditLogEntry.unscoped.count() == 0

    def test_a_null_grantor_logs_a_null_actor(self, mock_site_context: Site) -> None:
        cohort = CohortFactory()
        user = UserFactory()
        assign_site_role(UserFactory(), "site_admin")
        before = AuditLogEntry.unscoped.count()

        assign_object_role(user, cohort, "cohort_admin")
        deactivate_object_role(user, cohort, "cohort_admin")
        assign_site_role(user, "site_admin")
        deactivate_site_role(user, "site_admin")

        entries = list(AuditLogEntry.unscoped.filter(target_object_id=str(user.pk)))
        assert len(entries) == 4
        assert AuditLogEntry.unscoped.count() == before + 4
        assert {(e.actor, e.actor_label) for e in entries} == {(None, "")}

    def test_site_role_entries_have_no_organisation_and_the_roles_site(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        other_admin = UserFactory()
        assign_site_role(other_admin, "site_admin")

        assign_site_role(user, "site_admin", site=mock_site_context)
        deactivate_site_role(user, "site_admin", site=mock_site_context)

        entries = AuditLogEntry.unscoped.filter(target_object_id=str(user.pk))
        assert [e.action for e in entries.order_by("created_at")] == [
            "role.assigned",
            "role.deactivated",
        ]
        assert {(e.organisation, e.site) for e in entries} == {
            (None, mock_site_context)
        }
        assert {e.details["scope"] for e in entries} == {str(mock_site_context)}

    def test_removing_a_site_role_twice_writes_once(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        assign_site_role(UserFactory(), "site_admin")
        assign_site_role(user, "site_admin")

        deactivate_site_role(user, "site_admin")
        deactivate_site_role(user, "site_admin")

        assert AuditLogEntry.unscoped.filter(action="role.deactivated").count() == 1

    def test_a_refused_last_site_admin_removal_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        assign_site_role(user, "site_admin")
        before = AuditLogEntry.unscoped.count()

        with pytest.raises(RoleChangeRefused):
            deactivate_site_role(user, "site_admin")

        assert AuditLogEntry.unscoped.count() == before

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("utility", ["assign_object", "assign_site"])
    def test_a_grant_rolled_back_by_the_caller_leaves_no_entry(
        self, mock_site_context: Site, utility: str
    ) -> None:
        user = UserFactory()
        cohort = CohortFactory()

        change = (
            (lambda: assign_object_role(user, cohort, "cohort_admin"))
            if utility == "assign_object"
            else (lambda: assign_site_role(user, "site_admin"))
        )

        with pytest.raises(RuntimeError):
            _change_then_fail(change)

        assert AuditLogEntry.unscoped.count() == 0

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("utility", ["remove_object", "remove_site"])
    def test_a_removal_rolled_back_by_the_caller_leaves_no_new_entry(
        self, mock_site_context: Site, utility: str
    ) -> None:
        user = UserFactory()
        cohort = CohortFactory()
        assign_site_role(UserFactory(), "site_admin")
        assign_site_role(user, "site_admin")
        assign_object_role(user, cohort, "cohort_admin")
        before = AuditLogEntry.unscoped.count()

        change = (
            (lambda: deactivate_object_role(user, cohort, "cohort_admin"))
            if utility == "remove_object"
            else (lambda: deactivate_site_role(user, "site_admin"))
        )

        with pytest.raises(RuntimeError):
            _change_then_fail(change)

        assert AuditLogEntry.unscoped.count() == before

    def test_the_system_role_utilities_write_nothing(self) -> None:
        user = UserFactory()

        assign_system_role(user, "system_admin")
        deactivate_system_role(user, "system_admin")

        assert AuditLogEntry.unscoped.count() == 0
