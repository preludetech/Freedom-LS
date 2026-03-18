import json

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from freedom_ls.base.webhook_event_types import (
    FLS_WEBHOOK_EVENT_TYPES,
    WEBHOOK_EVENT_TYPE_SAMPLES,
)
from freedom_ls.webhooks.delivery import (
    _build_standard_request,
    _build_transformed_request,
    attempt_delivery,
)
from freedom_ls.webhooks.models import (
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    WebhookSecret,
)
from freedom_ls.webhooks.registry import validate_event_type


def send_test_form_view(request: HttpRequest, object_id: str) -> HttpResponse:
    """Show a form to select an event type and send a test webhook."""
    endpoint = get_object_or_404(WebhookEndpoint, pk=object_id)
    event_type_choices = [(code, label) for code, label in FLS_WEBHOOK_EVENT_TYPES]
    context = {
        "endpoint": endpoint,
        "event_type_choices": event_type_choices,
        "title": f"Send Test Webhook: {endpoint.description}",
        "result_url": reverse(
            "admin:webhooks_webhookendpoint_send_test_result",
            args=[object_id],
        ),
        **_admin_context(),
    }
    return render(request, "admin/webhooks/send_test_form.html", context)


@require_POST
def send_test_result_view(request: HttpRequest, object_id: str) -> HttpResponse:
    """Process the test webhook send and display results."""
    endpoint = get_object_or_404(WebhookEndpoint, pk=object_id)
    event_type = request.POST.get("event_type", "")

    # Validate event_type against the registry
    try:
        validate_event_type(event_type)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    # Build sample payload from WEBHOOK_EVENT_TYPE_SAMPLES
    sample_data = WEBHOOK_EVENT_TYPE_SAMPLES.get(event_type, {})
    payload = {**sample_data, "_test": True}

    # Create the WebhookEvent
    event = WebhookEvent.objects.create(
        event_type=event_type,
        payload=payload,
        site_id=endpoint.site_id,
    )

    # Create the WebhookDelivery
    delivery = WebhookDelivery.objects.create(
        event=event,
        endpoint=endpoint,
        status="pending",
        site_id=endpoint.site_id,
    )

    # Build request preview for display
    request_preview = _build_request_preview(event, endpoint)

    # Attempt delivery
    attempt_delivery(delivery)
    delivery.refresh_from_db()

    back_url = reverse(
        "admin:webhooks_webhookendpoint_change",
        args=[object_id],
    )

    context = {
        "endpoint": endpoint,
        "event": event,
        "delivery": delivery,
        "request_preview": request_preview,
        "title": f"Test Result: {endpoint.description}",
        "back_url": back_url,
        **_admin_context(),
    }
    return render(request, "admin/webhooks/send_test_result.html", context)


def _build_request_preview(
    event: WebhookEvent, endpoint: WebhookEndpoint
) -> dict[str, str]:
    """Build a preview of the request (standard or transformed) with masked secrets."""
    if endpoint.has_transformation:
        method, body, headers = _build_transformed_request(endpoint, event)
    else:
        method, body, headers = _build_standard_request(endpoint, event)

    # Mask secret values in headers for display
    secret_values = set(
        WebhookSecret.objects.filter(site_id=endpoint.site_id)
        .only("encrypted_value")
        .values_list("encrypted_value", flat=True)
    )
    masked_headers: dict[str, str] = {}
    for key, value in headers.items():
        masked_headers[key] = _mask_secrets(str(value), secret_values)

    return {
        "method": method,
        "url": endpoint.url,
        "headers": json.dumps(masked_headers, indent=2),
        "body": body,
    }


def _mask_secrets(value: str, secret_values: set[str]) -> str:
    """Replace secret values in a string with masked versions."""
    for secret_value in sorted(secret_values, key=len, reverse=True):
        if secret_value and secret_value in value:
            if len(secret_value) >= 4:
                masked = (
                    "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
                    + secret_value[-4:]
                )
            else:
                masked = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
            value = value.replace(secret_value, masked)
    return value


def _admin_context() -> dict[str, bool | str]:
    """Return common admin template context."""
    return {
        "is_popup": False,
        "has_permission": True,
        "site_header": "Freedom LS Admin",
    }
