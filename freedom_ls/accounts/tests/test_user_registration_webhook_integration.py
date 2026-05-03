"""Integration test: user registration should create a webhook event end-to-end."""

from unittest.mock import patch

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.webhooks.models import WebhookEvent


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
def test_signup_creates_user_registered_webhook_event(mock_site_context) -> None:
    """POST to the signup URL should create a WebhookEvent with type 'user.registered'."""
    assert WebhookEvent.objects.count() == 0

    # Mock attempt_delivery so we don't make real HTTP requests (system boundary).
    with patch("freedom_ls.webhooks.events.attempt_delivery"):
        response = Client().post(
            reverse("account_signup"),
            {
                "email": "integration-test@example.com",  # pragma: allowlist secret
                "password1": "TestPass123!xyz",  # pragma: allowlist secret
                "password2": "TestPass123!xyz",  # pragma: allowlist secret
                "first_name": "Integration",
                "last_name": "Test",
                "accept_terms": "on",
                "accept_privacy": "on",
            },
        )

    assert response.status_code == 302  # successful signup redirects

    events = list(WebhookEvent.objects.filter(event_type="user.registered"))
    assert len(events) == 1
    event = events[0]
    assert event.payload["user_email"] == "integration-test@example.com"
    assert event.site_id == mock_site_context.pk
