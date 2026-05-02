import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest

from django.utils import timezone

from freedom_ls.webhooks.delivery import (
    MAX_ATTEMPTS,
    _increment_failure_count_and_check_breaker,
    attempt_delivery,
    build_standard_request,
    build_transformed_request,
    build_webhook_headers,
    build_webhook_payload,
    calculate_next_retry,
    check_circuit_breaker,
)
from freedom_ls.webhooks.factories import (
    WebhookDeliveryFactory,
    WebhookEndpointFactory,
    WebhookEventFactory,
    WebhookSecretFactory,
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
        assert isinstance(parsed["timestamp"], str)
        # Should be ISO 8601 format ending with Z
        assert parsed["timestamp"].endswith("Z")


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
    @pytest.mark.parametrize(
        ("attempt_count", "base_delay_seconds", "max_delay_seconds"),
        [
            (1, 60, 72),
            (2, 300, 360),
            (3, 1800, 2160),
            (4, 7200, 8640),
            (5, 43200, 51840),
        ],
        ids=[
            "attempt_1_uses_60s_base",
            "attempt_2_uses_300s_base",
            "attempt_3_uses_1800s_base",
            "attempt_4_uses_7200s_base",
            "attempt_5_uses_43200s_base",
        ],
    )
    def test_retry_delay_window(
        self,
        attempt_count: int,
        base_delay_seconds: int,
        max_delay_seconds: int,
    ) -> None:
        # Hard-coded oracle: 20% jitter on each documented retry delay.
        # Do NOT import RETRY_DELAYS here — re-deriving the bound from the
        # production constant re-introduces the tautology this test removed.
        result = calculate_next_retry(attempt_count)
        now = timezone.now()
        min_expected = now + timedelta(seconds=base_delay_seconds)
        max_expected = now + timedelta(seconds=max_delay_seconds)
        # 2-second slop for clock drift between calculate_next_retry() and
        # the timezone.now() above.
        assert (
            min_expected - timedelta(seconds=2)
            <= result
            <= max_expected + timedelta(seconds=2)
        )

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

    def test_circuit_broken_endpoint_skips_during_cooldown(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(
            is_active=True,
            disabled_at=timezone.now() - timedelta(minutes=30),
        )
        assert check_circuit_breaker(endpoint) is False

    def test_circuit_broken_endpoint_probes_after_cooldown(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(
            is_active=True,
            disabled_at=timezone.now() - timedelta(hours=1, minutes=1),
        )
        assert check_circuit_breaker(endpoint) is True

    def test_user_disabled_with_expired_cooldown_still_returns_false(
        self, mock_site_context: object
    ) -> None:
        """User-disabled endpoints stay disabled even if cooldown has expired."""
        endpoint = WebhookEndpointFactory(
            is_active=False,
            disabled_at=timezone.now() - timedelta(hours=2),
        )
        assert check_circuit_breaker(endpoint) is False


@pytest.mark.django_db
class TestIncrementFailureCountAndCheckBreaker:
    def test_does_not_trip_below_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=3, is_active=True)
        _increment_failure_count_and_check_breaker(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.failure_count == 4
        assert endpoint.is_active is True
        assert endpoint.disabled_at is None

    def test_trips_at_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=4, is_active=True)
        _increment_failure_count_and_check_breaker(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.failure_count == 5
        assert endpoint.is_active is True
        assert endpoint.disabled_at is not None

    def test_trips_above_threshold(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(failure_count=9, is_active=True)
        _increment_failure_count_and_check_breaker(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.failure_count == 10
        assert endpoint.is_active is True
        assert endpoint.disabled_at is not None

    def test_atomically_increments_failure_count(
        self, mock_site_context: object
    ) -> None:
        """Verify F() expression is used for atomic increment."""
        endpoint = WebhookEndpointFactory(failure_count=2, is_active=True)
        _increment_failure_count_and_check_breaker(endpoint)
        endpoint.refresh_from_db()
        assert endpoint.failure_count == 3


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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
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

    def test_4xx_marks_permanent_failure(self, mock_site_context: object) -> None:
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=400,
            content=b"Bad Request",
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "permanent_failure"
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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
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
            "freedom_ls.webhooks.delivery.httpx.request",
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
            "freedom_ls.webhooks.delivery.httpx.request",
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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "dead_letter"
        assert delivery.attempt_count == MAX_ATTEMPTS
        assert delivery.next_retry_at is None

    def test_success_resets_endpoint_circuit_breaker_state(
        self, mock_site_context: object
    ) -> None:
        endpoint = WebhookEndpointFactory(
            failure_count=4,
            disabled_at=timezone.now() - timedelta(hours=2),
            is_active=True,
        )
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 0
        assert endpoint.disabled_at is None
        assert endpoint.is_active is True

    def test_success_does_not_reenable_user_disabled_endpoint(
        self, mock_site_context: object
    ) -> None:
        """Success on a user-disabled endpoint should not re-enable it."""
        endpoint = WebhookEndpointFactory(
            failure_count=3,
            disabled_at=None,
            is_active=False,
        )
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 0
        assert endpoint.disabled_at is None
        assert endpoint.is_active is False

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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 1

    def test_4xx_increments_failure_count(self, mock_site_context: object) -> None:
        """Issue #7: 4xx responses should increment failure_count on endpoint."""
        endpoint = WebhookEndpointFactory(failure_count=4)
        delivery = WebhookDeliveryFactory(endpoint=endpoint)

        mock_response = httpx.Response(
            status_code=400,
            content=b"Bad Request",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "permanent_failure"

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 5
        assert endpoint.is_active is True
        assert endpoint.disabled_at is not None

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
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ):
            attempt_delivery(delivery)

        endpoint.refresh_from_db()
        assert endpoint.failure_count == 5
        assert endpoint.is_active is True
        assert endpoint.disabled_at is not None


@pytest.mark.django_db
class TestAttemptDeliveryWithTransformation:
    """Tests for attempt_delivery with transformed endpoints."""

    def test_without_transformation_works_as_before(
        self, mock_site_context: object
    ) -> None:
        """Regression: endpoint without transformation uses standard delivery."""
        delivery = WebhookDeliveryFactory()

        mock_response = httpx.Response(
            status_code=200,
            content=b'{"ok": true}',
            request=httpx.Request("POST", delivery.endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        # Standard delivery uses POST and application/json
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        assert call_kwargs.kwargs["method"] == "POST"
        assert call_kwargs.kwargs["headers"]["Content-Type"] == "application/json"

    def test_with_transformation_uses_rendered_body(
        self, mock_site_context: object
    ) -> None:
        """Endpoint with transformation renders body_template."""
        endpoint = WebhookEndpointFactory(
            body_template='{"custom": "{{ event.type }}"}',
            content_type="application/json",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory(event_type="user.registered")
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        delivery.refresh_from_db()
        assert delivery.status == "success"
        sent_body = mock_request.call_args.kwargs["content"]
        parsed = json.loads(sent_body)
        assert parsed["custom"] == "user.registered"

    def test_with_transformation_uses_rendered_headers(
        self, mock_site_context: object
    ) -> None:
        """Endpoint with headers_template merges rendered headers."""
        endpoint = WebhookEndpointFactory(
            body_template="body content",
            headers_template='{"X-Custom": "my-value"}',
            content_type="text/plain",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        assert headers["X-Custom"] == "my-value"

    def test_body_template_render_failure_marks_delivery_failed(
        self, mock_site_context: object
    ) -> None:
        """Template rendering failure marks delivery as failed with error message."""
        endpoint = WebhookEndpointFactory(
            body_template="{{ undefined_variable }}",
            content_type="application/json",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        with patch("freedom_ls.webhooks.delivery.httpx.request") as mock_request:
            attempt_delivery(delivery)
            # No HTTP request should have been made
            mock_request.assert_not_called()

        delivery.refresh_from_db()
        assert delivery.status == "permanent_failure"
        assert delivery.last_response_error_message != ""
        assert "undefined_variable" in delivery.last_response_error_message.lower()

    def test_headers_template_render_failure_marks_delivery_failed(
        self, mock_site_context: object
    ) -> None:
        """Headers template rendering failure marks delivery as failed."""
        endpoint = WebhookEndpointFactory(
            body_template="valid body",
            headers_template="{{ undefined_header_var }}",
            content_type="text/plain",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        with patch("freedom_ls.webhooks.delivery.httpx.request") as mock_request:
            attempt_delivery(delivery)
            mock_request.assert_not_called()

        delivery.refresh_from_db()
        assert delivery.status == "permanent_failure"
        assert delivery.last_response_error_message != ""

    def test_headers_template_invalid_json_marks_delivery_failed(
        self, mock_site_context: object
    ) -> None:
        """Headers template that renders to invalid JSON marks delivery as failed."""
        endpoint = WebhookEndpointFactory(
            body_template="valid body",
            headers_template="not json at all",
            content_type="text/plain",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        with patch("freedom_ls.webhooks.delivery.httpx.request") as mock_request:
            attempt_delivery(delivery)
            mock_request.assert_not_called()

        delivery.refresh_from_db()
        assert delivery.status == "permanent_failure"
        assert delivery.last_response_error_message != ""

    def test_custom_http_method_used(self, mock_site_context: object) -> None:
        """Custom HTTP method from endpoint is used in the request."""
        endpoint = WebhookEndpointFactory(
            body_template="body",
            http_method="PUT",
            content_type="text/plain",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("PUT", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        assert mock_request.call_args.kwargs["method"] == "PUT"

    def test_custom_content_type_set_in_headers(
        self, mock_site_context: object
    ) -> None:
        """Custom content_type from endpoint is set in headers."""
        endpoint = WebhookEndpointFactory(
            body_template="<xml>data</xml>",
            http_method="POST",
            content_type="application/xml",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/xml"

    def test_auth_type_signing_includes_hmac_headers(
        self, mock_site_context: object
    ) -> None:
        """auth_type=signing adds HMAC signature headers even with transformation."""
        endpoint = WebhookEndpointFactory(
            body_template='{"data": "test"}',
            http_method="POST",
            content_type="application/json",
            auth_type="signing",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        assert "webhook-id" in headers
        assert "webhook-timestamp" in headers
        assert "webhook-signature" in headers

    def test_auth_type_none_excludes_hmac_headers(
        self, mock_site_context: object
    ) -> None:
        """auth_type=none does not add HMAC signature headers."""
        endpoint = WebhookEndpointFactory(
            body_template='{"data": "test"}',
            http_method="POST",
            content_type="application/json",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        assert "webhook-id" not in headers
        assert "webhook-timestamp" not in headers
        assert "webhook-signature" not in headers

    def test_rendered_headers_override_defaults(
        self, mock_site_context: object
    ) -> None:
        """Rendered headers from headers_template override default headers."""
        endpoint = WebhookEndpointFactory(
            body_template="body",
            headers_template='{"Content-Type": "text/html"}',
            content_type="text/plain",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        # Rendered header overrides the default Content-Type
        assert headers["Content-Type"] == "text/html"

    def test_json_content_type_with_invalid_json_body_still_proceeds(
        self, mock_site_context: object
    ) -> None:
        """Delivery proceeds even if body is not valid JSON despite json content type."""
        endpoint = WebhookEndpointFactory(
            body_template="not valid json {{ event.type }}",
            http_method="POST",
            content_type="application/json",
            auth_type="none",
        )
        event = WebhookEventFactory(event_type="user.registered")
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        # Request was made despite invalid JSON body
        mock_request.assert_called_once()
        delivery.refresh_from_db()
        assert delivery.status == "success"

    def test_transformation_with_secrets_in_headers(
        self, mock_site_context: object
    ) -> None:
        """Transformed endpoint can use secrets in headers_template."""
        site = mock_site_context
        WebhookSecretFactory(name="api_key", encrypted_value="secret-123", site=site)

        endpoint = WebhookEndpointFactory(
            body_template='{"msg": "hello"}',
            headers_template='{"Authorization": "Bearer {{ secrets.api_key }}"}',
            content_type="application/json",
            http_method="POST",
            auth_type="none",
        )
        event = WebhookEventFactory()
        delivery = WebhookDeliveryFactory(endpoint=endpoint, event=event)

        mock_response = httpx.Response(
            status_code=200,
            content=b"OK",
            request=httpx.Request("POST", endpoint.url),
        )

        with patch(
            "freedom_ls.webhooks.delivery.httpx.request", return_value=mock_response
        ) as mock_request:
            attempt_delivery(delivery)

        headers = mock_request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer secret-123"


@pytest.mark.django_db
class TestBuildStandardRequest:
    """Tests for build_standard_request helper."""

    def test_returns_post_method(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        method, _body, _headers = build_standard_request(endpoint, event)
        assert method == "POST"

    def test_returns_json_content_type(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory()
        _method, _body, headers = build_standard_request(endpoint, event)
        assert headers["Content-Type"] == "application/json"

    def test_body_is_valid_json_envelope(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory()
        event = WebhookEventFactory(event_type="test.event")
        _method, body, _headers = build_standard_request(endpoint, event)
        parsed = json.loads(body)
        assert parsed["type"] == "test.event"


@pytest.mark.django_db
class TestBuildTransformedRequest:
    """Tests for build_transformed_request helper."""

    def test_renders_body_template(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(
            body_template='{"event": "{{ event.type }}"}',
            http_method="POST",
            content_type="application/json",
            auth_type="none",
        )
        event = WebhookEventFactory(event_type="course.completed")
        _method, body, _headers = build_transformed_request(endpoint, event)
        parsed = json.loads(body)
        assert parsed["event"] == "course.completed"

    def test_uses_custom_http_method(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(
            body_template="body",
            http_method="PATCH",
            content_type="text/plain",
            auth_type="none",
        )
        event = WebhookEventFactory()
        method, _body, _headers = build_transformed_request(endpoint, event)
        assert method == "PATCH"

    def test_defaults_method_to_post(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(
            body_template="body",
            http_method="",
            content_type="text/plain",
            auth_type="none",
        )
        event = WebhookEventFactory()
        method, _body, _headers = build_transformed_request(endpoint, event)
        assert method == "POST"

    def test_defaults_content_type_to_json(self, mock_site_context: object) -> None:
        endpoint = WebhookEndpointFactory(
            body_template="body",
            http_method="POST",
            content_type="",
            auth_type="none",
        )
        event = WebhookEventFactory()
        _method, _body, headers = build_transformed_request(endpoint, event)
        assert headers["Content-Type"] == "application/json"
