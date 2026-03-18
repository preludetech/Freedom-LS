import json
import random
import time
from datetime import datetime, timedelta

import httpx
import jinja2

from django.db.models import F
from django.utils import timezone

from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from freedom_ls.webhooks.rendering import (
    build_event_envelope,
    build_template_context,
    render_template,
)
from freedom_ls.webhooks.signing import sign_webhook

RETRY_DELAYS = [60, 300, 1800, 7200, 43200]  # seconds
MAX_ATTEMPTS = 6  # initial + 5 retries
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN = timedelta(hours=1)
REQUEST_TIMEOUT = 30  # seconds


def build_webhook_payload(event: WebhookEvent) -> str:
    """Build the JSON envelope: {id, type, timestamp, data}."""
    envelope = build_event_envelope(event)
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


def build_standard_request(
    endpoint: WebhookEndpoint, event: WebhookEvent
) -> tuple[str, str, dict[str, str]]:
    """Returns (method, body, headers) for standard webhook format."""
    body = build_webhook_payload(event)
    headers = build_webhook_headers(body, endpoint, event)
    return "POST", body, headers


def build_transformed_request(
    endpoint: WebhookEndpoint, event: WebhookEvent
) -> tuple[str, str, dict[str, str]]:
    """Returns (method, body, headers) for a transformed endpoint.

    Raises jinja2.TemplateError on rendering failure.
    Raises json.JSONDecodeError if headers_template renders to invalid JSON.
    """
    context = build_template_context(event, endpoint.site_id)

    body = render_template(endpoint.body_template, context)

    method = endpoint.http_method or "POST"
    content_type = endpoint.content_type or "application/json"

    headers: dict[str, str] = {"Content-Type": content_type}

    if endpoint.auth_type == "signing":
        timestamp = int(time.time())
        webhook_id = str(event.pk)
        signature = sign_webhook(
            body=body,
            secret=endpoint.secret,
            webhook_id=webhook_id,
            timestamp=timestamp,
        )
        headers["webhook-id"] = webhook_id
        headers["webhook-timestamp"] = str(timestamp)
        headers["webhook-signature"] = signature

    if endpoint.headers_template:
        rendered_headers_str = render_template(endpoint.headers_template, context)
        rendered_headers = json.loads(rendered_headers_str)
        headers.update(rendered_headers)

    return method, body, headers


def attempt_delivery(delivery: WebhookDelivery) -> None:
    """
    Send HTTP request to the endpoint URL.
    Classifies response and updates delivery/endpoint records accordingly.
    """
    endpoint = delivery.endpoint
    event = delivery.event

    try:
        if endpoint.has_transformation:
            method, body, headers = build_transformed_request(endpoint, event)
        else:
            method, body, headers = build_standard_request(endpoint, event)
    except (jinja2.TemplateError, json.JSONDecodeError) as exc:
        delivery.attempt_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.last_response_error_message = f"Template rendering failed: {exc}"
        delivery.status = "permanent_failure"
        delivery.save()
        return

    response: httpx.Response | None = None
    start_time = time.monotonic()

    error_message = ""
    try:
        response = httpx.request(
            method=method,
            url=endpoint.url,
            content=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        error_message = f"Timeout after {REQUEST_TIMEOUT}s: {exc}"
    except httpx.TransportError as exc:
        error_message = f"Transport error: {exc}"

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    status_code = response.status_code if response is not None else None

    delivery.attempt_count += 1
    delivery.last_status_code = status_code
    delivery.last_response_body = response.text if response is not None else ""
    delivery.last_attempt_at = timezone.now()
    delivery.last_latency_ms = elapsed_ms
    delivery.last_response_error_message = error_message

    if response is not None and 200 <= response.status_code < 300:
        _handle_success(delivery, endpoint)
    elif response is not None and response.status_code == 429:
        retry_after = _parse_retry_after(response)
        _handle_retryable_failure(delivery, endpoint, retry_after=retry_after)
    elif response is not None and 400 <= response.status_code < 500:
        _handle_permanent_failure(delivery, endpoint)
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
    """Mark delivery as successful and reset endpoint circuit breaker state."""
    delivery.status = "success"
    delivery.next_retry_at = None
    WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
        failure_count=0, disabled_at=None
    )


def _handle_permanent_failure(
    delivery: WebhookDelivery, endpoint: WebhookEndpoint
) -> None:
    """Mark delivery as permanently failed (4xx except 429)."""
    delivery.status = "permanent_failure"
    delivery.next_retry_at = None
    _increment_failure_count_and_check_breaker(endpoint)


def _handle_retryable_failure(
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint,
    retry_after: int | None = None,
) -> None:
    """Handle a retryable failure: schedule retry or mark dead letter."""
    _increment_failure_count_and_check_breaker(endpoint)

    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "dead_letter"
        delivery.next_retry_at = None
    else:
        delivery.status = "failed"
        if retry_after is not None:
            delivery.next_retry_at = timezone.now() + timedelta(seconds=retry_after)
        else:
            delivery.next_retry_at = calculate_next_retry(delivery.attempt_count)


def _increment_failure_count_and_check_breaker(
    endpoint: WebhookEndpoint,
) -> None:
    """Atomically increment failure_count and trip circuit breaker if threshold reached."""
    WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
        failure_count=F("failure_count") + 1
    )
    endpoint.refresh_from_db()
    if endpoint.failure_count >= CIRCUIT_BREAKER_THRESHOLD:
        endpoint.disabled_at = timezone.now()
        endpoint.save()


def calculate_next_retry(attempt_count: int) -> datetime:
    """Base delay from RETRY_DELAYS + random jitter up to 20%."""
    index = min(attempt_count - 1, len(RETRY_DELAYS) - 1)
    base_delay = RETRY_DELAYS[index]
    jitter = random.uniform(0, base_delay * 0.2)  # noqa: S311 — jitter for retry timing, not crypto
    return timezone.now() + timedelta(seconds=base_delay + jitter)


def check_circuit_breaker(endpoint: WebhookEndpoint) -> bool:
    """
    Returns True if delivery should proceed.
    - is_active=False: user disabled — never deliver
    - disabled_at is None: active and healthy — proceed
    - disabled_at + cooldown < now: circuit-broken but cooldown expired — probe
    - Otherwise: circuit-broken within cooldown — skip
    """
    if not endpoint.is_active:
        return False
    if endpoint.disabled_at is None:
        return True
    return endpoint.disabled_at + CIRCUIT_BREAKER_COOLDOWN < timezone.now()
