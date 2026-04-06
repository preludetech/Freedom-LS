from django.contrib.sites.models import Site
from django.tasks import default_task_backend, task

from freedom_ls.site_aware_models.models import _thread_locals, get_cached_site
from freedom_ls.webhooks.delivery import attempt_delivery, check_circuit_breaker
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from freedom_ls.webhooks.registry import validate_event_type


def fire_webhook_event(event_type: str, payload: dict[str, object]) -> None:
    """
    Fire a webhook event. Silently returns if called outside a request context
    (e.g. management commands, shell, data migrations).

    1. Validate event_type against registry
    2. Capture site_id from current request context (or return early)
    3. Create WebhookEvent record (with explicit site_id)
    4. Enqueue dispatch_event task with event_id and site_id
    """
    validate_event_type(event_type)

    request = getattr(_thread_locals, "request", None)
    if request is None:
        return
    site_result = get_cached_site(request)
    if not isinstance(site_result, Site):
        return
    site_id: int = site_result.pk

    event = WebhookEvent.objects.create(
        event_type=event_type,
        payload=payload,
        site_id=site_id,
    )
    default_task_backend.enqueue(
        _dispatch_event_task,
        args=[str(event.pk), site_id],
        kwargs={},
    )


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
    try:
        event = WebhookEvent.objects.get(pk=event_id)
    except WebhookEvent.DoesNotExist:
        return

    # Filter explicitly by site_id since we have no request context.
    # Only include user-enabled endpoints subscribed to this event type.
    # Circuit-broken endpoints still have is_active=True; check_circuit_breaker()
    # handles probe gating.
    endpoints = WebhookEndpoint.objects.filter(
        site_id=site_id,
        is_active=True,
        event_types__contains=[event.event_type],
    )

    for endpoint in endpoints:
        if not check_circuit_breaker(endpoint):
            continue

        delivery = WebhookDelivery.objects.create(
            event=event,
            endpoint=endpoint,
            status="pending",
            site_id=site_id,
        )
        attempt_delivery(delivery)
