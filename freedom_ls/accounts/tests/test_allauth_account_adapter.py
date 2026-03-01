"""Tests for AccountAdapter.send_notification_mail."""

from unittest.mock import patch

import pytest

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
def test_send_notification_mail_does_not_overwrite_existing_user(
    mock_site_context: object,
) -> None:
    """send_notification_mail should set user in context (overwriting is acceptable since it's the correct user)."""
    user = UserFactory()
    adapter = AccountAdapter()
    other_user = UserFactory()
    context: dict[str, object] = {"user": other_user}

    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, context)

    mock_super.assert_called_once()
    assert context["user"] is user
