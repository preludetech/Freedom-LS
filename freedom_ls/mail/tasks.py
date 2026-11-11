"""The queued send: what the background worker runs for each message.

The task carries only the id of an ``OutboundEmail`` row. ``fls_run_worker``
claims the row, rebuilds the message from its payload and sends it through
EMAIL_UPSTREAM_BACKEND, which is what actually talks to the mail server. Dev
settings select the queueing backend; production sends in the request unless a
deployment opts in, because choosing it commits that deployment to running a
worker. Without one the mail is accepted and never sent.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.core.mail import get_connection
from django.db.models import F
from django.tasks import TaskResult, task
from django.utils import timezone

from freedom_ls.mail.config import config
from freedom_ls.mail.encoding import set_8bit_encoding
from freedom_ls.mail.errors import (
    SendErrorKind,
    classify_send_error,
    describe_error,
    report_outbound_email,
)
from freedom_ls.mail.models import LAST_ERROR_MAX_LENGTH, OutboundEmail
from freedom_ls.mail.serialisation import SerialisedMessage, deserialise_message

# Ahead of the default 0 that webhook delivery and report rendering enqueue at.
# django-tasks-db orders its queue by priority descending, so a person waiting on
# a password reset is not stuck behind a cohort report that happened to be asked
# for first. It does not preempt a report already running -- see the deployment
# docs for the separate-worker escape hatch.
EMAIL_TASK_PRIORITY = 10

Status = OutboundEmail.Status

PERMANENT_FAILURE_MESSAGE = (
    "An outgoing email failed permanently and will not be retried."
)


def send_serialised_email(payload: SerialisedMessage) -> None:
    """Rebuild a queued message and send it through the upstream backend.

    Failures propagate rather than being swallowed. The worker marks the task
    result FAILED and the task framework's own task_finished receiver logs that
    at ERROR with the traceback attached, which reaches the console handler and,
    where a DSN is configured, Sentry. Swallowing here would instead mark the
    task successful and drop the mail with no signal anywhere.
    """
    message = deserialise_message(payload)
    set_8bit_encoding(message)
    connection = get_connection(backend=config.EMAIL_UPSTREAM_BACKEND)
    connection.send_messages([message])


@task(priority=EMAIL_TASK_PRIORITY)
def _send_email_task(email_id: str) -> None:
    send_outbound_email(email_id)


def enqueue_send(email_id: UUID, run_after: datetime | None = None) -> TaskResult:
    """Enqueue one attempt at sending a row, optionally not before run_after.

    The task carries the row id and nothing else, so no copy of the message
    body is written to the task table.
    """
    task_to_run = _send_email_task
    if run_after is not None:
        task_to_run = task_to_run.using(run_after=run_after)
    return task_to_run.enqueue(str(email_id))


def send_outbound_email(email_id: str) -> None:
    """Claim one row and send it.

    A permanent failure ends the row. Any other error propagates, leaving it
    sending.
    """
    now = timezone.now()
    # One UPDATE is the whole guard: a second worker and a redelivered task can
    # race for the row and exactly one wins. The due-time filter stops a stray
    # task sending before the row is due.
    claimed = OutboundEmail.objects.filter(
        pk=email_id,
        status__in=(Status.PENDING, Status.FAILED),
        next_attempt_at__lte=now,
    ).update(
        status=Status.SENDING,
        attempt_count=F("attempt_count") + 1,
        last_attempt_at=now,
    )
    if not claimed:
        return
    email = OutboundEmail.objects.get(pk=email_id)
    try:
        send_serialised_email(email.payload)
    # Every exception is caught because the classifier is what decides, and it
    # needs to see them all. An unclassified one is re-raised untouched.
    except Exception as exc:
        if classify_send_error(exc) is SendErrorKind.PERMANENT:
            email.status = Status.PERMANENT_FAILURE
            email.last_error = describe_error(exc)
            email.save(update_fields=["status", "last_error"])
            report_outbound_email(email, PERMANENT_FAILURE_MESSAGE)
            return
        # The row stays in sending. A bug in our own code is reported loudly by
        # the failed task, not retried quietly. The cause is kept on the row so
        # the admin shows why once housekeeping moves it on.
        OutboundEmail.objects.filter(pk=email.pk).update(
            last_error=describe_error(exc)[:LAST_ERROR_MAX_LENGTH]
        )
        raise
    # Nothing runs between the send and this write: a crash here re-sends the
    # message, so the window is kept as small as one statement.
    sent_at = timezone.now()
    email.status = Status.SENT
    email.sent_at = sent_at
    email.payload = {}
    email.scrubbed_at = sent_at
    email.last_error = ""
    email.save(
        update_fields=["status", "sent_at", "payload", "scrubbed_at", "last_error"]
    )
