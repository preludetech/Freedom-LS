"""Tests for role_based_permissions management commands."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm
from pytest_mock import MockerFixture

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import CommandError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.types import Role, SiteRolesConfig
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _clear_role_config_cache() -> Generator[None]:
    """Clear the loader cache between tests."""
    get_role_config.cache_clear()
    yield
    get_role_config.cache_clear()


@pytest.fixture(autouse=True)
def _mock_get_current_site(mock_site_context: Site, mocker: MockerFixture) -> None:
    """Ensure Site.objects.get_current() returns the test site."""
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        return_value=mock_site_context,
    )


class TestSyncRolePermissionsNoAssignments:
    """Test sync command with no assignments."""

    @pytest.mark.django_db
    def test_runs_cleanly_reports_zero_drift(self) -> None:
        """Sync with no assignments runs cleanly and reports 0 drift."""
        out = _call_sync()
        assert "0 drifted" in out or "0 assignment" in out or "No drift" in out


class TestSyncRolePermissionsDetectsAndFixesDrift:
    """Test sync command detects and fixes drift."""

    @pytest.mark.django_db
    def test_detects_and_fixes_drift(self) -> None:
        """Manually added guardian perm is removed by sync command."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an active role assignment for 'ta' (has view_cohort, view_student)
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="ta", is_active=True
        )

        # Manually add a guardian perm that the role shouldn't have
        assign_perm("freedom_ls_student_management.add_cohort", user, cohort)

        # Verify it exists
        assert UserObjectPermission.objects.filter(
            user=user,
            permission__codename="add_cohort",
            content_type=ContentType.objects.get_for_model(cohort),
            object_pk=str(cohort.pk),
        ).exists()

        out = _call_sync()

        # The extra perm should be removed
        assert not UserObjectPermission.objects.filter(
            user=user,
            permission__codename="add_cohort",
            content_type=ContentType.objects.get_for_model(cohort),
            object_pk=str(cohort.pk),
        ).exists()

        # Should report drift
        assert "1 drifted" in out or "drift" in out.lower()


class TestSyncRolePermissionsDryRun:
    """Test sync command with --dry-run."""

    @pytest.mark.django_db
    def test_dry_run_reports_drift_but_no_changes(self) -> None:
        """--dry-run reports drift without changing guardian state."""
        user = UserFactory()
        cohort = CohortFactory()

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="ta", is_active=True
        )

        # Manually add an extra guardian perm
        assign_perm("freedom_ls_student_management.add_cohort", user, cohort)

        out = _call_sync("--dry-run")

        # The extra perm should still exist (dry run doesn't change anything)
        assert UserObjectPermission.objects.filter(
            user=user,
            permission__codename="add_cohort",
            content_type=ContentType.objects.get_for_model(cohort),
            object_pk=str(cohort.pk),
        ).exists()

        # Should still report drift
        assert "dry" in out.lower() or "drift" in out.lower()


class TestSyncRolePermissionsOrphanedAssignment:
    """Test sync command handles orphaned assignments (target object deleted)."""

    @pytest.mark.django_db
    def test_handles_orphaned_target_object(self) -> None:
        """Sync handles assignments where the target object has been deleted."""
        user = UserFactory()
        cohort = CohortFactory()
        ct = ContentType.objects.get_for_model(cohort)

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="ta", is_active=True
        )

        # Delete the cohort but leave the assignment
        cohort_pk = str(cohort.pk)
        cohort.delete()

        # Verify assignment still exists
        assert ObjectRoleAssignment.objects.filter(
            user=user, content_type=ct, object_id=cohort_pk, is_active=True
        ).exists()

        # Sync should not crash
        out = _call_sync()
        assert out is not None  # Command completed without error


class TestSyncRolePermissionsReportOrphans:
    """Test --report-orphans detects manually-granted guardian permissions."""

    @pytest.mark.django_db
    def test_report_orphans_detects_manual_guardian_perms(self) -> None:
        """--report-orphans detects guardian perms not traceable to any active role."""
        user = UserFactory()
        cohort = CohortFactory()

        # Manually grant a guardian perm with no role assignment
        assign_perm("freedom_ls_student_management.add_cohort", user, cohort)

        out = _call_sync("--report-orphans")

        assert "orphan" in out.lower()


# ============================================================
# Tests for validate_role_permissions command
# ============================================================


class TestValidateRolePermissionsValidConfig:
    """Test validate command with valid config."""

    @pytest.mark.django_db
    def test_valid_config_succeeds(self) -> None:
        """validate_role_permissions succeeds with default valid config."""
        out = _call_validate()
        assert "valid" in out.lower() or "ok" in out.lower() or "pass" in out.lower()


class TestValidateRolePermissionsInvalidRoleName:
    """Test validate command detects invalid role name."""

    @pytest.mark.django_db
    def test_invalid_role_name_reports_error(self) -> None:
        """Role name that is not a valid Python identifier is reported."""
        bad_config = SiteRolesConfig(
            {
                "not-valid-identifier": Role(
                    display_name="Bad Role",
                    permissions=frozenset(),
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.get_role_config",
                return_value=bad_config,
            ),
            pytest.raises(CommandError, match="not-valid-identifier"),
        ):
            _call_validate()


class TestValidateRolePermissionsUnknownPermission:
    """Test validate command detects unknown permissions in roles."""

    @pytest.mark.django_db
    def test_unknown_permission_reports_error(self) -> None:
        """Permission not in registry is reported as error."""
        bad_config = SiteRolesConfig(
            {
                "test_role": Role(
                    display_name="Test Role",
                    permissions=frozenset(
                        {
                            "nonexistent_app.nonexistent_perm",
                        }
                    ),
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.get_role_config",
                return_value=bad_config,
            ),
            pytest.raises(CommandError, match=r"nonexistent_app\.nonexistent_perm"),
        ):
            _call_validate()


class TestValidateRolePermissionsInvalidRoleType:
    """Test validate command detects invalid role_type."""

    @pytest.mark.django_db
    def test_invalid_role_type_reports_error(self) -> None:
        """role_type that is neither 'standalone' nor 'composable' is reported."""
        bad_config = SiteRolesConfig(
            {
                "test_role": Role(
                    display_name="Test Role",
                    permissions=frozenset(),
                    role_type="invalid_hint",
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.get_role_config",
                return_value=bad_config,
            ),
            pytest.raises(CommandError, match="invalid_hint"),
        ):
            _call_validate()


class TestValidateRolePermissionsOrphanedDbAssignment:
    """Test validate command detects orphaned DB assignments."""

    @pytest.mark.django_db
    def test_orphaned_db_assignment_reports_error(self) -> None:
        """Role in assignment table not in any config is reported as error."""
        user = UserFactory()
        # Create assignment with a role not in the config
        SystemRoleAssignment.objects.create(
            user=user, role="nonexistent_role_xyz", is_active=True
        )

        with pytest.raises(CommandError, match="nonexistent_role_xyz"):
            _call_validate()


class TestValidateRolePermissionsMultipleConfigs:
    """Test validate command validates multiple configs."""

    @pytest.mark.django_db
    def test_multiple_configs_validated(self) -> None:
        """Base + site-specific configs are all validated."""
        bad_site_config = SiteRolesConfig(
            {
                "bad role name!": Role(
                    display_name="Bad",
                    permissions=frozenset(),
                ),
            }
        )

        def mock_get_config(site_name: str | None = None) -> SiteRolesConfig:
            if site_name == "bad_site":
                return bad_site_config
            return get_role_config.__wrapped__(site_name)

        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.get_role_config",
                side_effect=mock_get_config,
            ),
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions._get_permissions_modules",
                return_value={"bad_site": "some.module"},
            ),
            pytest.raises(CommandError, match="bad role name!"),
        ):
            _call_validate()


# ============================================================
# Helpers
# ============================================================


def _call_sync(*args: str) -> str:
    """Call sync_role_permissions and return stdout."""
    from io import StringIO

    out = StringIO()
    call_command("sync_role_permissions", *args, stdout=out)
    return out.getvalue()


def _call_validate(*args: str) -> str:
    """Call validate_role_permissions and return stdout."""
    from io import StringIO

    out = StringIO()
    call_command("validate_role_permissions", *args, stdout=out)
    return out.getvalue()
