"""Sweeps that keep outgoing email moving when the normal path let a row down."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from freedom_ls.mail.config import config
from freedom_ls.mail.errors import report_outbound_email
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.tasks import enqueue_send

Status = OutboundEmail.Status

TERMINAL_STATUSES = (Status.SENT, Status.PERMANENT_FAILURE, Status.DEAD_LETTER)

STUCK_LAST_ERROR = "The worker sending this email stopped before it finished."
STUCK_MESSAGE = (
    "An outgoing email was left in sending by a worker that did not finish it."
)


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


def recover_stuck_outbound_email() -> list[OutboundEmail]:
    """Re-drive rows a dead worker left in sending. Returns the rows dead-lettered.

    This is the one place a killed task's work is run again, so the message may be
    delivered twice: the worker may have handed it to the mail host just before it
    died. The pinned Message-ID lets a mail client collapse the duplicate.
    """
    now = timezone.now()
    cutoff = now - timedelta(seconds=config.HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS)
    dead_lettered: list[OutboundEmail] = []
    stuck = OutboundEmail.objects.filter(
        status=Status.SENDING, last_attempt_at__lt=cutoff
    )
    for email in stuck:
        out_of_attempts = email.attempt_count >= config.EMAIL_MAX_ATTEMPTS
        new_status = Status.DEAD_LETTER if out_of_attempts else Status.FAILED
        # Conditional on the attempt this run saw, so a row a worker finished
        # or re-claimed since the query is left to that worker.
        moved = OutboundEmail.objects.filter(
            pk=email.pk, status=Status.SENDING, last_attempt_at=email.last_attempt_at
        ).update(
            status=new_status,
            next_attempt_at=now,
            # A row whose task died without recording a cause still says
            # something in the admin.
            last_error=email.last_error or STUCK_LAST_ERROR,
        )
        if not moved:
            continue
        email.status = new_status
        report_outbound_email(email, STUCK_MESSAGE)
        if out_of_attempts:
            dead_lettered.append(email)
        else:
            enqueue_send(email.pk)
    return dead_lettered


def prune_outbound_email() -> None:
    """Delete finished rows past retention and drop the body of old failed ones."""
    now = timezone.now()
    OutboundEmail.objects.filter(
        status__in=TERMINAL_STATUSES,
        created_at__lt=now - timedelta(days=config.EMAIL_OUTBOUND_RETENTION_DAYS),
    ).delete()
    # Measured from the last attempt, not from creation, so a row an admin
    # resent keeps its body for the full window after it fails again.
    OutboundEmail.objects.filter(
        status__in=(Status.PERMANENT_FAILURE, Status.DEAD_LETTER),
        scrubbed_at__isnull=True,
        last_attempt_at__lt=now
        - timedelta(days=config.EMAIL_FAILED_PAYLOAD_RETENTION_DAYS),
    ).update(payload={}, scrubbed_at=now)
