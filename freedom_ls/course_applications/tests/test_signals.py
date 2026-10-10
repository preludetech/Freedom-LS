"""Tests for the receivers that claim a browser's applications on login."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import EmailAddressFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import UNCLAIMED_APPLICATIONS_SESSION_KEY
from freedom_ls.course_applications.factories import CourseApplicationFactory

if TYPE_CHECKING:
    # Stub-only: the test client's response type.
    from django.test.client import _MonkeyPatchedWSGIResponse


def _hold(client: Client, *pks: object) -> None:
    session = client.session
    session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = [str(pk) for pk in pks]
    session.save()


def _log_in(client: Client, user: User) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        reverse("account_login"), {"login": user.email, "password": user.email}
    )


@pytest.mark.django_db
class TestClaimOnLogin:
    def test_claim_runs_on_login(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user)
        app = CourseApplicationFactory(unclaimed=True, email=user.email)
        client = Client()
        _hold(client, app.pk)

        _log_in(client, user)

        app.refresh_from_db()
        assert app.user == user

    def test_receiver_no_ops_without_ids(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user)
        client = Client()

        with patch(
            "freedom_ls.course_applications.signals.claim_unclaimed_applications"
        ) as claim:
            _log_in(client, user)

        claim.assert_not_called()

    def test_claim_database_error_does_not_break_login(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user)
        app = CourseApplicationFactory(unclaimed=True, email=user.email)
        client = Client()
        _hold(client, app.pk)

        with patch(
            "django.db.models.query.QuerySet.select_for_update",
            side_effect=DatabaseError("down"),
        ):
            response = _log_in(client, user)

        assert response.status_code == 302
        assert "_auth_user_id" in client.session

    def test_claim_database_error_is_reported(self, mock_site_context):
        user = UserFactory()
        EmailAddressFactory(user=user)
        app = CourseApplicationFactory(unclaimed=True, email=user.email)
        client = Client()
        _hold(client, app.pk)
        error = DatabaseError("down")

        with (
            patch(
                "django.db.models.query.QuerySet.select_for_update",
                side_effect=error,
            ),
            patch("freedom_ls.course_applications.signals.sentry_sdk") as sentry,
        ):
            _log_in(client, user)

        sentry.capture_exception.assert_called_once_with(error)


def _sign_up_and_confirm(
    client: Client, email: str, next_url: str, follow: bool
) -> _MonkeyPatchedWSGIResponse:
    client.post(
        reverse("account_signup"),
        {
            "email": email,
            "password1": "TestPass123!xyz",  # pragma: allowlist secret
            "password2": "TestPass123!xyz",  # pragma: allowlist secret
            "first_name": "Signup",
            "last_name": "Applicant",
            "accept_terms": "on",
            "accept_privacy": "on",
            "next": next_url,
        },
    )
    confirmation = EmailConfirmationHMAC(EmailAddress.objects.get(email=email))
    return client.post(
        reverse("account_confirm_email", args=[confirmation.key]), follow=follow
    )


@pytest.mark.django_db(transaction=True)
class TestClaimOnSignup:
    def test_claim_runs_on_login_on_email_confirmation_in_same_browser(
        self, mock_site_context
    ):
        email = "applicant@example.com"
        app = CourseApplicationFactory(unclaimed=True, email=email)
        client = Client()
        _hold(client, app.pk)

        _sign_up_and_confirm(
            client, email, reverse("course_applications:claim"), follow=False
        )

        app.refresh_from_db()
        assert app.user == User.objects.get(email=email)

    def test_signup_confirmation_round_trip_lands_on_the_status_page(
        self, mock_site_context
    ):
        email = "round-trip@example.com"
        app = CourseApplicationFactory(unclaimed=True, email=email)
        client = Client()
        _hold(client, app.pk)

        confirmed = _sign_up_and_confirm(
            client, email, reverse("course_applications:claim"), follow=True
        )

        app.refresh_from_db()
        assert app.user is not None
        assert confirmed.redirect_chain[-1][0] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
