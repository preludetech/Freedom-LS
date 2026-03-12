import pytest

from django.core.exceptions import ValidationError

from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookEventFactory,
)


@pytest.mark.django_db
class TestWebhookEndpoint:
    def test_secret_auto_generated_on_save(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        assert endpoint.secret
        # Secret should not change on subsequent saves
        original_secret = endpoint.secret
        endpoint.save()
        assert endpoint.secret == original_secret

    def test_clean_https_not_enforced_in_debug(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = True
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        # Should not raise
        endpoint.clean()

    def test_clean_http_url_does_not_pass_in_production(
        self, mock_site_context: object, settings: object
    ) -> None:
        settings.DEBUG = False
        endpoint = WebhookEndpointFactory(url="http://example.com/webhook")
        with pytest.raises(ValidationError):
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

    def test_short_response_body_not_truncated(self, mock_site_context: object) -> None:
        short_body = "x" * 100
        delivery = WebhookDeliveryFactory(last_response_body=short_body)
        assert delivery.last_response_body == short_body

    def test_delivery_linked_to_event_and_endpoint(
        self, mock_site_context: object
    ) -> None:
        delivery = WebhookDeliveryFactory()
        assert delivery.event is not None
        assert delivery.endpoint is not None
        assert delivery.event.deliveries.count() == 1
        assert delivery.endpoint.deliveries.count() == 1
