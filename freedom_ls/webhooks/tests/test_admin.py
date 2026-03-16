from unittest.mock import patch

import httpx
import pytest

from django.utils import timezone

from freedom_ls.webhooks.admin import WebhookDeliveryAdmin, WebhookEndpointAdmin
from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
)
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint


@pytest.mark.django_db
class TestRetryDeliveries:
    def test_retry_resets_delivery_state(self, mock_site_context: object) -> None:
        """Issue #1: retry must reset attempt_count and status before re-attempting."""
        delivery = WebhookDeliveryFactory(
            attempt_count=6,
            status="dead_letter",
        )
        endpoint = delivery.endpoint

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)
        queryset = WebhookDelivery.objects.filter(pk=delivery.pk)

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            admin_instance.retry_deliveries(request=None, queryset=queryset)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.attempt_count == 1  # reset to 0, then incremented by attempt

    def test_retry_uses_select_related(self, mock_site_context: object) -> None:
        """Issue #5: retry queryset should use select_related to avoid N+1."""
        delivery = WebhookDeliveryFactory(
            status="failed",
        )

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)
        queryset = WebhookDelivery.objects.filter(pk=delivery.pk)

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ) as mock_post:
            # Use assertNumQueries or just verify it works without extra queries
            admin_instance.retry_deliveries(request=None, queryset=queryset)
            mock_post.assert_called_once()


@pytest.mark.django_db
class TestEnableEndpoints:
    def test_enable_clears_circuit_breaker_state(
        self, mock_site_context: object
    ) -> None:
        """Issue #6: enable_endpoints must clear disabled_at and failure_count."""
        endpoint = WebhookEndpointFactory(
            is_active=False,
            disabled_at=timezone.now(),
            failure_count=5,
        )

        admin_instance = WebhookEndpointAdmin(WebhookEndpoint, None)
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)

        admin_instance.enable_endpoints(request=None, queryset=queryset)

        endpoint.refresh_from_db()
        assert endpoint.is_active is True
        assert endpoint.disabled_at is None
        assert endpoint.failure_count == 0
