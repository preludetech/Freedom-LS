"""Queue outgoing email onto the background worker.

Pointing EMAIL_BACKEND here makes every ``send()`` in the project return as soon
as the message is on the queue rather than blocking the request on an SMTP round
trip.

How much the queue can promise depends on the task backend behind it. A durable
backend hands the message to a worker and the request learns nothing more. An
inline one -- what dev and the test suite run -- has already attempted the send
by the time the task is enqueued, so the outcome is read from the row and
reported.

Each message is written to an ``OutboundEmail`` row first, and the task carries
only that row's id.

No call site changes to make this work: ``EmailMessage.send()`` resolves its
connection through ``get_connection()``, so pinning the setting catches every
sender, allauth's transactional mail included.
"""

from __future__ import annotations

from collections.abc import Sequence
from email.utils import make_msgid

from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage
from django.core.mail.utils import DNS_NAME
from django.db import DatabaseError, transaction
from django.tasks import TaskResult
from django.utils import timezone

from freedom_ls.mail.config import config
from freedom_ls.mail.encoding import set_8bit_encoding
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import UnserialisableMessageError, serialise_message
from freedom_ls.mail.tasks import enqueue_send


class QueuedEmailNotSentError(Exception):
    """A queued send was attempted and failed before the request returned."""


class QueuedEmailBackend(BaseEmailBackend):
    """Put each message on the task queue instead of sending it in-process."""

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        return sum(1 for message in email_messages if self._queue_or_send(message))

    def _queue_or_send(self, message: EmailMessage) -> bool:
        # Mirrors the SMTP backend, which declines to open a connection for a
        # message addressed to nobody.
        if not message.recipients():
            return False

        # Django mints a fresh Message-ID each time a message is rendered, so
        # every retry would look like a new message. Pinning it lets a mail
        # client collapse a duplicate delivery. Done before serialising so the
        # payload carries it.
        message_id = _pin_message_id(message)

        try:
            payload = serialise_message(message)
        except UnserialisableMessageError:
            # Sendable, just not expressible as JSON. Paying the SMTP latency
            # here beats dropping the message, and FLS's own mail never reaches
            # this path.
            return self._send_now(message)

        try:
            email = OutboundEmail.objects.create(
                message_id=message_id,
                recipients=message.recipients(),
                subject=str(message.subject),
                payload=payload,
                next_attempt_at=timezone.now(),
            )
        except DatabaseError:
            # The queue is the database, so this means the database is down, in
            # which case whatever triggered the mail has already failed -- there
            # is no account for a verification link to confirm. Deliberately not
            # falling back to an inline send, which would deliver a link to a row
            # that was never written. Raising leaves the caller as badly off as it
            # is today when SMTP fails, which is the right amount.
            if not self.fail_silently:
                raise
            return False

        # Read before registering: outside a transaction on_commit runs the
        # callback at once, and afterwards there is no telling which case this
        # was.
        in_transaction = transaction.get_connection().in_atomic_block
        results: list[TaskResult] = []

        def enqueue() -> None:
            results.append(enqueue_send(email.pk))

        # robust=True: an enqueue that fails after the commit must not fail the
        # request that already committed. The row stays pending for a later
        # attempt.
        transaction.on_commit(enqueue, robust=True)

        if in_transaction or not results or not results[0].is_finished:
            return True
        # An inline task backend has already attempted the send. Reporting a
        # failed attempt as a message sent would leave the caller telling someone
        # to check an inbox nothing is on its way to.
        email.refresh_from_db(fields=["status", "last_error"])
        if email.status == OutboundEmail.Status.SENT:
            return True
        if not self.fail_silently:
            raise QueuedEmailNotSentError(_failure_detail(email, results[0]))
        return False

    def _send_now(self, message: EmailMessage) -> bool:
        """Send through the upstream backend, bypassing the queue."""
        set_8bit_encoding(message)
        connection = get_connection(
            backend=config.EMAIL_UPSTREAM_BACKEND,
            fail_silently=self.fail_silently,
        )
        return bool(connection.send_messages([message]))


def _pin_message_id(message: EmailMessage) -> str:
    """Return the message's Message-ID, minting one when the caller set none."""
    # Header names are case-insensitive, so a caller's "Message-Id" counts.
    # Adding a second spelling would send two Message-ID headers.
    for name, value in message.extra_headers.items():
        if name.lower() == "message-id":
            return str(value)
    message_id = make_msgid(domain=DNS_NAME)
    message.extra_headers["Message-ID"] = message_id
    return message_id


def _failure_detail(email: OutboundEmail, result: TaskResult) -> str:
    """Describe a failed attempt, keeping the worker's traceback when it has one.

    The exception instance itself does not survive the task framework -- only its
    class path and formatted traceback do -- so there is nothing to chain from.
    """
    if result.errors:
        return "\n".join(
            f"{error.exception_class_path}\n{error.traceback}"
            for error in result.errors
        )
    return email.last_error or "the queued send failed with no error recorded"
