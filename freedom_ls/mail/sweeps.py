"""Sweeps that keep outgoing email moving when the normal path let a row down."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from freedom_ls.mail.config import config
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.tasks import enqueue_send

Status = OutboundEmail.Status


def requeue_due_outbound_email() -> int:
    """Enqueue a send for each row that is overdue. Returns how many.

    Never sends: the worker does that. Covers a failed on-commit enqueue, a task
    backend that cannot defer, and a deferred task that was lost.
    """
    now = timezone.now()
    cutoff = now - timedelta(seconds=config.HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS)
    overdue = OutboundEmail.objects.filter(
        status__in=(Status.PENDING, Status.FAILED), next_attempt_at__lt=cutoff
    )
    due_ids = list(
        overdue.order_by("next_attempt_at").values_list("pk", flat=True)[
            : config.HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE
        ]
    )
    requeued = 0
    for email_id in due_ids:
        # One transaction per row: an enqueue that fails rolls the due time
        # back, so the row is still overdue on the next run.
        with transaction.atomic():
            # Moving the due time to now takes the row out of the next run's
            # match, so a run made while the worker is down does not stack a
            # second task behind the first.
            if overdue.filter(pk=email_id).update(next_attempt_at=now):
                enqueue_send(email_id)
                requeued += 1
    return requeued
