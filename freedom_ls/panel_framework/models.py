"""The one record the framework keeps: a bulk action applied to a snapshot of
rows, for a host of any kind."""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Model
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import SiteAwareModel


class RunStatus(models.TextChoices):
    """The lifecycle of a unit of work that may outlive the request that
    started it."""

    QUEUED = "queued", _("Queued")
    RUNNING = "running", _("Running")
    DONE = "done", _("Done")
    FAILED = "failed", _("Failed")


class BulkActionRun(SiteAwareModel):
    """One bulk action applied to a snapshot of keys, and what it did.

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

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["scope_type", "scope_id"])]

    def __str__(self) -> str:
        return f"{self.table_key} {self.action_name} ({self.status})"

    def save(self, *args: object, **kwargs: object) -> None:
        # Assigning `scope = None` nulls the id; an unscoped run stores the
        # empty string instead, which is what `scope_lookup(None)` matches.
        if not self.scope_id:
            self.scope_id = ""
        super().save(*args, **kwargs)


def scope_lookup(scope: Model | None) -> dict[str, object]:
    """Filter arguments matching runs recorded under `scope`, or under no
    scope at all when it is None."""
    if scope is None:
        return {"scope_type__isnull": True, "scope_id": ""}
    return {
        "scope_type": ContentType.objects.get_for_model(scope),
        "scope_id": str(scope.pk),
    }
