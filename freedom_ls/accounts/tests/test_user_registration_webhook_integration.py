"""Integration test: user registration should create a webhook event end-to-end."""

from unittest.mock import patch

import pytest

from django.contrib.sites.models import SITE_CACHE, Site
from django.test import Client
from django.urls import reverse

from freedom_ls.webhooks.models import WebhookEvent


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestUserRegistrationCreatesWebhookEvent:
    """End-to-end test: signing up via the view should create a user.registered WebhookEvent."""

    def test_signup_creates_user_registered_webhook_event(self) -> None:
        """POST to the signup URL should create a WebhookEvent with type 'user.registered'."""
        site = Site.objects.get_or_create(
            name="TestSite", defaults={"domain": "testserver"}
        )[0]
        # Ensure SITE_CACHE maps testserver to our site (Django test client uses testserver)
        SITE_CACHE.clear()
        SITE_CACHE["testserver"] = site

        try:
            assert WebhookEvent.objects.count() == 0

            client = Client()
            # Mock attempt_delivery so we don't make real HTTP requests
            with patch("freedom_ls.webhooks.events.attempt_delivery"):
                response = client.post(
                    reverse("account_signup"),
                    {
                        "email": "integration-test@example.com",  # pragma: allowlist secret
                        "password1": "TestPass123!xyz",  # pragma: allowlist secret
                        "password2": "TestPass123!xyz",  # pragma: allowlist secret
                        "first_name": "Integration",
                        "last_name": "Test",
                    },
                )

            # Signup should redirect (302) on success
            assert response.status_code == 302, (
                f"Expected redirect after signup, got {response.status_code}: "
                f"{response.content[:500].decode() if response.status_code != 302 else ''}"
            )

            # A user.registered WebhookEvent should have been created
            events = list(WebhookEvent.objects.filter(event_type="user.registered"))
            assert len(events) == 1, (
                f"Expected 1 user.registered event, found {len(events)}. "
                f"All events: {list(WebhookEvent.objects.values_list('event_type', flat=True))}"
            )
            event = events[0]
            assert event.payload["user_email"] == "integration-test@example.com"
            assert event.site_id == site.pk
        finally:
            SITE_CACHE.clear()
