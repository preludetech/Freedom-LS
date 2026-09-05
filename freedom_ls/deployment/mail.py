"""Queue outgoing email onto the background worker.

Both settings modules point EMAIL_BACKEND here, so every ``send()`` in the
project returns as soon as the message is on the queue rather than blocking the
request on an SMTP round trip. ``fls_run_worker`` rebuilds the message and sends
it through EMAIL_UPSTREAM_BACKEND, which is what actually talks to the mail
server. A deployment that runs no worker sets EMAIL_BACKEND back to Django's SMTP
backend; otherwise its mail would be accepted and never sent.

No call site changes to make this work: ``EmailMessage.send()`` resolves its
connection through ``get_connection()``, so pinning the setting catches every
sender, allauth's transactional mail included.

The task queue stores its arguments as JSON, so a message has to be reduced to
primitives. That reduction is also what discards the bound ``message`` patch
``set_8bit_encoding`` installs, which is why the worker reapplies it after
rebuilding rather than relying on the sender having done it.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from email.message import MIMEPart
from email.mime.base import MIMEBase
from typing import TypedDict

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailAttachment, EmailMessage
from django.db import DatabaseError
from django.tasks import default_task_backend, task

from freedom_ls.base.email_encoding import set_8bit_encoding
from freedom_ls.deployment.config import config

# Ahead of the default 0 that webhook delivery and report rendering enqueue at.
# django-tasks-db orders its queue by priority descending, so a person waiting on
# a password reset is not stuck behind a cohort report that happened to be asked
# for first. It does not preempt a report already running -- see the deployment
# docs for the separate-worker escape hatch.
EMAIL_TASK_PRIORITY = 10


class UnserialisableMessageError(Exception):
    """Raised when a message holds something a JSON task payload cannot carry."""


class SerialisedAlternative(TypedDict):
    content: str
    mimetype: str


class SerialisedAttachment(TypedDict):
    filename: str | None
    content: str
    mimetype: str | None
    # Django keeps a text/* attachment's content as str and everything else as
    # bytes. Both travel base64-encoded, so this records which to decode back to.
    text: bool


class SerialisedMessage(TypedDict):
    subject: str
    body: str
    from_email: str
    to: list[str]
    cc: list[str]
    bcc: list[str]
    reply_to: list[str]
    extra_headers: dict[str, str]
    content_subtype: str
    alternatives: list[SerialisedAlternative]
    attachments: list[SerialisedAttachment]


def _serialise_attachment(
    attachment: EmailAttachment | MIMEPart | MIMEBase,
) -> SerialisedAttachment:
    """Reduce one attachment to base64, or refuse it.

    ``attach()`` puts a live MIMEPart or MIMEBase on the list when handed one,
    and neither has a ``(filename, content, mimetype)`` form to reduce. Caught by
    type: both iterate over their header names, so unpacking one succeeds
    whenever it carries three headers -- which a real attachment part, with a
    content type, an encoding and a disposition, does. Nothing in FLS attaches
    anything to an email today; this guards a future caller against silently
    losing its attachment.
    """
    if isinstance(attachment, MIMEPart | MIMEBase):
        raise UnserialisableMessageError(
            f"{type(attachment).__name__} attachments have no JSON representation."
        )
    # A caller appending to `attachments` by hand rather than through attach().
    try:
        filename, content, mimetype = attachment
    except (TypeError, ValueError) as exc:
        raise UnserialisableMessageError(
            f"{type(attachment).__name__} attachments have no JSON representation."
        ) from exc
    if isinstance(content, str):
        raw, is_text = content.encode(), True
    elif isinstance(content, bytes):
        raw, is_text = content, False
    else:
        raise UnserialisableMessageError(
            f"An attachment whose content is {type(content).__name__} has no "
            f"JSON representation."
        )
    return {
        "filename": filename,
        "content": base64.b64encode(raw).decode("ascii"),
        "mimetype": mimetype,
        "text": is_text,
    }


def serialise_message(message: EmailMessage) -> SerialisedMessage:
    """Reduce an EmailMessage to the JSON-safe payload the task carries."""
    alternatives: list[SerialisedAlternative] = []
    if isinstance(message, EmailMultiAlternatives):
        # Unpacked rather than read by attribute: Django 6 stores EmailAlternative
        # namedtuples here, but a caller appending a plain 2-tuple is still valid.
        alternatives = [
            {"content": str(content), "mimetype": str(mimetype)}
            for content, mimetype in message.alternatives
        ]

    return {
        # str() because a lazy translation is not JSON-serialisable.
        "subject": str(message.subject),
        "body": str(message.body),
        "from_email": str(message.from_email),
        "to": [str(address) for address in message.to],
        "cc": [str(address) for address in message.cc],
        "bcc": [str(address) for address in message.bcc],
        "reply_to": [str(address) for address in message.reply_to],
        "extra_headers": {
            name: str(value) for name, value in message.extra_headers.items()
        },
        "content_subtype": message.content_subtype,
        "alternatives": alternatives,
        "attachments": [
            _serialise_attachment(attachment) for attachment in message.attachments
        ],
    }


def deserialise_message(payload: SerialisedMessage) -> EmailMultiAlternatives:
    """Rebuild the message a worker is to send from its queued payload."""
    message = EmailMultiAlternatives(
        subject=payload["subject"],
        body=payload["body"],
        from_email=payload["from_email"],
        to=payload["to"],
        cc=payload["cc"],
        bcc=payload["bcc"],
        reply_to=payload["reply_to"],
        headers=payload["extra_headers"],
        alternatives=[
            (alternative["content"], alternative["mimetype"])
            for alternative in payload["alternatives"]
        ],
    )
    message.content_subtype = payload["content_subtype"]
    for attachment in payload["attachments"]:
        raw = base64.b64decode(attachment["content"])
        message.attach(
            attachment["filename"],
            raw.decode() if attachment["text"] else raw,
            attachment["mimetype"],
        )
    return message


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
def _send_email_task(payload: SerialisedMessage) -> None:
    send_serialised_email(payload)


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
            default_task_backend.enqueue(_send_email_task, args=[payload], kwargs={})
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
        return True

    def _send_now(self, message: EmailMessage) -> bool:
        """Send through the upstream backend, bypassing the queue."""
        set_8bit_encoding(message)
        connection = get_connection(
            backend=config.EMAIL_UPSTREAM_BACKEND,
            fail_silently=self.fail_silently,
        )
        return bool(connection.send_messages([message]))
