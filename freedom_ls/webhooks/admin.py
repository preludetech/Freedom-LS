from unfold.decorators import action as unfold_action

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import URLPattern, reverse

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from freedom_ls.webhooks.delivery import attempt_delivery
from freedom_ls.webhooks.forms import WebhookEndpointForm, WebhookSecretForm
from freedom_ls.webhooks.models import (
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    WebhookSecret,
)


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
    fieldsets = (
        (
            None,
            {
                "fields": ("description", "url", "event_types", "is_active"),
            },
        ),
        (
            "Transformation",
            {
                "fields": (
                    "preset_slug",
                    "http_method",
                    "content_type",
                    "auth_type",
                    "headers_template",
                    "body_template",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "secret",
                    "failure_count",
                    "disabled_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    actions = ["enable_endpoints", "disable_endpoints"]
    actions_detail = ["send_test_action"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: WebhookEndpoint | None = None
    ) -> list[str]:
        if obj is None:
            # On create form, exclude secret (it's auto-generated on save)
            return [f for f in self.readonly_fields if f != "secret"]
        return list(self.readonly_fields)

    def get_fieldsets(
        self, request: HttpRequest, obj: WebhookEndpoint | None = None
    ) -> list[tuple[str | None, dict[str, list[str]]]]:
        fieldsets: list[tuple[str | None, dict[str, list[str]]]] = (
            super().get_fieldsets(request, obj)
        )
        if obj is None:
            # On create, exclude secret (editable=False, auto-generated on save)
            return [
                (
                    name,
                    {
                        **options,
                        "fields": [f for f in options["fields"] if f != "secret"],
                    },
                )
                for name, options in fieldsets
            ]
        return fieldsets

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
        queryset.update(is_active=True, disabled_at=None, failure_count=0)

    @admin.action(description="Disable selected endpoints")
    def disable_endpoints(
        self, request: HttpRequest, queryset: QuerySet[WebhookEndpoint]
    ) -> None:
        queryset.update(is_active=False, disabled_at=None, failure_count=0)

    @unfold_action(description="Send Test", url_path="send-test-action")
    def send_test_action(self, request: HttpRequest, object_id: str) -> HttpResponse:
        url = reverse(
            "admin:webhooks_webhookendpoint_send_test_form",
            args=[object_id],
        )
        return redirect(url)

    def save_model(
        self,
        request: HttpRequest,
        obj: WebhookEndpoint,
        form: object,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        unknown_vars = obj.get_unknown_template_variables()
        if unknown_vars:
            sorted_vars = ", ".join(sorted(unknown_vars))
            messages.warning(
                request,
                f"Template uses unknown variables: {sorted_vars}. "
                f"Only 'event' and 'secrets' are available at render time.",
            )

    def get_urls(self) -> list[URLPattern]:
        from django.urls import path

        from freedom_ls.webhooks.views import send_test_form_view, send_test_result_view

        custom_urls = [
            path(
                "<path:object_id>/send-test/",
                self.admin_site.admin_view(send_test_form_view),
                name="webhooks_webhookendpoint_send_test_form",
            ),
            path(
                "<path:object_id>/send-test/result/",
                self.admin_site.admin_view(send_test_result_view),
                name="webhooks_webhookendpoint_send_test_result",
            ),
        ]
        return custom_urls + list(super().get_urls())


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
    list_select_related = ["event", "endpoint"]
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
        "last_response_error_message",
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
        retryable = queryset.filter(
            status__in=["failed", "permanent_failure", "dead_letter"]
        ).select_related("endpoint", "event")
        for delivery in retryable:
            delivery.attempt_count = 0
            delivery.status = "pending"
            delivery.save()
            attempt_delivery(delivery)


@admin.register(WebhookSecret)
class WebhookSecretAdmin(SiteAwareModelAdmin):
    form = WebhookSecretForm
    list_display = ["name", "description", "masked_value", "created_at", "updated_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["masked_value", "created_at", "updated_at"]

    @admin.display(description="Value")
    def masked_value(self, obj: WebhookSecret) -> str:
        value = obj.encrypted_value
        if value and len(value) >= 4:
            return "••••••••" + str(value[-4:])
        return "••••••••"
