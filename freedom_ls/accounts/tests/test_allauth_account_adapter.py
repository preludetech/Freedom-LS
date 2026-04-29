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
    """send_notification_mail should add `user` to the context dict before calling super."""
    user = UserFactory()
    adapter = AccountAdapter()
    context: dict[str, str] = {"some_key": "some_value"}

    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, context)

    mock_super.assert_called_once_with("account/email/test", user, context, email=None)
    assert context["user"] is user


@pytest.mark.django_db
def test_send_notification_mail_creates_context_if_none(
    mock_site_context: object,
) -> None:
    """send_notification_mail should create a context dict if None is passed."""
    user = UserFactory()
    adapter = AccountAdapter()

    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, None)

    call_args = mock_super.call_args
    passed_context = call_args[0][2]
    assert passed_context["user"] is user


@pytest.mark.django_db
def test_send_mail_does_not_corrupt_long_urls(mock_site_context: object) -> None:
    """Long URLs in emails must not be broken by quoted-printable line wrapping."""
    user = UserFactory()
    adapter = AccountAdapter()

    long_url = "http://testsite/account/password/reset/key/" + "a" * 80 + "/"
    context = {"password_reset_url": long_url, "user": user}

    request = RequestFactory().get("/")
    with request_context(request):
        adapter.send_mail("account/email/password_reset_key", user.email, context)

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]

    # Check the raw MIME-serialized message for quoted-printable soft line breaks.
    # Quoted-printable encoding wraps lines >76 chars with "=\r\n" (or "=\n"),
    # which corrupts URLs when email clients reassemble the message.
    mime_msg = sent.message()
    for part in mime_msg.walk():
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        raw_payload = part.get_payload()
        assert "=\n" not in raw_payload, (
            f"{content_type} has quoted-printable line wrapping"
        )
        assert "=\r\n" not in raw_payload, (
            f"{content_type} has quoted-printable line wrapping"
        )
        assert long_url in raw_payload, f"Long URL is broken in {content_type}"
        cte = part["Content-Transfer-Encoding"]
        assert cte == "8bit", f"{content_type} uses {cte}, expected 8bit"
