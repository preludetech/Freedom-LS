import contextlib
import json
import random
import time
from datetime import datetime, timedelta

import httpx

from django.utils import timezone

from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from freedom_ls.webhooks.signing import sign_webhook

RETRY_DELAYS = [60, 300, 1800, 7200, 43200]  # seconds
MAX_ATTEMPTS = 6  # initial + 5 retries
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN = timedelta(hours=1)
REQUEST_TIMEOUT = 30  # seconds


def build_webhook_payload(event: WebhookEvent) -> str:
    """Build the JSON envelope: {id, type, timestamp, data}."""
    envelope = {
        "id": str(event.pk),
        "type": event.event_type,
        "timestamp": int(event.created_at.timestamp()),
        "data": event.payload,
    }
    return json.dumps(envelope, separators=(",", ":"))


def build_webhook_headers(
    body: str, endpoint: WebhookEndpoint, event: WebhookEvent
) -> dict[str, str]:
    """Build headers: webhook-id, webhook-timestamp, webhook-signature, Content-Type."""
    timestamp = int(time.time())
    webhook_id = str(event.pk)
    signature = sign_webhook(
        body=body,
        secret=endpoint.secret,
        webhook_id=webhook_id,
        timestamp=timestamp,
    )
    return {
        "webhook-id": webhook_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": signature,
        "Content-Type": "application/json",
    }


def attempt_delivery(delivery: WebhookDelivery) -> None:
    """
    Send HTTP POST to the endpoint URL.
    Classifies response and updates delivery/endpoint records accordingly.
    """
    endpoint = delivery.endpoint
    event = delivery.event

    body = build_webhook_payload(event)
    headers = build_webhook_headers(body, endpoint, event)

    response: httpx.Response | None = None
    start_time = time.monotonic()

    with contextlib.suppress(httpx.TimeoutException, httpx.ConnectError):
        response = httpx.post(
            endpoint.url,
            content=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    status_code = response.status_code if response is not None else None

    delivery.attempt_count += 1
    delivery.last_status_code = status_code
    delivery.last_response_body = response.text if response is not None else ""
    delivery.last_attempt_at = timezone.now()
    delivery.last_latency_ms = elapsed_ms

    if response is not None and 200 <= response.status_code < 300:
        _handle_success(delivery, endpoint)
    elif response is not None and response.status_code == 429:
        retry_after = _parse_retry_after(response)
        _handle_retryable_failure(delivery, endpoint, retry_after=retry_after)
    elif response is not None and 400 <= response.status_code < 500:
        _handle_permanent_failure(delivery)
    else:
        # 5xx, timeout, or connection error
        _handle_retryable_failure(delivery, endpoint)

    delivery.save()


def _parse_retry_after(response: httpx.Response) -> int | None:
    """Parse the Retry-After header value as seconds."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return int(retry_after)
        except ValueError:
            return None
    return None


def _handle_success(delivery: WebhookDelivery, endpoint: WebhookEndpoint) -> None:
    """Mark delivery as successful and reset endpoint failure state."""
    delivery.status = "success"
    delivery.next_retry_at = None
    endpoint.failure_count = 0
    endpoint.disabled_at = None
    endpoint.is_active = True
    endpoint.save()


def _handle_permanent_failure(delivery: WebhookDelivery) -> None:
    """Mark delivery as permanently failed (4xx except 429)."""
    delivery.status = "failed"
    delivery.next_retry_at = None


def _handle_retryable_failure(
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint,
    retry_after: int | None = None,
) -> None:
    """Handle a retryable failure: schedule retry or mark dead letter."""
    endpoint.failure_count += 1
    endpoint.save()
    handle_circuit_breaker_trip(endpoint)

    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "dead_letter"
        delivery.next_retry_at = None
    else:
        delivery.status = "failed"
        if retry_after is not None:
            delivery.next_retry_at = timezone.now() + timedelta(seconds=retry_after)
        else:
            delivery.next_retry_at = calculate_next_retry(delivery.attempt_count)


def calculate_next_retry(attempt_count: int) -> datetime:
    """Base delay from RETRY_DELAYS + random jitter up to 20%."""
    index = min(attempt_count - 1, len(RETRY_DELAYS) - 1)
    base_delay = RETRY_DELAYS[index]
    jitter = random.uniform(0, base_delay * 0.2)  # noqa: S311
    return timezone.now() + timedelta(seconds=base_delay + jitter)


def check_circuit_breaker(endpoint: WebhookEndpoint) -> bool:
    """
    Returns True if delivery should proceed.
    - If endpoint.is_active: proceed
    - If not active and disabled_at is None: skip (manually disabled)
    - If not active and disabled_at + 1 hour < now: proceed (probe)
    - Otherwise: skip
    """
    if endpoint.is_active:
        return True
    if endpoint.disabled_at is None:
        return False
    return endpoint.disabled_at + CIRCUIT_BREAKER_COOLDOWN < timezone.now()


def handle_circuit_breaker_trip(endpoint: WebhookEndpoint) -> None:
    """If failure_count >= 5: set is_active=False, disabled_at=now."""
    if endpoint.failure_count >= CIRCUIT_BREAKER_THRESHOLD:
        endpoint.is_active = False
        endpoint.disabled_at = timezone.now()
        endpoint.save()
