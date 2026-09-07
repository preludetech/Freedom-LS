"""Queue outgoing email onto the background worker.

Pointing EMAIL_BACKEND here makes every ``send()`` in the project return as soon
as the message is on the queue rather than blocking the request on an SMTP round
trip.

How much the queue can promise depends on the task backend behind it. A durable
backend hands the message to a worker and the request learns nothing more. An
inline one -- what dev and the test suite run -- has already attempted the send
by the time ``enqueue()`` returns, so the outcome is in hand and reported.

No call site changes to make this work: ``EmailMessage.send()`` resolves its
connection through ``get_connection()``, so pinning the setting catches every
sender, allauth's transactional mail included.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage
from django.db import DatabaseError
from django.tasks import TaskResult, TaskResultStatus, default_task_backend

from freedom_ls.mail.config import config
from freedom_ls.mail.encoding import set_8bit_encoding
from freedom_ls.mail.serialisation import UnserialisableMessageError, serialise_message
from freedom_ls.mail.tasks import _send_email_task


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

        try:
            payload = serialise_message(message)
        except UnserialisableMessageError:
            # Sendable, just not expressible as JSON. Paying the SMTP latency
            # here beats dropping the message, and FLS's own mail never reaches
            # this path.
            return self._send_now(message)

        try:
            result = default_task_backend.enqueue(
                _send_email_task, args=[payload], kwargs={}
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

        # An inline task backend runs the send before enqueue() returns, and
        # records what went wrong on the result rather than raising it. Reporting
        # a refused connection as a message sent would leave the caller telling
        # someone to check an inbox nothing is on its way to. A durable backend
        # leaves the status READY, so production never takes this branch.
        if result.status == TaskResultStatus.FAILED:
            if not self.fail_silently:
                raise QueuedEmailNotSentError(_failure_detail(result))
            return False
        return True

    def _send_now(self, message: EmailMessage) -> bool:
        """Send through the upstream backend, bypassing the queue."""
        set_8bit_encoding(message)
        connection = get_connection(
            backend=config.EMAIL_UPSTREAM_BACKEND,
            fail_silently=self.fail_silently,
        )
        return bool(connection.send_messages([message]))


def _failure_detail(result: TaskResult) -> str:
    """Describe a failed task result, keeping the worker's traceback.

    The exception instance itself does not survive the task framework -- only its
    class path and formatted traceback do -- so there is nothing to chain from.
    """
    if not result.errors:
        return "the queued send failed with no error recorded"
    return "\n".join(
        f"{error.exception_class_path}\n{error.traceback}" for error in result.errors
    )
