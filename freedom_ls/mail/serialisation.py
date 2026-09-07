"""Reduce an outgoing message to primitives, and rebuild it from them.

The task queue stores its arguments as JSON, so a message has to be reduced to
primitives before it can be enqueued. That reduction is also what discards the
bound ``message`` patch ``set_8bit_encoding`` installs, which is why the worker
reapplies it after rebuilding rather than relying on the sender having done it.
"""

from __future__ import annotations

import base64
from email.message import MIMEPart
from email.mime.base import MIMEBase
from typing import TypedDict

from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import EmailAttachment, EmailMessage


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
