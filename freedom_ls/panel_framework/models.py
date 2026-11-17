"""The one record the framework keeps: a bulk action applied to a snapshot of
rows, for a host of any kind."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import Model
from django.db.models.base import ModelBase
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from freedom_ls.panel_framework.sites import resolve_site

__all__ = [
    "BulkActionRun",
    "RunStatus",
    "scope_lookup",
]


class RunStatus(models.TextChoices):
    """The lifecycle of a unit of work that may outlive the request that
    started it."""

    QUEUED = "queued", _("Queued")
    RUNNING = "running", _("Running")
    DONE = "done", _("Done")
    FAILED = "failed", _("Failed")


class BulkActionRunQuerySet(models.QuerySet["BulkActionRun"]):
    def for_site(self, site_id: int) -> BulkActionRunQuerySet:
        return self.filter(site_id=site_id)

    def for_request(self, request: HttpRequest) -> BulkActionRunQuerySet:
        """The runs of the request's site. A request the host resolves to no
        Site row sees no runs, rather than every site's."""
        site = resolve_site(request)
        return self.none() if site is None else self.for_site(site.pk)


class BulkActionRun(models.Model):
    """One bulk action applied to a snapshot of keys, and what it did.

    A run belongs to one site, named when it is created. `objects` is not
    filtered by site: a caller scopes a read with `for_request` or
    `for_site`, and a worker or sweep with no request reads by the site id it
    was given.

    `scope` is whatever object the host's section config scopes its requests
    to (an organisation, a workspace, a tenant), or nothing: the framework
    never names the host's models, so the run points at its scope generically
    and the host filters runs the same way. `action_path` is the dotted path
    of the action class, so a worker process can rebuild the action from the
    row alone, without the host having registered anything first. `keys` is
    the list of primary keys resolved when the action was confirmed, so the
    run acts on exactly the rows the reader was shown even if the table
    changes while it runs. `target` holds the action's parameters as JSON
    (for example the cohort a learner is added to). `result` is a
    `BulkResult` as JSON, set when the run finishes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    scope_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    # Open-set, like ObjectRoleAssignment.object_id (docs/app_conventions.md):
    # a host scopes its tables to models of its own choosing, so the primary
    # key type cannot be pinned in advance.
    scope_id = models.CharField(max_length=255, blank=True, default="")
    scope = GenericForeignKey("scope_type", "scope_id")
    action_path = models.CharField(max_length=255)
    table_key = models.CharField(max_length=100)
    action_name = models.CharField(max_length=100)
    target = models.JSONField(default=dict, blank=True)
    keys = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.QUEUED,
        db_index=True,
    )
    processed_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Unfiltered: a caller scopes a read with for_request or for_site.
    objects = BulkActionRunQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["scope_type", "scope_id"])]

    def __str__(self) -> str:
        return f"{self.table_key} {self.action_name} ({self.status})"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        # Assigning `scope = None` nulls the id; an unscoped run stores the
        # empty string instead, which is what `scope_lookup(None)` matches.
        if not self.scope_id:
            self.scope_id = ""
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


def scope_lookup(scope: Model | None) -> dict[str, object]:
    """Filter arguments matching runs recorded under `scope`, or under no
    scope at all when it is None."""
    if scope is None:
        return {"scope_type__isnull": True, "scope_id": ""}
    return {
        "scope_type": ContentType.objects.get_for_model(scope),
        "scope_id": str(scope.pk),
    }
