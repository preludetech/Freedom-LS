"""Tests for the sync_role_permissions management command."""

from collections.abc import Generator
from contextlib import redirect_stdout
from io import StringIO

import pytest
from guardian.models import GroupObjectPermission, UserObjectPermission
from guardian.shortcuts import assign_perm

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.role_based_permissions.factories import ObjectRoleAssignmentFactory
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    """Clear the loader and permission caches between tests."""
    clear_caches()
    yield
    clear_caches()


@pytest.fixture(autouse=True)
def _site_context(mock_site_context: Site) -> None:
    """Every test here builds site-aware objects and assigns roles."""


class TestSyncRolePermissionsNoAssignments:
    """Test sync command with no assignments."""

    @pytest.mark.django_db
    def test_runs_cleanly_reports_zero_drift(self) -> None:
        """Sync with no assignments runs cleanly and reports 0 drift."""
        out = _call_sync()
        assert "0 drifted assignment(s) found." in out


class TestSyncRolePermissionsDetectsAndFixesDrift:
    """Test sync command detects and fixes drift."""

    @pytest.mark.django_db
    def test_detects_and_fixes_drift(self) -> None:
        """Manually added guardian perm is removed by sync command."""
        user = UserFactory()
        cohort = CohortFactory()

        # Create an active role assignment for 'cohort_viewer' (has view_cohort)
        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_viewer", is_active=True
        )

        # Manually add a guardian perm that the role shouldn't have
        assign_perm("freedom_ls_learner_management.add_cohort", user, cohort)

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
        assert "1 drifted assignment(s) found." in out


class TestSyncRolePermissionsDryRun:
    """Test sync command with --dry-run."""

    @pytest.mark.django_db
    def test_dry_run_reports_drift_but_no_changes(self) -> None:
        """--dry-run reports drift without changing guardian state."""
        user = UserFactory()
        cohort = CohortFactory()

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_viewer", is_active=True
        )

        # Manually add an extra guardian perm
        assign_perm("freedom_ls_learner_management.add_cohort", user, cohort)

        out = _call_sync("--dry-run")

        # The extra perm should still exist (dry run doesn't change anything)
        assert UserObjectPermission.objects.filter(
            user=user,
            permission__codename="add_cohort",
            content_type=ContentType.objects.get_for_model(cohort),
            object_pk=str(cohort.pk),
        ).exists()

        # Should still report drift
        assert "[DRY RUN] 1 drifted assignment(s) found." in out


class TestSyncRolePermissionsOrphanedAssignment:
    """Test sync command handles orphaned assignments (target object deleted)."""

    @pytest.mark.django_db
    def test_handles_orphaned_target_object(self) -> None:
        """Sync handles assignments where the target object has been deleted."""
        user = UserFactory()
        cohort = CohortFactory()
        ct = ContentType.objects.get_for_model(cohort)

        ObjectRoleAssignmentFactory(
            user=user, target_object=cohort, role="cohort_viewer", is_active=True
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
        assert "0 drifted assignment(s) found." in out


class TestSyncRolePermissionsReportOrphans:
    """Test --report-orphans detects manually-granted guardian permissions."""

    @pytest.mark.django_db
    def test_report_orphans_detects_manual_guardian_perms(self) -> None:
        """--report-orphans detects guardian perms not traceable to any active role."""
        user = UserFactory()
        cohort = CohortFactory()

        # Manually grant a guardian perm with no role assignment
        assign_perm("freedom_ls_learner_management.add_cohort", user, cohort)

        out = _call_sync("--report-orphans")

        assert "Found 1 orphan permission(s)." in out

    @pytest.mark.django_db
    def test_report_orphans_detects_group_object_permissions(self) -> None:
        """--report-orphans detects GroupObjectPermission rows as orphans."""
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="test-group")
        cohort = CohortFactory()

        assign_perm("freedom_ls_learner_management.add_cohort", group, cohort)

        assert GroupObjectPermission.objects.count() == 1

        out = _call_sync("--report-orphans")

        assert "Found 1 orphan permission(s)." in out
        assert "group=test-group" in out


def _call_sync(*args: str) -> str:
    """Call sync_role_permissions and return stdout."""
    out = StringIO()
    with redirect_stdout(out):
        call_command("sync_role_permissions", *args)
    return out.getvalue()
