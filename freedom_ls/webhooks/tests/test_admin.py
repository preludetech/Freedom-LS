from unittest.mock import patch

import pytest

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from freedom_ls.webhooks.admin import (
    WebhookDeliveryAdmin,
    WebhookEndpointAdmin,
    WebhookEventAdmin,
)
from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookEventFactory,
)
from freedom_ls.webhooks.models import (
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
)


@pytest.mark.django_db
class TestWebhookEndpointAdmin:
    def test_registered(self) -> None:
        assert admin.site.is_registered(WebhookEndpoint)

    def test_list_display(self) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        assert model_admin.list_display == [
            "description",
            "url_truncated",
            "display_event_types",
            "is_active",
            "failure_count",
            "created_at",
        ]

    def test_list_filter(self) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        assert model_admin.list_filter == ["is_active", "created_at"]

    def test_readonly_fields(self) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        assert "secret" in model_admin.readonly_fields
        assert "failure_count" in model_admin.readonly_fields
        assert "disabled_at" in model_admin.readonly_fields
        assert "created_at" in model_admin.readonly_fields
        assert "updated_at" in model_admin.readonly_fields

    def test_url_truncated_short(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory(url="https://example.com/hook")
        result = model_admin.url_truncated(endpoint)
        assert result == "https://example.com/hook"

    def test_url_truncated_long(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        long_url = "https://example.com/" + "a" * 100
        endpoint = WebhookEndpointFactory(url=long_url)
        result = model_admin.url_truncated(endpoint)
        assert len(result) == 53  # 50 chars + "..."
        assert result.endswith("...")

    def test_display_event_types(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered", "course.completed"]
        )
        result = model_admin.display_event_types(endpoint)
        assert result == "user.registered, course.completed"

    def test_display_event_types_empty(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory(event_types=[])
        result = model_admin.display_event_types(endpoint)
        assert result == ""

    def test_enable_endpoints_action(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory(is_active=False)
        request = RequestFactory().post("/admin/")
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)
        model_admin.enable_endpoints(request, queryset)
        endpoint.refresh_from_db()
        assert endpoint.is_active is True

    def test_disable_endpoints_action(self, mock_site_context: object) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory(is_active=True)
        request = RequestFactory().post("/admin/")
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)
        model_admin.disable_endpoints(request, queryset)
        endpoint.refresh_from_db()
        assert endpoint.is_active is False

    @patch("freedom_ls.webhooks.admin.send_test_ping")
    def test_send_test_ping_action(
        self, mock_send_ping: object, mock_site_context: object
    ) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        endpoint = WebhookEndpointFactory()
        request = RequestFactory().post("/admin/")
        queryset = WebhookEndpoint.objects.filter(pk=endpoint.pk)
        model_admin.send_test_ping(request, queryset)
        mock_send_ping.assert_called_once_with(endpoint)

    def test_actions_list(self) -> None:
        model_admin = WebhookEndpointAdmin(WebhookEndpoint, AdminSite())
        assert "enable_endpoints" in model_admin.actions
        assert "disable_endpoints" in model_admin.actions
        assert "send_test_ping" in model_admin.actions


@pytest.mark.django_db
class TestWebhookEventAdmin:
    def test_registered(self) -> None:
        assert admin.site.is_registered(WebhookEvent)

    def test_list_display(self) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        assert model_admin.list_display == [
            "event_type",
            "short_id",
            "created_at",
        ]

    def test_list_filter(self) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        assert model_admin.list_filter == ["event_type", "created_at"]

    def test_has_add_permission_false(self) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        request = RequestFactory().get("/admin/")
        assert model_admin.has_add_permission(request) is False

    def test_has_change_permission_false(self) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        request = RequestFactory().get("/admin/")
        assert model_admin.has_change_permission(request) is False

    def test_short_id(self, mock_site_context: object) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        event = WebhookEventFactory()
        result = model_admin.short_id(event)
        assert len(result) == 8
        assert result == str(event.pk)[:8]

    def test_all_fields_readonly(self) -> None:
        model_admin = WebhookEventAdmin(WebhookEvent, AdminSite())
        # All model fields should be readonly
        for field in ["event_type", "payload", "created_at"]:
            assert field in model_admin.readonly_fields


@pytest.mark.django_db
class TestWebhookDeliveryAdmin:
    def test_registered(self) -> None:
        assert admin.site.is_registered(WebhookDelivery)

    def test_list_display(self) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        assert model_admin.list_display == [
            "event_type_display",
            "endpoint_truncated",
            "status",
            "attempt_count",
            "last_status_code",
            "last_attempt_at",
        ]

    def test_list_filter(self) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        assert model_admin.list_filter == [
            "status",
            "endpoint",
            "event__event_type",
        ]

    def test_event_type_display(self, mock_site_context: object) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        delivery = WebhookDeliveryFactory()
        result = model_admin.event_type_display(delivery)
        assert result == delivery.event.event_type

    def test_endpoint_truncated(self, mock_site_context: object) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        long_url = "https://example.com/" + "a" * 100
        delivery = WebhookDeliveryFactory(endpoint=WebhookEndpointFactory(url=long_url))
        result = model_admin.endpoint_truncated(delivery)
        assert len(result) == 53
        assert result.endswith("...")

    @patch("freedom_ls.webhooks.admin.attempt_delivery")
    def test_retry_deliveries_action(
        self, mock_attempt: object, mock_site_context: object
    ) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        delivery_failed = WebhookDeliveryFactory(status="failed")
        delivery_dead = WebhookDeliveryFactory(status="dead_letter")
        delivery_success = WebhookDeliveryFactory(status="success")
        request = RequestFactory().post("/admin/")
        queryset = WebhookDelivery.objects.filter(
            pk__in=[delivery_failed.pk, delivery_dead.pk, delivery_success.pk]
        )
        model_admin.retry_deliveries(request, queryset)
        # Only failed and dead_letter deliveries should be retried
        assert mock_attempt.call_count == 2

    def test_all_fields_readonly(self) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        for field in [
            "event",
            "endpoint",
            "status",
            "attempt_count",
            "last_status_code",
            "last_attempt_at",
        ]:
            assert field in model_admin.readonly_fields

    def test_actions_list(self) -> None:
        model_admin = WebhookDeliveryAdmin(WebhookDelivery, AdminSite())
        assert "retry_deliveries" in model_admin.actions
