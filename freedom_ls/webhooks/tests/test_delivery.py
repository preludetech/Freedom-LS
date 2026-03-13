import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest

from django.utils import timezone

from freedom_ls.webhooks.delivery import (
    MAX_ATTEMPTS,
    RETRY_DELAYS,
    attempt_delivery,
    build_webhook_headers,
    build_webhook_payload,
    calculate_next_retry,
    check_circuit_breaker,
    handle_circuit_breaker_trip,
)
from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookEventFactory,
)


class TestBuildWebhookPayload:
    @pytest.mark.django_db
    def test_returns_valid_json(self, mock_site_context: object) -> None:
        event = WebhookEventFactory(
            event_type="user.registered",
            payload={"user_id": "abc-123"},
        )
        result = build_webhook_payload(event)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.django_db
    def test_envelope_contains_required_fields(self, mock_site_context: object) -> None:
        event = WebhookEventFactory(
            event_type="user.registered",
            payload={"user_id": "abc-123"},
        )
        result = build_webhook_payload(event)
        parsed = json.loads(result)
        assert "id" in parsed
        assert "type" in parsed
        assert "timestamp" in parsed
        assert "data" in parsed

    @pytest.mark.django_db
    def test_envelope_values(self, mock_site_context: object) -> None:
        event = WebhookEventFactory(
            event_type="course.completed",
            payload={"course_id": "xyz-789"},
        )
        result = build_webhook_payload(event)
        parsed = json.loads(result)
        assert parsed["type"] == "course.completed"
        assert parsed["data"] == {"course_id": "xyz-789"}
        assert parsed["id"] == str(event.pk)
        assert isinstance(parsed["timestamp"], int)


class TestBuildWebhookHeaders:
    @pytest.mark.django_db
    def test_includes_all_standard_webhook_headers(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        body = build_webhook_payload(event)
        headers = build_webhook_headers(body, endpoint, event)

        assert "webhook-id" in headers
        assert "webhook-timestamp" in headers
        assert "webhook-signature" in headers
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.django_db
    def test_webhook_id_matches_event_pk(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        body = build_webhook_payload(event)
        headers = build_webhook_headers(body, endpoint, event)

        assert headers["webhook-id"] == str(event.pk)

    @pytest.mark.django_db
    def test_webhook_timestamp_is_integer_string(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        body = build_webhook_payload(event)
        headers = build_webhook_headers(body, endpoint, event)

        # Should be parseable as int
        int(headers["webhook-timestamp"])

    @pytest.mark.django_db
    def test_webhook_signature_starts_with_v1(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        body = build_webhook_payload(event)
        headers = build_webhook_headers(body, endpoint, event)

        assert headers["webhook-signature"].startswith("v1,")


class TestCalculateNextRetry:
    def test_first_retry_within_expected_range(self) -> None:
        # attempt_count=1 means first retry, base delay = RETRY_DELAYS[0] = 60s
        result = calculate_next_retry(1)
        now = timezone.now()
        min_expected = now + timedelta(seconds=60)
        max_expected = now + timedelta(seconds=60 * 1.2)
        assert (
            min_expected - timedelta(seconds=2)
            <= result
            <= max_expected + timedelta(seconds=2)
        )

    def test_later_retries_use_correct_base_delays(self) -> None:
        for i, base_delay in enumerate(RETRY_DELAYS):
            result = calculate_next_retry(i + 1)
            now = timezone.now()
            min_expected = now + timedelta(seconds=base_delay)
            max_expected = now + timedelta(seconds=base_delay * 1.2)
            assert (
                min_expected - timedelta(seconds=2)
                <= result
                <= max_expected + timedelta(seconds=2)
            ), f"Failed for attempt {i + 1} with base delay {base_delay}"

    def test_jitter_adds_variability(self) -> None:
        # Run multiple times and check we don't always get the exact same result
        results = set()
        for _ in range(20):
            result = calculate_next_retry(1)
            # Round to seconds to detect meaningful variation
            results.add(int(result.timestamp()))
        # With 20% jitter on 60s, we should see at least some variation
        assert len(results) > 1


@pytest.mark.django_db
class TestCheckCircuitBreaker:
    def test_active_endpoint_proceeds(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(is_active=True)
        assert check_circuit_breaker(endpoint) is True

    def test_manually_disabled_endpoint_skips(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(is_active=False, disabled_at=None)
        assert check_circuit_breaker(endpoint) is False

    def test_recently_disabled_endpoint_skips(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(
            is_active=False,
            disabled_at=timezone.now() - timedelta(minutes=30),
        )
        assert check_circuit_breaker(endpoint) is False

    def test_disabled_endpoint_probes_after_one_hour(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(
            is_active=False,
            disabled_at=timezone.now() - timedelta(hours=1, minutes=1),
        )
        assert check_circuit_breaker(endpoint) is True


@pytest.mark.django_db
class TestHandleCircuitBreakerTrip:
    def test_does_not_trip_below_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=4, is_active=True)
        handle_circuit_breaker_trip(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.is_active is True
        assert endpoint.disabled_at is None

    def test_trips_at_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=5, is_active=True)
        handle_circuit_breaker_trip(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.is_active is False
        assert endpoint.disabled_at is not None

    def test_trips_above_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=10, is_active=True)
        handle_circuit_breaker_trip(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.is_active is False
        assert endpoint.disabled_at is not None


@pytest.mark.django_db
class TestAttemptDelivery:
    def test_successful_delivery(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()
        endpoint = delivery.endpoint
        endpoint.failure_count = 3
        endpoint.save()

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        assert delivery.attempt_count == 1
        assert delivery.last_status_code == 200
        assert delivery.last_attempt_at is not None
        assert delivery.last_latency_ms is not None

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 0
        assert endpoint.disabled_at is None

    def test_4xx_marks_failed(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=400,
            content=b"Bad Request",
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.last_status_code == 400

    def test_429_schedules_retry(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=429,
            content=b"Too Many Requests",
            headers={"Retry-After": "120"},
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at is not None
        assert delivery.last_status_code == 429

    def test_429_uses_retry_after_header(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=429,
            content=b"Too Many Requests",
            headers={"Retry-After": "120"},
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        now = timezone.now()
        # Retry-After is 120 seconds
        expected_min = now + timedelta(seconds=118)
        expected_max = now + timedelta(seconds=122)
        assert expected_min <= delivery.next_retry_at <= expected_max

    def test_5xx_schedules_retry(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at is not None

        delivery.endpoint.refresh_from_db()
        assert delivery.endpoint.failure_count == 1

    def test_timeout_schedules_retry(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at is not None
        assert delivery.last_status_code is None

        delivery.endpoint.refresh_from_db()
        assert delivery.endpoint.failure_count == 1

    def test_connection_error_schedules_retry(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at is not None

    def test_max_attempts_marks_dead_letter(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory(attempt_count=MAX_ATTEMPTS - 1)

        mock_response = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "dead_letter"
        assert delivery.attempt_count == MAX_ATTEMPTS
        assert delivery.next_retry_at is None

    def test_success_resets_endpoint_failure_state(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(
            failure_count=4,
            disabled_at=timezone.now() - timedelta(hours=2),
            is_active=False,
        )
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 0
        assert endpoint.disabled_at is None
        assert endpoint.is_active is True

    def test_retryable_failure_increments_failure_count(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(failure_count=0)
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=502,
            content=b"Bad Gateway",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 1

    def test_retryable_failure_trips_circuit_breaker(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(failure_count=4)
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.post", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 5
        assert endpoint.is_active is False
        assert endpoint.disabled_at is not None
