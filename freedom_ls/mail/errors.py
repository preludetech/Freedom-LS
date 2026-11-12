"""Deciding whether a failed send is worth another attempt.

One blind spot: smtplib.sendmail raises only when every recipient is refused,
so a message some recipients refused is recorded as sent and not retried. A
retry would send a second copy to the recipients who accepted the first.

A header-injection error is not listed as permanent. Django 6 raises it as a
plain ValueError (BadHeaderError is now an alias of ValueError), which is
indistinguishable from a bug in our own code and is treated as one.
"""

from __future__ import annotations

import ssl
from enum import StrEnum
from smtplib import (
    SMTPAuthenticationError,
    SMTPException,
    SMTPNotSupportedError,
    SMTPRecipientsRefused,
)
from typing import TYPE_CHECKING

import sentry_sdk

if TYPE_CHECKING:
    from freedom_ls.mail.models import OutboundEmail


class SendErrorKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"


class UpstreamSendCountZeroError(Exception):
    """The upstream backend raised nothing and reported no message sent."""


def classify_send_error(exc: BaseException) -> SendErrorKind | None:
    if _is_permanent(exc):
        return SendErrorKind.PERMANENT
    if _is_transient(exc):
        return SendErrorKind.TRANSIENT
    return None


def _smtp_code(exc: BaseException) -> int | None:
    code = getattr(exc, "smtp_code", None)
    return code if isinstance(code, int) else None


def _is_permanent(exc: BaseException) -> bool:
    # Bad credentials are permanent whatever the code: retrying them across a
    # backlog gets the sending account locked.
    if isinstance(
        exc,
        (
            SMTPAuthenticationError,
            SMTPNotSupportedError,
            ssl.SSLCertVerificationError,
            UnicodeEncodeError,
        ),
    ):
        return True
    if isinstance(exc, SMTPRecipientsRefused):
        # One 4xx among them is worth a retry: the recipient refused only for
        # now gets the message on the next attempt.
        codes = [code for code, _ in exc.recipients.values()]
        return bool(codes) and all(500 <= code <= 599 for code in codes)
    code = _smtp_code(exc)
    return code is not None and 500 <= code <= 599


def _is_transient(exc: BaseException) -> bool:
    # Every SMTPException is an OSError, and so is each socket and TLS error
    # worth retrying. Permanent cases are ruled out before this runs.
    code = _smtp_code(exc)
    if code is not None and 400 <= code <= 499:
        return True
    return isinstance(exc, (OSError, SMTPException, UpstreamSendCountZeroError))


def describe_error(exc: BaseException) -> str:
    """'<exception class path>: <message>', the text stored in last_error."""
    cls = type(exc)
    return f"{cls.__module__}.{cls.__qualname__}: {exc}"


def report_outbound_email(email: OutboundEmail, message: str) -> None:
    """Send Sentry a constant message about one row.

    Only the row id, attempt count and status go on the scope. Exception text
    from smtplib can carry recipient addresses, so it is never attached, and a
    constant message groups every such row into one issue.
    """
    with sentry_sdk.new_scope() as scope:
        scope.set_extra("outbound_email_id", str(email.pk))
        scope.set_extra("attempt_count", email.attempt_count)
        scope.set_extra("status", email.status)
        sentry_sdk.capture_message(message)
