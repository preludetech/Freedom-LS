from django.db import transaction
from django.tasks import default_task_backend, task  # type: ignore[import-untyped]

from freedom_ls.site_aware_models.models import _thread_locals, get_cached_site
from freedom_ls.webhooks.delivery import attempt_delivery, check_circuit_breaker
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from freedom_ls.webhooks.registry import validate_event_type


def fire_webhook_event(event_type: str, payload: dict[str, object]) -> None:
    """
    Fire a webhook event. Must be called within a request context.

    1. Validate event_type against registry
    2. Capture site_id from current request context
    3. Inside transaction.on_commit():
       a. Create WebhookEvent record (with explicit site_id)
       b. enqueue dispatch_event task with event_id and site_id
    """
    validate_event_type(event_type)

    request = getattr(_thread_locals, "request", None)
    if request is None:
        raise RuntimeError(
            "fire_webhook_event must be called within a request context."
        )
    site = get_cached_site(request)
    site_id: int = site.pk

    def _on_commit() -> None:
        event = WebhookEvent.objects.create(
            event_type=event_type,
            payload=payload,
            site_id=site_id,
        )
        default_task_backend.enqueue(
            _dispatch_event_task,
            args=(str(event.pk), site_id),
            kwargs={},
        )

    transaction.on_commit(_on_commit)


def send_test_ping(endpoint: WebhookEndpoint) -> None:
    """
    Send a webhook.test event to a specific endpoint.
    Bypasses registry validation. Creates a WebhookEvent with type='webhook.test'
    and a static payload {'ping': True}, then creates and attempts a single delivery.
    """
    event = WebhookEvent.objects.create(
        event_type="webhook.test",
        payload={"ping": True},
        site_id=endpoint.site_id,
    )
    delivery = WebhookDelivery.objects.create(
        event=event,
        endpoint=endpoint,
        status="pending",
        site_id=endpoint.site_id,
    )
    attempt_delivery(delivery)


@task()
def _dispatch_event_task(event_id: str, site_id: int) -> None:
    """Wrapper task for dispatch_event."""
    dispatch_event(event_id, site_id)


def dispatch_event(event_id: str, site_id: int) -> None:
    """
    Background task. Look up all active WebhookEndpoint records for the given
    site_id that subscribe to the event type. Filter explicitly by site_id
    (cannot use SiteAwareManager — no request context in background tasks).

    For each matching endpoint:
    - Check circuit breaker
    - Create WebhookDelivery(status='pending')
    - Call attempt_delivery(delivery)
    """
    event = WebhookEvent.objects.get(pk=event_id)

    # Filter explicitly by site_id since we have no request context
    endpoints = WebhookEndpoint.objects.filter(site_id=site_id)

    for endpoint in endpoints:
        if event.event_type not in endpoint.event_types:
            continue

        if not check_circuit_breaker(endpoint):
            continue

        delivery = WebhookDelivery.objects.create(
            event=event,
            endpoint=endpoint,
            status="pending",
            site_id=site_id,
        )
        attempt_delivery(delivery)
