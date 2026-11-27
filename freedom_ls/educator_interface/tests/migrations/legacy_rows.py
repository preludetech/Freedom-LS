"""One row per installed model that points at `ContentType`, built to point at a given
content type. The migration tests use these to prove which rows a content type delete
removes and which it leaves in place."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import models
from django.utils import timezone
from guardian.models import GroupObjectPermission, UserObjectPermission

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment


@dataclass(frozen=True)
class Built:
    """The model and primary key of a row a builder made."""

    model: type[models.Model]
    pk: object

    def exists(self) -> bool:
        return self.model._base_manager.filter(pk=self.pk).exists()


def _other_permission() -> Permission:
    return Permission.objects.exclude(
        content_type__app_label="freedom_ls_panel_framework"
    )[0]


def permission(ct: ContentType) -> Built:
    row = Permission.objects.create(
        codename="legacy_perm", name="Legacy", content_type=ct
    )
    return Built(Permission, row.pk)


def user_object_permission(ct: ContentType) -> Built:
    # `bulk_create`: guardian's `save()` looks up the object the content type names.
    row = UserObjectPermission.objects.bulk_create(
        [
            UserObjectPermission(
                user=UserFactory(),
                permission=_other_permission(),
                content_type=ct,
                object_pk="1",
            )
        ]
    )[0]
    return Built(UserObjectPermission, row.pk)


def group_object_permission(ct: ContentType) -> Built:
    row = GroupObjectPermission.objects.bulk_create(
        [
            GroupObjectPermission(
                group=Group.objects.create(name="legacy-group"),
                permission=_other_permission(),
                content_type=ct,
                object_pk="1",
            )
        ]
    )[0]
    return Built(GroupObjectPermission, row.pk)


def collection_item_by_collection(ct: ContentType) -> Built:
    row = ContentCollectionItem.objects.create(
        collection_type=ct,
        collection_id=uuid.uuid4(),
        child_type=_other_permission().content_type,
        child_id=uuid.uuid4(),
    )
    return Built(ContentCollectionItem, row.pk)


def collection_item_by_child(ct: ContentType) -> Built:
    row = ContentCollectionItem.objects.create(
        collection_type=_other_permission().content_type,
        collection_id=uuid.uuid4(),
        child_type=ct,
        child_id=uuid.uuid4(),
    )
    return Built(ContentCollectionItem, row.pk)


def conversion(ct: ContentType) -> Built:
    # Looked up by label: importing the model would add a dependency on an app this
    # one has no other reason to import.
    Conversion = apps.get_model("freedom_ls_referral_tracking", "Conversion")
    row = Conversion.objects.create(
        user=UserFactory(),
        kind="account_signup",
        content_type=ct,
        object_id="1",
        occurred_at=timezone.now(),
        window_days=30,
    )
    return Built(Conversion, row.pk)


def object_role_assignment(ct: ContentType) -> Built:
    # `bulk_create`: a post-save signal looks up the object the content type names.
    # `bulk_create` skips the `save()` that fills in the site, so the site is set here.
    row = ObjectRoleAssignment.objects.bulk_create(
        [
            ObjectRoleAssignment(
                site=Site.objects.get_current(),
                user=UserFactory(),
                content_type=ct,
                object_id="1",
                role="legacy",
            )
        ]
    )[0]
    return Built(ObjectRoleAssignment, row.pk)


def notification(ct: ContentType) -> Built:
    row = Notification.objects.create(
        user=UserFactory(),
        category="legacy",
        content_type=ct,
        object_id="1",
    )
    return Built(Notification, row.pk)


def log_entry(ct: ContentType) -> Built:
    row = LogEntry.objects.create(
        user=UserFactory(),
        content_type=ct,
        object_id="1",
        object_repr="legacy",
        action_flag=ADDITION,
    )
    return Built(LogEntry, row.pk)


def audit_log_entry(ct: ContentType) -> Built:
    row = AuditLogEntryFactory(target_content_type=ct)
    return Built(AuditLogEntry, row.pk)


# Models whose `on_delete` removes the row with its content type.
CASCADING: dict[str, Callable[[ContentType], Built]] = {
    "guardian.UserObjectPermission": user_object_permission,
    "guardian.GroupObjectPermission": group_object_permission,
    "content_engine.ContentCollectionItem.collection_type": collection_item_by_collection,
    "content_engine.ContentCollectionItem.child_type": collection_item_by_child,
    "referral_tracking.Conversion": conversion,
    "role_based_permissions.ObjectRoleAssignment": object_role_assignment,
    "comms.Notification": notification,
}
