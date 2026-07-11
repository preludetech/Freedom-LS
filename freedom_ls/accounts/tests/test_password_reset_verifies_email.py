"""Tests: a completed keyed password reset must verify the reset email.

Drives allauth's real reset-request -> reset-from-key views end-to-end with
the Django test `Client`, extracting the keyed reset link from the rendered
email (`mail.outbox`, the locmem backend) rather than asserting on Mailpit.
"""

from __future__ import annotations

import re

import pytest
from allauth.account.models import EmailAddress

from django.core import mail
from django.http import HttpResponseBase
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import EmailAddressFactory, UserFactory

NEW_PASSWORD = "a-brand-new-p4ssw0rd!"  # noqa: S105  # pragma: allowlist secret


def _extract_reset_url(body: str) -> str:
    """Pull the keyed reset URL out of the rendered password-reset email body."""
    match = re.search(r"Reset Password: (\S+)", body)
    assert match, f"no reset URL found in email body:\n{body}"
    return match.group(1)


def _complete_password_reset(
    client: Client, user_email: str, new_password: str
) -> HttpResponseBase:
    """Drive a full keyed password reset through allauth's real views.

    Requests a reset, extracts the keyed link from the outgoing mail, follows
    allauth's key-in-session redirect, then submits the new password. Returns
    the final `form_valid` response (the one that runs the reset-triggered
    auto-login).
    """
    outbox_before = len(mail.outbox)
    response = client.post(
        reverse("account_reset_password"), {"email": user_email}, follow=False
    )
    assert response.status_code == 302
    assert len(mail.outbox) == outbox_before + 1

    reset_url = _extract_reset_url(mail.outbox[-1].body)

    # First GET stores the real key in the session and redirects to a
    # key-free URL (allauth avoids leaking the key via the Referer header).
    response = client.get(reset_url, follow=False)
    assert response.status_code == 302
    key_free_url = response["Location"]

    # GET the key-free URL to confirm the form renders (key resolved from session).
    response = client.get(key_free_url, follow=False)
    assert response.status_code == 200

    return client.post(
        key_free_url,
        {"password1": new_password, "password2": new_password},
        follow=False,
    )


@pytest.mark.django_db
def test_unverified_account_completes_reset_verifies_email_and_logs_in(
    mock_site_context,
):
    user = UserFactory()
    EmailAddressFactory(user=user, email=user.email, verified=False)
    client = Client()

    response = _complete_password_reset(client, user.email, NEW_PASSWORD)

    assert response.status_code == 302
    assert (
        EmailAddress.objects.get(user=user, email__iexact=user.email).verified is True
    )

    profile_response = client.get(reverse("accounts:account_profile"))
    assert profile_response.status_code == 200


@pytest.mark.django_db
def test_account_with_no_email_address_row_completes_reset_creates_verified_row_and_logs_in(
    mock_site_context,
):
    user = UserFactory()
    client = Client()

    response = _complete_password_reset(client, user.email, NEW_PASSWORD)

    assert response.status_code == 302
    assert (
        EmailAddress.objects.get(user=user, email__iexact=user.email).verified is True
    )

    profile_response = client.get(reverse("accounts:account_profile"))
    assert profile_response.status_code == 200


@pytest.mark.django_db
def test_already_verified_account_completes_reset_stays_verified_and_logged_in(
    mock_site_context,
):
    user = UserFactory()
    EmailAddressFactory(user=user, email=user.email, verified=True)
    client = Client()

    response = _complete_password_reset(client, user.email, NEW_PASSWORD)

    assert response.status_code == 302
    assert (
        EmailAddress.objects.get(user=user, email__iexact=user.email).verified is True
    )

    profile_response = client.get(reverse("accounts:account_profile"))
    assert profile_response.status_code == 200


@pytest.mark.django_db
def test_unverified_account_normal_login_is_still_blocked_by_email_verification(
    mock_site_context,
):
    """Resetting is the only new way an unverified account gets verified.

    An ordinary login attempt (no reset involved) for an unverified
    pre-existing account must still be blocked by mandatory verification.
    """
    user = UserFactory()
    EmailAddressFactory(user=user, email=user.email, verified=False)
    client = Client()

    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": user.email},
        follow=False,
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("account_email_verification_sent")

    profile_response = client.get(reverse("accounts:account_profile"), follow=False)
    assert profile_response.status_code == 302
    assert profile_response["Location"].startswith(reverse("account_login"))
