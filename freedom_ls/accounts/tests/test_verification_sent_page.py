"""Tests for the "verification sent" screen (`account_email_verification_sent`).

Allauth routes new signups, existing-email signups, and cooldown-suppressed
resends all to this same screen. The copy must stay honest without leaking
which of those happened, and must give a stuck, unauthenticated user a
reachable way to try again.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_verification_sent_page_does_not_claim_a_verification_link_was_sent(
    mock_site_context,
) -> None:
    """The screen must not assert that a "verification link" was emailed.

    A caller on the existing-email/enumeration branch, or hitting the resend
    cooldown, receives no such link — claiming one was sent would be false
    for them, and the falseness would differ by branch (an enumeration leak).
    """
    client = Client()

    response = client.get(reverse("account_email_verification_sent"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "verification link" not in content.lower()
    assert "finalize the signup process" not in content.lower()


@pytest.mark.django_db
def test_verification_sent_page_links_to_password_reset_request(
    mock_site_context,
) -> None:
    """The screen must offer a reachable way forward: the reset-request page.

    Reusing `account_reset_password` (rather than a bespoke resend view) keeps
    the recovery entry point enumeration-safe by construction — it already
    shows the same confirmation regardless of whether the account exists.
    """
    client = Client()

    response = client.get(reverse("account_email_verification_sent"))

    content = response.content.decode()
    reset_url = reverse("account_reset_password")
    assert f'href="{reset_url}"' in content
