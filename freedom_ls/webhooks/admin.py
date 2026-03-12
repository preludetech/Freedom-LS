from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from freedom_ls.webhooks.delivery import attempt_delivery
from freedom_ls.webhooks.events import send_test_ping
from freedom_ls.webhooks.forms import WebhookEndpointForm
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(SiteAwareModelAdmin):
    form = WebhookEndpointForm
    list_display = [
        "description",
        "url_truncated",
        "display_event_types",
        "is_active",
        "failure_count",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    readonly_fields = [
        "secret",
        "failure_count",
        "disabled_at",
        "created_at",
        "updated_at",
    ]
    actions = ["enable_endpoints", "disable_endpoints", "send_test_ping"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: WebhookEndpoint | None = None
    ) -> list[str]:
        if obj is None:
            # On create form, exclude secret (it's auto-generated on save)
            return [f for f in self.readonly_fields if f != "secret"]
        return list(self.readonly_fields)

    @admin.display(description="URL")
    def url_truncated(self, obj: WebhookEndpoint) -> str:
        url = obj.url
        if len(url) > 50:
            return url[:50] + "..."
        return url

    @admin.display(description="Event types")
    def display_event_types(self, obj: WebhookEndpoint) -> str:
        return ", ".join(obj.event_types)

    @admin.action(description="Enable selected endpoints")
    def enable_endpoints(
        self, request: HttpRequest, queryset: QuerySet[WebhookEndpoint]
    ) -> None:
        queryset.update(is_active=True)

    @admin.action(description="Disable selected endpoints")
    def disable_endpoints(
        self, request: HttpRequest, queryset: QuerySet[WebhookEndpoint]
    ) -> None:
        queryset.update(is_active=False)

    @admin.action(description="Send test ping")
    def send_test_ping(
        self, request: HttpRequest, queryset: QuerySet[WebhookEndpoint]
    ) -> None:
        for endpoint in queryset:
            send_test_ping(endpoint)


@admin.register(WebhookEvent)
class WebhookEventAdmin(SiteAwareModelAdmin):
    list_display = ["event_type", "short_id", "created_at"]
    list_filter = ["event_type", "created_at"]
    readonly_fields = ["event_type", "payload", "created_at"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: WebhookEvent | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: WebhookEvent | None = None
    ) -> bool:
        return False

    @admin.display(description="ID")
    def short_id(self, obj: WebhookEvent) -> str:
        return str(obj.pk)[:8]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(SiteAwareModelAdmin):
    list_display = [
        "event_type_display",
        "endpoint_truncated",
        "status",
        "attempt_count",
        "last_status_code",
        "last_attempt_at",
    ]
    list_filter = ["status", "endpoint", "event__event_type"]
    readonly_fields = [
        "event",
        "endpoint",
        "status",
        "attempt_count",
        "next_retry_at",
        "last_status_code",
        "last_response_body",
        "last_attempt_at",
        "last_latency_ms",
        "created_at",
    ]
    actions = ["retry_deliveries"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: WebhookDelivery | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: WebhookDelivery | None = None
    ) -> bool:
        return False

    @admin.display(description="Event type")
    def event_type_display(self, obj: WebhookDelivery) -> str:
        return obj.event.event_type

    @admin.display(description="Endpoint")
    def endpoint_truncated(self, obj: WebhookDelivery) -> str:
        url = obj.endpoint.url
        if len(url) > 50:
            return url[:50] + "..."
        return url

    @admin.action(description="Retry failed/dead-lettered deliveries")
    def retry_deliveries(
        self, request: HttpRequest, queryset: QuerySet[WebhookDelivery]
    ) -> None:
        retryable = queryset.filter(status__in=["failed", "dead_letter"])
        for delivery in retryable:
            attempt_delivery(delivery)
