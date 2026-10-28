from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Field, Index, QuerySet
from django.db.models.deletion import Collector
from django.utils import timezone
from django.utils.functional import cached_property

from freedom_ls.audit_log.actions import AuditAction, get_audit_action
from freedom_ls.audit_log.exceptions import AppendOnlyError
from freedom_ls.site_aware_models.models import SiteAwareManager, SiteAwareModel

REASON_LENGTH = 500


def set_null_by_instance(
    collector: Collector, field: Field, sub_objs: QuerySet[AuditLogEntry], using: str
) -> None:
    """SET_NULL for the actor FK. Django's own hands the collector a queryset,
    which it nulls through `QuerySet.update()`; the instances go through
    `sql.UpdateQuery` instead, so `update()` below can refuse every call. The
    `actor_label` column keeps the entry readable afterwards."""
    collector.add_field_update(field, None, list(sub_objs.only("pk")))


class AuditLogEntryQuerySet(models.QuerySet["AuditLogEntry"]):
    """`create()` and `bulk_create()` work; every call that would change or
    remove existing rows raises."""

    def update(self, **kwargs: object) -> int:
        raise AppendOnlyError()

    def delete(self) -> tuple[int, dict[str, int]]:
        raise AppendOnlyError()

    def prune_before(self, cutoff: datetime, *, batch_size: int = 1000) -> int:
        """The only delete path. Deletes rows created before `cutoff` in
        batches so a long-retained table never locks in one statement."""
        total = 0
        while True:
            batch = list(
                self.filter(created_at__lt=cutoff).values_list("pk", flat=True)[
                    :batch_size
                ]
            )
            if not batch:
                return total
            total += self._delete_batch(batch)

    def _delete_batch(self, pks: list[UUID]) -> int:
        # The base delete, since this class's own refuses.
        deleted, _ = models.QuerySet.delete(self.filter(pk__in=pks))
        return deleted

    def bulk_update(
        self,
        objs: Iterable[AuditLogEntry],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise AppendOnlyError()


class AuditLogEntry(SiteAwareModel):
    """One audited change: who did what to which object, and when.

    The `*_label` fields keep reading correctly after the actor or the target
    is gone. They are copied from other models' fields, so they carry no
    length of their own: a user's display name alone runs to 401 characters.
    """

    created_at = models.DateTimeField(default=timezone.now)
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        null=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=set_null_by_instance,
        related_name="+",
    )
    actor_label = models.CharField(blank=True)
    action = models.CharField(max_length=100)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="+"
    )
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")
    target_label = models.CharField()
    subjects = ArrayField(models.CharField(max_length=300))
    reason = models.CharField(max_length=REASON_LENGTH, blank=True)
    details = models.JSONField(default=dict, blank=True)
    run_id = models.UUIDField(null=True, blank=True)

    objects = SiteAwareManager.from_queryset(AuditLogEntryQuerySet)()
    unscoped = AuditLogEntryQuerySet.as_manager()

    class Meta:
        # Django's own internals read through the base manager; naming the
        # unscoped one makes them carry the append-only guards too.
        base_manager_name = "unscoped"
        ordering = ("-created_at", "-id")
        verbose_name_plural = "audit log entries"
        indexes = [
            Index(fields=["organisation", "-created_at"]),
            # The Who filter lists the actors on an organisation's entries.
            Index(fields=["organisation", "actor"]),
            Index(fields=["run_id"]),
            GinIndex(fields=["subjects"]),
        ]

    def __str__(self) -> str:
        return f"{self.action}: {self.target_label}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise AppendOnlyError()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise AppendOnlyError()

    @cached_property
    def audit_action(self) -> AuditAction:
        return get_audit_action(self.action)

    @property
    def label(self) -> str:
        return self.audit_action.label

    @property
    def description(self) -> str:
        describe = self.audit_action.describe
        return describe(self) if describe else ""
