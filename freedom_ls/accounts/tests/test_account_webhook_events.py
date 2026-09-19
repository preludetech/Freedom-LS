"""Tests for webhook events fired from the accounts app."""

from unittest.mock import patch

import pytest

from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import UserFactory


def _request_with_session() -> HttpRequest:
    request = RequestFactory().post("/accounts/signup/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


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
            result = adapter.save_user(
                _request_with_session(), user, mock_form, commit=True
            )

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
            adapter.save_user(_request_with_session(), user, mock_form, commit=False)

        mock_fire.assert_not_called()


@pytest.mark.django_db(transaction=True)
class TestSignUpGoogleAnalyticsEvent:
    def test_save_user_records_the_sign_up_event_on_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()
        mock_form = mocker.Mock()
        request = _request_with_session()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(request, user, mock_form, commit=True)

        assert request.session["google_analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]

    def test_save_user_does_not_record_the_event_without_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()
        mock_form = mocker.Mock()
        request = _request_with_session()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(request, user, mock_form, commit=False)

        assert "google_analytics_events" not in request.session


@pytest.mark.django_db(transaction=True)
class TestSignUpGoogleAnalyticsEventEndToEnd:
    def test_signing_up_emits_the_sign_up_event_on_the_landing_page(
        self, mock_site_context: object
    ) -> None:
        """`save_user` runs before allauth touches the session, and mandatory
        email verification defers login, so the event recorded during signup must
        survive allauth's own redirect chain to the page the new user lands
        on. Guards against a later allauth upgrade changing that chain.
        """
        with (
            override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST"),
            patch("freedom_ls.webhooks.events.attempt_delivery"),
        ):
            response = Client().post(
                reverse("account_signup"),
                {
                    "email": "ga-signup-test@example.com",  # pragma: allowlist secret
                    "password1": "TestPass123!xyz",  # pragma: allowlist secret
                    "password2": "TestPass123!xyz",  # pragma: allowlist secret
                    "first_name": "Ga",
                    "last_name": "Test",
                    "accept_terms": "on",
                    "accept_privacy": "on",
                },
                follow=True,
            )

        assert (
            """gtag('event', 'sign_up', {"method": "email"})"""
            in response.content.decode()
        )
