"""The retry ladder: when a failed send is attempted again, and when it is given up on."""

from __future__ import annotations

import random
from datetime import timedelta

from django.tasks import default_task_backend
from django.utils import timezone

from freedom_ls.mail.config import config
from freedom_ls.mail.errors import describe_error, report_outbound_email
from freedom_ls.mail.models import OutboundEmail

Status = OutboundEmail.Status

DEAD_LETTER_MESSAGE = (
    "An outgoing email ran out of send attempts and was dead-lettered."
)


def next_attempt_delay(attempt_count: int) -> timedelta:
    """How long to wait after the given attempt failed."""
    delays = config.EMAIL_RETRY_DELAYS
    base = delays[min(attempt_count - 1, len(delays) - 1)]
    # Jitter spreads a backlog that all failed in the same second, so the
    # retries do not arrive at the mail host as one burst.
    jitter = random.uniform(0, base * config.EMAIL_RETRY_JITTER_RATIO)  # noqa: S311
    return timedelta(seconds=base + jitter)


def schedule_retry(email: OutboundEmail, exc: BaseException) -> None:
    """Record a transient failure and arrange the next attempt, or dead-letter the row."""
    # Imported here because tasks imports this module.
    from freedom_ls.mail.tasks import enqueue_send

    email.last_error = describe_error(exc)
    if email.attempt_count >= config.EMAIL_MAX_ATTEMPTS:
        email.status = Status.DEAD_LETTER
        email.save(update_fields=["status", "last_error"])
        report_outbound_email(email, DEAD_LETTER_MESSAGE)
        return
    email.status = Status.FAILED
    email.next_attempt_at = timezone.now() + next_attempt_delay(email.attempt_count)
    email.save(update_fields=["status", "next_attempt_at", "last_error"])
    # A backend that cannot defer would run the next attempt at once, and an
    # inline one would walk the whole ladder inside the request. Housekeeping
    # drives the row instead.
    if default_task_backend.supports_defer:
        enqueue_send(email.pk, run_after=email.next_attempt_at)
