"""Tests for deciding whether a failed send is worth another attempt."""

from __future__ import annotations

import socket
import ssl
from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPDataError,
    SMTPException,
    SMTPHeloError,
    SMTPNotSupportedError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)

import pytest

from freedom_ls.mail.errors import (
    SendErrorKind,
    UpstreamSendCountZeroError,
    classify_send_error,
    describe_error,
    report_outbound_email,
)
from freedom_ls.mail.factories import OutboundEmailFactory

PERMANENT = SendErrorKind.PERMANENT
TRANSIENT = SendErrorKind.TRANSIENT


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (SMTPAuthenticationError(535, b"bad credentials"), PERMANENT),
        (SMTPAuthenticationError(454, b"try later"), PERMANENT),
        (SMTPNotSupportedError("no AUTH"), PERMANENT),
        (SMTPDataError(550, b"rejected"), PERMANENT),
        (SMTPSenderRefused(553, b"bad sender", "a@example.test"), PERMANENT),
        (
            SMTPRecipientsRefused(
                {"a@example.test": (550, b"no"), "b@example.test": (551, b"no")}
            ),
            PERMANENT,
        ),
        (
            SMTPRecipientsRefused(
                {"a@example.test": (450, b"later"), "b@example.test": (550, b"no")}
            ),
            TRANSIENT,
        ),
        (ssl.SSLCertVerificationError("certificate verify failed"), PERMANENT),
        (UnicodeEncodeError("ascii", "é", 0, 1, "ordinal not in range"), PERMANENT),
        (SMTPServerDisconnected("connection lost"), TRANSIENT),
        (SMTPConnectError(421, b"busy"), TRANSIENT),
        (SMTPHeloError(421, b"busy"), TRANSIENT),
        (SMTPDataError(451, b"try later"), TRANSIENT),
        (SMTPSenderRefused(452, b"full", "a@example.test"), TRANSIENT),
        (SMTPRecipientsRefused({"a@example.test": (450, b"later")}), TRANSIENT),
        (TimeoutError(), TRANSIENT),
        (ConnectionRefusedError(), TRANSIENT),
        (ConnectionResetError(), TRANSIENT),
        (BrokenPipeError(), TRANSIENT),
        (socket.gaierror(-2, "name not known"), TRANSIENT),
        (ssl.SSLError("handshake failed"), TRANSIENT),
        (OSError("network unreachable"), TRANSIENT),
        (SMTPException("something odd"), TRANSIENT),
        (UpstreamSendCountZeroError(), TRANSIENT),
        (ValueError("our bug"), None),
        (KeyError("our bug"), None),
    ],
    ids=lambda value: (
        type(value).__name__ if isinstance(value, BaseException) else str(value)
    ),
)
def test_send_error_is_classified(
    exc: BaseException, expected: SendErrorKind | None
) -> None:
    assert classify_send_error(exc) is expected


def test_describe_error_gives_class_path_and_message() -> None:
    assert describe_error(ConnectionRefusedError("nope")) == (
        "builtins.ConnectionRefusedError: nope"
    )


@pytest.mark.django_db
def test_report_outbound_email_puts_only_the_row_facts_on_the_scope(
    sentry_events: list[dict],
) -> None:
    email = OutboundEmailFactory(attempt_count=2)

    report_outbound_email(email, "constant message")

    assert len(sentry_events) == 1
    assert sentry_events[0]["message"] == "constant message"
    assert sentry_events[0]["extra"] == {
        "outbound_email_id": str(email.pk),
        "attempt_count": 2,
        "status": email.status,
    }
