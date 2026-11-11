"""The row that owns one outgoing message from the moment it is written."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from django.db import models
from django.db.models.base import ModelBase

SUBJECT_MAX_LENGTH = 255
LAST_ERROR_MAX_LENGTH = 1000


class OutboundEmail(models.Model):
    """One outgoing message: its payload until sent, then its status and attempts.

    Not a SiteAwareModel: mail is sent by the process, not on behalf of a site,
    and the worker and housekeeping read rows with no site context. Not a
    TimestampedModel either, because its timestamps carry meaning (the last
    attempt, the send, the scrub) rather than recording row edits.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        SENDING = "sending"
        FAILED = "failed"
        SENT = "sent"
        PERMANENT_FAILURE = "permanent_failure"
        DEAD_LETTER = "dead_letter"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Not unique: a caller can send the same EmailMessage object twice.
    message_id = models.CharField(max_length=255, db_index=True)
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=SUBJECT_MAX_LENGTH)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    scrubbed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]

    def __str__(self) -> str:
        return f"{self.subject} ({self.status})"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.subject = self.subject[:SUBJECT_MAX_LENGTH]
        self.last_error = self.last_error[:LAST_ERROR_MAX_LENGTH]
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
