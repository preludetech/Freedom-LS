import pytest

from django.core.exceptions import ValidationError

from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookEventFactory,
)
from freedom_ls.webhooks.models import STATUS_CHOICES


@pytest.mark.django_db
class TestWebhookEndpoint:
    def test_create_endpoint(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        assert endpoint.pk is not None
        assert endpoint.secret != ""
        assert len(endpoint.secret) > 0
        assert endpoint.is_active is True

    def test_secret_auto_generated_on_save(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        assert endpoint.secret
        # Secret should not change on subsequent saves
        original_secret = endpoint.secret
        endpoint.save()
        assert endpoint.secret == original_secret

    def test_str_returns_description(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(description="My webhook")
        assert str(endpoint) == "My webhook"

    def test_clean_valid_event_types(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered", "course.completed"]
        )
        # Should not raise
        endpoint.clean()

    def test_clean_invalid_event_type_raises(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(event_types=["invalid.type"])
        with pytest.raises(ValidationError) as exc_info:
            endpoint.clean()
        assert "event_types" in exc_info.value.message_dict

    def test_clean_https_enforced_in_production(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = False
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        with pytest.raises(ValidationError) as exc_info:
            endpoint.clean()
        assert "url" in exc_info.value.message_dict

    def test_clean_https_not_enforced_in_debug(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        # Should not raise
        endpoint.clean()

    def test_clean_https_url_passes_in_production(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = False
        endpoint = WebhookEndpointFactory(url="https://example.com/webhook")
        # Should not raise
        endpoint.clean()

    def test_clean_empty_event_types_passes(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(event_types=[])
        # Should not raise
        endpoint.clean()


@pytest.mark.django_db
class TestWebhookEvent:
    def test_create_event(self, mock_site_context: object) -> None:
        event = WebhookEventFactory()
        assert event.pk is not None
        assert event.event_type == "user.registered"
        assert event.payload == {"user_id": "abc-123"}


@pytest.mark.django_db
class TestWebhookDelivery:
    def test_create_delivery(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()
        assert delivery.pk is not None
        assert delivery.status == "pending"
        assert delivery.attempt_count == 0

    def test_status_choices(self) -> None:
        status_values = [choice[0] for choice in STATUS_CHOICES]
        assert "pending" in status_values
        assert "success" in status_values
        assert "failed" in status_values
        assert "dead_letter" in status_values

    def test_response_body_truncated_on_save(self, mock_site_context: object) -> None:
        long_body = "x" * 1000
        delivery = WebhookDeliveryFactory(last_response_body=long_body)
        assert len(delivery.last_response_body) == 500

    def test_short_response_body_not_truncated(self, mock_site_context: object) -> None:
        short_body = "x" * 100
        delivery = WebhookDeliveryFactory(last_response_body=short_body)
        assert len(delivery.last_response_body) == 100

    def test_delivery_linked_to_event_and_endpoint(
        self, mock_site_context: object
    ) -> None:
        delivery = WebhookDeliveryFactory()
        assert delivery.event is not None
        assert delivery.endpoint is not None
        assert delivery.event.deliveries.count() == 1
        assert delivery.endpoint.deliveries.count() == 1
