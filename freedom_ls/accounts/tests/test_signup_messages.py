"""Test that signup + email-confirmation flow surfaces Django messages as toasts.

Allauth ships templates for `account/messages/email_confirmation_sent.txt`
and `account/messages/email_confirmed.txt` and calls `add_message` from
its email-verification flow. This test guards that those messages reach
the toast live regions on the post-signup and post-confirm landing pages.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from django.test import Client
from django.urls import reverse


def _assert_toast_body(html: str, region_id: str, expected_text: str) -> None:
    """Assert the response renders a toast in the named region containing `expected_text`."""
    region_marker = f'id="{region_id}"'
    assert region_marker in html, f"region {region_id} missing from response"
    region_start = html.find(region_marker)
    # Take a generous slice — the toast container is the next ~4kB.
    region_slice = html[region_start : region_start + 8000]
    assert '<div id="toast-' in region_slice, (
        f"no toast node in region {region_id}; slice: {region_slice[:500]!r}"
    )
    assert expected_text in region_slice, (
        f"expected '{expected_text}' in toast region {region_id}; slice: {region_slice!r}"
    )


@pytest.mark.django_db(transaction=True)
def test_signup_renders_email_confirmation_toast(mock_site_context) -> None:
    """Post-signup landing page should render an info toast in the polite region."""
    client = Client()
    response = client.post(
        reverse("account_signup"),
        {
            "email": "msg-signup@example.com",  # pragma: allowlist secret
            "password1": "TestPass123!xyz",  # pragma: allowlist secret
            "password2": "TestPass123!xyz",  # pragma: allowlist secret
            "first_name": "Msg",
            "last_name": "Test",
            "accept_terms": "on",
            "accept_privacy": "on",
        },
        follow=True,
    )

    assert response.status_code == 200
    _assert_toast_body(
        response.content.decode(),
        "toast-region-polite",
        "msg-signup@example.com",
    )


@pytest.mark.django_db(transaction=True)
def test_email_confirmation_renders_success_toast(mock_site_context) -> None:
    """Post-confirm landing page should render a success toast in the polite region."""
    client = Client()
    client.post(
        reverse("account_signup"),
        {
            "email": "msg-confirm@example.com",  # pragma: allowlist secret
            "password1": "TestPass123!xyz",  # pragma: allowlist secret
            "password2": "TestPass123!xyz",  # pragma: allowlist secret
            "first_name": "Msg",
            "last_name": "Confirm",
            "accept_terms": "on",
            "accept_privacy": "on",
        },
    )

    email_address = EmailAddress.objects.get(email="msg-confirm@example.com")
    key = EmailConfirmationHMAC(email_address).key
    confirm_url = reverse("account_confirm_email", args=[key])

    response = client.post(confirm_url, follow=True)

    assert response.status_code == 200
    _assert_toast_body(
        response.content.decode(),
        "toast-region-polite",
        "msg-confirm@example.com",
    )
