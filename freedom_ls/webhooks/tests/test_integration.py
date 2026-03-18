import json
from unittest.mock import patch

import httpx
import pytest

from django.contrib.sites.models import Site

from freedom_ls.webhooks.events import dispatch_event
from freedom_ls.webhooks.factories import (
    WebhookEndpointFactory,
    WebhookEventFactory,
    WebhookSecretFactory,
)
from freedom_ls.webhooks.models import WebhookDelivery
from freedom_ls.webhooks.presets import WEBHOOK_PRESETS
from freedom_ls.webhooks.rendering import build_template_context


@pytest.mark.django_db
class TestBrevoPresetIntegration:
    """Full flow: Brevo preset endpoint fires event, delivery uses transformed format."""

    def test_brevo_preset_delivery_sends_transformed_payload(
        self, mock_site_context: Site
    ) -> None:
        site = mock_site_context
        preset = WEBHOOK_PRESETS["brevo-track-event"]

        # Create the MA key secret that Brevo track event template references
        WebhookSecretFactory(
            name="brevo_ma_key",
            encrypted_value="xkeysib-test-ma-key-123",
            site=site,
        )

        # Create endpoint configured with the Brevo preset
        endpoint = WebhookEndpointFactory(
            url=preset.default_url,
            event_types=["user.registered"],
            http_method=preset.http_method,
            content_type=preset.content_type,
            headers_template=preset.headers_template,
            body_template=preset.body_template,
            preset_slug=preset.slug,
            auth_type="none",
        )

        # Create the event
        event = WebhookEventFactory(
            event_type="user.registered",
            payload={
                "user_id": "abc-123",
                "user_email": "student@example.com",
            },
        )

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"success": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ) as mock_request:
            dispatch_event(str(event.pk), site.pk)

        # Verify a delivery was created and succeeded
        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery is not None
        assert delivery.status == "success"

        # Verify the HTTP request used the Brevo-transformed format
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs

        # Method should be POST (Brevo preset)
        assert call_kwargs["method"] == "POST"

        # URL should be the Brevo API endpoint
        assert call_kwargs["url"] == preset.default_url

        # Headers should include the Brevo MA key from secrets
        headers = call_kwargs["headers"]
        assert headers["ma-key"] == "xkeysib-test-ma-key-123"
        assert headers["accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

        # Body should be the Brevo-transformed payload
        body = json.loads(call_kwargs["content"])
        assert body["event"] == "user_registered"
        assert body["email"] == "student@example.com"
        assert body["properties"]["user_id"] == "abc-123"

        # auth_type=none means no HMAC headers
        assert "webhook-signature" not in headers

    def test_brevo_preset_delivery_missing_secret_fails(
        self, mock_site_context: Site
    ) -> None:
        """When the required brevo_api_key secret is missing, template rendering fails."""
        site = mock_site_context
        preset = WEBHOOK_PRESETS["brevo-track-event"]

        # No secret created -- template will fail on {{ secrets.brevo_api_key }}
        WebhookEndpointFactory(
            url=preset.default_url,
            event_types=["user.registered"],
            http_method=preset.http_method,
            content_type=preset.content_type,
            headers_template=preset.headers_template,
            body_template=preset.body_template,
            preset_slug=preset.slug,
            auth_type="none",
        )

        event = WebhookEventFactory(
            event_type="user.registered",
            payload={"user_id": "abc-123", "user_email": "test@example.com"},
        )

        with patch("freedom_ls.webhooks.delivery.httpx.request") as mock_request:
            dispatch_event(str(event.pk), site.pk)
            # No HTTP request should be made -- template rendering fails
            mock_request.assert_not_called()

        delivery = WebhookDelivery.objects.first()
        assert delivery is not None
        assert delivery.status == "permanent_failure"
        assert "brevo_ma_key" in delivery.last_response_error_message.lower()


@pytest.mark.django_db
class TestStandardWebhookIntegration:
    """Full flow: standard endpoint fires event, delivery uses standard webhook format."""

    def test_standard_endpoint_delivers_with_hmac_envelope(
        self, mock_site_context: Site
    ) -> None:
        site = mock_site_context

        # Regular endpoint -- no transformation fields
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
        )

        event = WebhookEventFactory(
            event_type="user.registered",
            payload={"user_id": "abc-123"},
        )

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ) as mock_request:
            dispatch_event(str(event.pk), site.pk)

        # Verify delivery created and succeeded
        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery is not None
        assert delivery.status == "success"

        # Verify the standard format
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs

        assert call_kwargs["method"] == "POST"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

        # Standard envelope body
        body = json.loads(call_kwargs["content"])
        assert body["type"] == "user.registered"
        assert body["data"] == {"user_id": "abc-123"}
        assert body["id"] == str(event.pk)
        assert "timestamp" in body

        # HMAC signing headers present
        headers = call_kwargs["headers"]
        assert "webhook-id" in headers
        assert "webhook-timestamp" in headers
        assert "webhook-signature" in headers
        assert headers["webhook-signature"].startswith("v1,")


@pytest.mark.django_db
class TestSiteIsolation:
    """Secrets from site A must not be accessible by endpoints from site B."""

    def test_build_template_context_returns_only_own_site_secrets(
        self, mock_site_context: Site
    ) -> None:
        """build_template_context filters secrets by site_id.

        In production, this runs in a background task without a request context.
        We simulate that by clearing thread locals before calling it.
        """
        from freedom_ls.site_aware_models.models import _thread_locals

        site_a = mock_site_context

        # Create a secret for site A
        WebhookSecretFactory(
            name="site_a_key",
            encrypted_value="secret-a-value",
            site=site_a,
        )

        # Create a different site and a secret for it
        site_b = Site.objects.create(name="SiteB", domain="siteb.example.com")
        WebhookSecretFactory(
            name="site_b_key",
            encrypted_value="secret-b-value",
            site=site_b,
        )

        event = WebhookEventFactory(event_type="user.registered")

        # Clear request context to simulate background task environment
        old_request = getattr(_thread_locals, "request", None)
        delattr(_thread_locals, "request")
        try:
            # Build context for site A -- should only see site A's secrets
            context_a = build_template_context(event, site_a.pk)
            secrets_a = context_a["secrets"]
            assert isinstance(secrets_a, dict)
            assert "site_a_key" in secrets_a
            assert "site_b_key" not in secrets_a

            # Build context for site B -- should only see site B's secrets
            context_b = build_template_context(event, site_b.pk)
            secrets_b = context_b["secrets"]
            assert isinstance(secrets_b, dict)
            assert "site_b_key" in secrets_b
            assert "site_a_key" not in secrets_b
        finally:
            _thread_locals.request = old_request

    def test_dispatch_event_only_delivers_to_own_site_endpoints(
        self, mock_site_context: Site
    ) -> None:
        site_a = mock_site_context

        # Endpoint for site A
        WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
            site=site_a,
        )

        # Endpoint for site B
        site_b = Site.objects.create(name="SiteB", domain="siteb.example.com")
        WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
            site=site_b,
        )

        event = WebhookEventFactory(event_type="user.registered")

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", "https://example.com"),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request",
            return_value=mock_response,
        ):
            dispatch_event(str(event.pk), site_a.pk)

        # Only one delivery for site A's endpoint
        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery is not None
        assert delivery.endpoint.site_id == site_a.pk
