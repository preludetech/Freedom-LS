from __future__ import annotations

import posixpath

from django.conf import settings
from django.core.files.storage import InvalidStorageError, Storage, storages
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.db.models.signals import post_delete
from django.dispatch import receiver

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
    """pk-derived, never the cohort name — a cohort name is guessable and enumerable."""
    if not instance.pk:
        raise ValueError("Instance must be saved before uploading files")
    return f"reports/{instance.pk}/cohort-report.pdf"


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
        "freedom_ls_student_management.Cohort",
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
        # name the cohort an admin is about to destroy a report for.
        return f"Report for cohort {self.cohort} ({self.status})"


def _delete_empty_report_directory(
    storage: Storage, directory: str
) -> None:  # TODO why a directory?
    """Remove the per-report directory once its only file is gone.

    `report_upload_path` gives every report a directory of its own, so an
    emptied one is dead weight. Not every backend has directories: the base
    `Storage` API raises `NotImplementedError` for both `listdir` and `delete`,
    and object stores synthesise a prefix that disappears with its last key.
    Those and a concurrently removed directory are the only ways there can
    legitimately be nothing to remove, so they are the only failures swallowed
    here — anything else is a real storage fault and must surface.
    """
    if not directory:
        return
    try:
        subdirectories, files = storage.listdir(directory)
    except (NotImplementedError, FileNotFoundError):
        return
    if subdirectories or files:
        return
    try:
        storage.delete(directory)
    except NotImplementedError:
        return


@receiver(post_delete, sender=GeneratedReport)  # TODO signals should go in signals.py
def delete_report_file(
    sender: type[GeneratedReport], instance: GeneratedReport, **kwargs: object
) -> None:
    """Storage does not follow the row. An orphaned PDF is PII left behind.

    TODO: no retention/expiry policy exists yet for report files while their
    row is still alive — this only cleans up on delete. Do not remove this
    TODO without implementing retention.
    """
    if not instance.file:
        return
    # Read through a local: FieldFile.name is Optional, and the truthiness
    # check above narrows the FieldFile, not the name it carries.
    file_name = instance.file.name
    if not file_name:
        return
    directory = posixpath.dirname(file_name)
    storage = instance.file.storage
    instance.file.delete(save=False)
    _delete_empty_report_directory(storage, directory)
