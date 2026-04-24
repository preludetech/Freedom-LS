from unittest.mock import patch

import pytest

from freedom_ls.webhooks.factories import (
    WebhookEndpointFactory,
    WebhookEventFactory,
)
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEvent


@pytest.mark.django_db(transaction=True)
class TestFireWebhookEvent:
    def test_raises_value_error_for_unknown_event_type(
        self, mock_site_context: object
    ) -> None:
        from freedom_ls.webhooks.events import fire_webhook_event

        with pytest.raises(ValueError, match="Unknown webhook event type"):
            fire_webhook_event("nonexistent.event", {"key": "value"})

    def test_creates_event_record_on_commit(self, mock_site_context: object) -> None:
        from freedom_ls.webhooks.events import fire_webhook_event

        assert WebhookEvent.objects.count() == 0

        fire_webhook_event("user.registered", {"user_id": "abc-123"})

        assert WebhookEvent.objects.count() == 1
        event = WebhookEvent.objects.first()
        assert event is not None
        assert event.event_type == "user.registered"
        assert event.payload == {"user_id": "abc-123"}

    def test_enqueues_dispatch_event_task(self, mock_site_context: object) -> None:
        from freedom_ls.webhooks.events import fire_webhook_event

        with patch("freedom_ls.webhooks.events.default_task_backend") as mock_backend:
            fire_webhook_event("user.registered", {"user_id": "abc-123"})

        event = WebhookEvent.objects.first()
        assert event is not None
        mock_backend.enqueue.assert_called_once()
        enqueue_args = mock_backend.enqueue.call_args
        # The first positional arg is the task, then args=[event_id, site_id]
        assert enqueue_args.kwargs["args"] == [
            str(event.pk),
            mock_site_context.pk,
        ]

    def test_does_not_create_event_for_invalid_type(
        self, mock_site_context: object
    ) -> None:
        from freedom_ls.webhooks.events import fire_webhook_event

        with pytest.raises(ValueError, match="Unknown webhook event type"):
            fire_webhook_event("invalid.type", {"data": "test"})

        assert WebhookEvent.objects.count() == 0


@pytest.mark.django_db
class TestDispatchEvent:
    def test_finds_matching_endpoints_and_creates_deliveries(
        self, mock_site_context: object
    ) -> None:
        from freedom_ls.webhooks.events import dispatch_event

        endpoint = WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
        )
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 1
        delivery = WebhookDelivery.objects.first()
        assert delivery is not None
        assert delivery.event == event
        assert delivery.endpoint == endpoint
        assert delivery.status == "pending"
        mock_attempt.assert_called_once_with(delivery)

    def test_skips_endpoints_not_subscribed_to_event_type(
        self, mock_site_context: object
    ) -> None:
        from freedom_ls.webhooks.events import dispatch_event

        # Endpoint subscribes to course.completed, not user.registered
        WebhookEndpointFactory(
            event_types=["course.completed"],
            is_active=True,
        )
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 0
        mock_attempt.assert_not_called()

    def test_skips_manually_disabled_endpoints(self, mock_site_context: object) -> None:
        from freedom_ls.webhooks.events import dispatch_event

        # Manually disabled endpoint (is_active=False, disabled_at=None)
        WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=False,
            disabled_at=None,
        )
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 0
        mock_attempt.assert_not_called()

    def test_respects_circuit_breaker_allowing_probe(
        self, mock_site_context: object
    ) -> None:
        from datetime import timedelta

        from django.utils import timezone

        from freedom_ls.webhooks.events import dispatch_event

        # Endpoint circuit-broken over an hour ago — circuit breaker allows probe
        WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
            disabled_at=timezone.now() - timedelta(hours=1, minutes=1),
        )
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 1
        mock_attempt.assert_called_once()

    def test_delivers_to_multiple_matching_endpoints(
        self, mock_site_context: object
    ) -> None:
        from freedom_ls.webhooks.events import dispatch_event

        WebhookEndpointFactory(event_types=["user.registered"], is_active=True)
        WebhookEndpointFactory(event_types=["user.registered"], is_active=True)
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 2
        assert mock_attempt.call_count == 2

    def test_returns_silently_when_event_does_not_exist(
        self, mock_site_context: object
    ) -> None:
        from uuid import uuid4

        from freedom_ls.webhooks.events import dispatch_event

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(uuid4()), mock_site_context.pk)

        assert WebhookDelivery.objects.count() == 0
        mock_attempt.assert_not_called()

    def test_filters_by_site_id(self, mock_site_context: object) -> None:
        from django.contrib.sites.models import Site

        from freedom_ls.webhooks.events import dispatch_event

        # Create an endpoint for the current site
        WebhookEndpointFactory(event_types=["user.registered"], is_active=True)

        # Create endpoint for a different site
        other_site = Site.objects.create(name="OtherSite", domain="othersite")
        WebhookEndpointFactory(
            event_types=["user.registered"],
            is_active=True,
            site=other_site,
        )
        event = WebhookEventFactory(event_type="user.registered")

        with patch("freedom_ls.webhooks.events.attempt_delivery") as mock_attempt:
            dispatch_event(str(event.pk), mock_site_context.pk)

        # Only one delivery for current site's endpoint
        assert WebhookDelivery.objects.count() == 1
        mock_attempt.assert_called_once()
