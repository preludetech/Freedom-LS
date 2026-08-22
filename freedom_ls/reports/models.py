from __future__ import annotations

from django.conf import settings
from django.core.files.storage import InvalidStorageError, Storage, storages
from django.db import models
from django.db.models import Q, UniqueConstraint

from freedom_ls.reports.config import config
from freedom_ls.site_aware_models.models import SiteAwareModel

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_READY = "ready"
STATUS_FAILED = "failed"

STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_RUNNING, "Running"),
    (STATUS_READY, "Ready"),
    (STATUS_FAILED, "Failed"),
]


def report_upload_path(instance: GeneratedReport, filename: str) -> str:
    """pk-derived, never the cohort name — a cohort name is guessable and enumerable.

    The pk is a uuid4, so it alone makes the name unique and every report can
    sit directly under `reports/`. Nothing user-facing reads this name:
    `download_report_view` names the download itself via Content-Disposition.
    """
    if not instance.pk:
        raise ValueError("Instance must be saved before uploading files")
    return f"reports/{instance.pk}-cohort-report.pdf"


def get_reports_storage() -> Storage:
    """The alias named by REPORTS_STORAGE_ALIAS, falling back to the default storage."""
    try:
        return storages[config.REPORTS_STORAGE_ALIAS]
    except InvalidStorageError:
        return storages["default"]


class GeneratedReport(SiteAwareModel):
    STATUS_PENDING = STATUS_PENDING
    STATUS_RUNNING = STATUS_RUNNING
    STATUS_READY = STATUS_READY
    STATUS_FAILED = STATUS_FAILED
    STATUS_CHOICES = STATUS_CHOICES

    cohort = models.ForeignKey(
        "freedom_ls_learner_management.Cohort",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        db_index=True,
        default=STATUS_PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    file = models.FileField(
        upload_to=report_upload_path, storage=get_reports_storage, blank=True
    )

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            UniqueConstraint(
                fields=["cohort"],
                condition=Q(status__in=[STATUS_PENDING, STATUS_RUNNING]),
                name="one_inflight_report_per_cohort",
            ),
        ]

    def __str__(self) -> str:
        # The delete-confirmation screens show only this string, so it has to
        # name the cohort an admin is about to destroy a report for -- and the
        # organisation with it, since cohort names are unique per organisation
        # rather than per site.
        return (
            f"Report for cohort {self.cohort.organisation} / {self.cohort} "
            f"({self.status})"
        )
