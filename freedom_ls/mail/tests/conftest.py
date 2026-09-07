"""Shared fixtures and message builders for the mail app's tests.

The helpers are public rather than underscore-prefixed because they cross module
boundaries: the same message shape is what serialisation, the worker send and the
backend are all tested against.
"""

from __future__ import annotations

from collections.abc import Sequence
from email.message import MIMEPart

import pytest
import pytest_django.fixtures

from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
REFUSING = "freedom_ls.mail.tests.conftest.RefusingEmailBackend"
LONG_URL = "https://example.test/account/password/reset/key/" + "a" * 80 + "/"


class RefusingEmailBackend(BaseEmailBackend):
    """A mail host that is not listening, reached by dotted path.

    ``get_connection()`` imports the backend it is given, so a double that stands
    in for a dead SMTP server has to be importable rather than a local object.
    """

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise ConnectionRefusedError("mail host is not listening")


@pytest.fixture
def upstream_locmem(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Send through locmem, so mail.outbox is the record of what went out.

    Django forces EMAIL_BACKEND to locmem under test; this points the backend
    *behind* the queue at it too, so nothing reaches for a real socket.
    """
    settings.EMAIL_UPSTREAM_BACKEND = LOCMEM


def make_message() -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject="Reset your password",
        body=f"Follow this link: {LONG_URL}",
        from_email="noreply@example.test",
        to=["learner@example.test"],
        cc=["educator@example.test"],
        bcc=["audit@example.test"],
        reply_to=["support@example.test"],
        headers={"X-Tenant": "example"},
    )
    message.attach_alternative(f'<a href="{LONG_URL}">Reset</a>', "text/html")
    return message


def body_parts(mime_msg: object) -> list:
    return [
        part
        for part in mime_msg.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]


def raw_attachment_part() -> MIMEPart:
    """A raw MIME attachment built the way a caller would really build one.

    Carries a content type, an encoding and a disposition -- exactly three
    headers, which is what a bare part set up in a test does not have.
    """
    part = MIMEPart()
    part.set_content(
        b"%PDF-1.4 \x00\x01\x02",
        maintype="application",
        subtype="pdf",
        disposition="attachment",
        filename="report.pdf",
    )
    return part
