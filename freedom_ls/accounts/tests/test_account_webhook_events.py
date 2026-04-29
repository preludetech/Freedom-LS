"""Tests for webhook events fired from the accounts app."""

from unittest.mock import patch

import pytest

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import UserFactory


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestUserRegisteredWebhookEvent:
    def test_save_user_fires_webhook_event_on_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """When save_user is called with commit=True, fire_webhook_event is called."""
        mock_fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()

        mock_form = mocker.Mock()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ) as mock_super_save:
            result = adapter.save_user(mocker.Mock(), user, mock_form, commit=True)

        mock_super_save.assert_called_once()
        mock_fire.assert_called_once_with(
            "user.registered",
            {
                "user_id": user.pk,
                "user_email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )
        assert result is user

    def test_save_user_does_not_fire_webhook_without_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """When save_user is called with commit=False, no webhook event is fired."""
        mock_fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()

        mock_form = mocker.Mock()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(mocker.Mock(), user, mock_form, commit=False)

        mock_fire.assert_not_called()
