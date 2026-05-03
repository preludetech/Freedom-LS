"""Tests for AccountAdapter."""

from unittest.mock import patch

import pytest
from allauth.core.context import request_context

from django.core import mail
from django.test import RequestFactory

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import UserFactory


@pytest.mark.django_db
def test_send_notification_mail_adds_user_to_context(mock_site_context: object) -> None:
    """send_notification_mail should add `user` to the context dict before delegating."""
    user = UserFactory()
    adapter = AccountAdapter()
    context: dict[str, object] = {"some_key": "some_value"}

    # Patch the upstream allauth method (system boundary — we don't want
    # allauth resolving a real email template / sending mail).
    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, context)

    forwarded_context = mock_super.call_args.args[2]
    assert forwarded_context["user"] is user
    assert forwarded_context["some_key"] == "some_value"


@pytest.mark.django_db
def test_send_notification_mail_creates_context_if_none(
    mock_site_context: object,
) -> None:
    """When no context is passed, one is created with the user populated."""
    user = UserFactory()
    adapter = AccountAdapter()

    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, None)

    forwarded_context = mock_super.call_args.args[2]
    assert forwarded_context["user"] is user


def _body_parts(mime_msg: object) -> list:
    """Return the text/plain and text/html parts of a MIME message."""
    return [
        part
        for part in mime_msg.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]


@pytest.fixture
def long_url_email(mock_site_context):
    """Send an allauth password-reset email containing a long URL.

    Returns ``(long_url, body_parts)`` so individual tests can assert on
    one property of the rendered MIME parts at a time.
    """
    user = UserFactory()
    adapter = AccountAdapter()

    long_url = "http://testsite/account/password/reset/key/" + "a" * 80 + "/"
    context = {"password_reset_url": long_url, "user": user}

    request = RequestFactory().get("/")
    with request_context(request):
        adapter.send_mail("account/email/password_reset_key", user.email, context)

    assert len(mail.outbox) == 1
    return long_url, _body_parts(mail.outbox[0].message())


@pytest.mark.django_db
def test_send_mail_emits_at_least_one_body_part(long_url_email) -> None:
    _, parts = long_url_email
    assert parts, "expected at least one text/plain or text/html body part"


@pytest.mark.django_db
@pytest.mark.parametrize("soft_break", ["=\n", "=\r\n"])
def test_send_mail_avoids_quoted_printable_line_wrapping(
    long_url_email, soft_break: str
) -> None:
    """Quoted-printable wraps lines >76 chars with =\\n, which corrupts URLs."""
    _, parts = long_url_email
    payloads = [part.get_payload() for part in parts]
    assert all(soft_break not in payload for payload in payloads)


@pytest.mark.django_db
def test_send_mail_preserves_long_url_in_body(long_url_email) -> None:
    long_url, parts = long_url_email
    payloads = [part.get_payload() for part in parts]
    assert all(long_url in payload for payload in payloads)


@pytest.mark.django_db
def test_send_mail_uses_8bit_transfer_encoding(long_url_email) -> None:
    _, parts = long_url_email
    encodings = [part["Content-Transfer-Encoding"] for part in parts]
    assert all(encoding == "8bit" for encoding in encodings)
