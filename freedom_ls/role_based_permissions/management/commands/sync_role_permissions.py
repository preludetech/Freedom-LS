"""Management command to sync guardian permissions with role assignments."""

from argparse import ArgumentParser

from guardian.models import UserObjectPermission

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from freedom_ls.accounts.models import User
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import (
    ObjectRoleAssignment,
    SiteRoleAssignment,
    SystemRoleAssignment,
)
from freedom_ls.role_based_permissions.types import SiteRolesConfig
from freedom_ls.role_based_permissions.utils import sync_user_object_permissions


class Command(BaseCommand):
    help = "Sync guardian permissions with role assignments and detect drift."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing.",
        )
        parser.add_argument(
            "--report-orphans",
            action="store_true",
            help="Detect guardian perms with no matching role assignment.",
        )

    def handle(self, *args: object, **options: object) -> None:
        dry_run = bool(options["dry_run"])
        report_orphans = bool(options["report_orphans"])
        config = get_role_config()

        # Phase 1: Ensure permission objects exist
        self._ensure_permissions_exist(config)

        # Phase 2: Sync ObjectRoleAssignments
        drifted = 0
        drifted += self._sync_object_assignments(config, dry_run)

        # Phase 3: Sync SiteRoleAssignments
        drifted += self._sync_site_assignments(config, dry_run)

        # Phase 4: Validate SystemRoleAssignments
        self._validate_system_assignments(config)

        # Phase 5: Report orphans
        if report_orphans:
            orphan_count = self._report_orphans(config)
            self.stdout.write(f"Found {orphan_count} orphan permission(s).")

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(f"{prefix}{drifted} drifted assignment(s) found.")

    def _ensure_permissions_exist(self, config: SiteRolesConfig) -> None:
        """Ensure all permissions in config exist in auth_permission table."""
        for perm_string in config.all_permission_strings():
            app_label, codename = perm_string.split(".", 1)

            # Check if permission already exists for this app_label + codename
            exists = Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).exists()
            if exists:
                continue

            # Need to create it - get a ContentType for this app_label
            ct = ContentType.objects.filter(app_label=app_label).first()
            if ct is None:
                self.stderr.write(
                    f"Warning: No ContentType for app_label '{app_label}', "
                    f"skipping permission '{perm_string}'."
                )
                continue
            Permission.objects.create(
                content_type=ct,
                codename=codename,
                name=f"Can {codename}",
            )

    def _sync_object_assignments(self, config: SiteRolesConfig, dry_run: bool) -> int:
        """Sync guardian perms for all active ObjectRoleAssignments. Returns drift count."""
        drifted = 0
        # Group by (user, content_type, object_id) to sync once per user+object pair
        pairs_seen: set[tuple[int, int, str]] = set()

        for assignment in ObjectRoleAssignment.objects.filter(
            is_active=True
        ).select_related("user", "content_type"):
            pair_key = (
                assignment.user_id,
                assignment.content_type_id,
                assignment.object_id,
            )
            if pair_key in pairs_seen:
                continue
            pairs_seen.add(pair_key)

            # Resolve the target object
            model_class = assignment.content_type.model_class()
            if model_class is None:
                continue
            try:
                obj = model_class._default_manager.get(pk=assignment.object_id)
            except model_class.DoesNotExist:
                self.stderr.write(
                    f"Warning: Target object "
                    f"{assignment.content_type}:{assignment.object_id} "
                    f"not found, skipping."
                )
                continue

            result = sync_user_object_permissions(assignment.user, obj, dry_run=dry_run)
            if result["added"] or result["removed"]:
                drifted += 1

        return drifted

    def _sync_site_assignments(self, config: SiteRolesConfig, dry_run: bool) -> int:
        """Sync guardian perms for all active SiteRoleAssignments. Returns drift count."""
        drifted = 0
        pairs_seen: set[tuple[int, int]] = set()

        for assignment in SiteRoleAssignment.objects.filter(
            is_active=True
        ).select_related("user", "site"):
            pair_key = (assignment.user_id, assignment.site_id)
            if pair_key in pairs_seen:
                continue
            pairs_seen.add(pair_key)

            result = sync_user_object_permissions(
                assignment.user, assignment.site, dry_run=dry_run
            )
            if result["added"] or result["removed"]:
                drifted += 1

        return drifted

    def _validate_system_assignments(self, config: SiteRolesConfig) -> None:
        """Validate that all active SystemRoleAssignments have roles in config."""
        for assignment in SystemRoleAssignment.objects.filter(
            is_active=True
        ).select_related("user"):
            if assignment.role not in config:
                self.stderr.write(
                    f"Warning: SystemRoleAssignment for user {assignment.user} "
                    f"has unknown role '{assignment.role}'."
                )

    def _report_orphans(self, config: SiteRolesConfig) -> int:
        """Scan UserObjectPermission for rows not traceable to any active role assignment."""
        orphan_count = 0

        for uop in UserObjectPermission.objects.select_related(
            "permission__content_type", "user"
        ).all():
            perm_string = (
                f"{uop.permission.content_type.app_label}.{uop.permission.codename}"
            )
            user = uop.user
            ct = uop.content_type
            object_pk = uop.object_pk

            # Check if any active ObjectRoleAssignment matches
            if self._perm_traceable_to_object_role(
                config, user, ct, object_pk, perm_string
            ):
                continue

            # Check if any active SiteRoleAssignment matches (for Site objects)
            if self._perm_traceable_to_site_role(
                config, user, ct, object_pk, perm_string
            ):
                continue

            orphan_count += 1
            self.stdout.write(
                f"  Orphan: user={user}, perm={perm_string}, object={ct}:{object_pk}"
            )

        return orphan_count

    def _perm_traceable_to_object_role(
        self,
        config: SiteRolesConfig,
        user: User,
        ct: ContentType,
        object_pk: str,
        perm_string: str,
    ) -> bool:
        """Check if a guardian perm is traceable to an active ObjectRoleAssignment."""
        assignments = ObjectRoleAssignment.objects.filter(
            user=user,
            content_type=ct,
            object_id=object_pk,
            is_active=True,
        )
        for assignment in assignments:
            if (
                assignment.role in config
                and perm_string in config[assignment.role].permissions
            ):
                return True
        return False

    def _perm_traceable_to_site_role(
        self,
        config: SiteRolesConfig,
        user: User,
        ct: ContentType,
        object_pk: str,
        perm_string: str,
    ) -> bool:
        """Check if a guardian perm is traceable to an active SiteRoleAssignment."""
        site_ct = ContentType.objects.get_for_model(Site)
        if ct != site_ct:
            return False

        try:
            site_id = int(object_pk)
        except (ValueError, TypeError):
            return False

        assignments = SiteRoleAssignment.objects.filter(
            user=user,
            site_id=site_id,
            is_active=True,
        )
        for assignment in assignments:
            if (
                assignment.role in config
                and perm_string in config[assignment.role].permissions
            ):
                return True
        return False
