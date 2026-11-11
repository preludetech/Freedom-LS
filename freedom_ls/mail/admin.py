"""Read-only admin for OutboundEmail. The stored message body is never rendered."""

from __future__ import annotations

from unfold.admin import ModelAdmin

from django.contrib import admin
from django.http import HttpRequest

from freedom_ls.mail.models import OutboundEmail

LAST_ERROR_LIST_LENGTH = 80


# Not a SiteAwareModelAdmin: that base filters on a site column OutboundEmail lacks.
@admin.register(OutboundEmail)
class OutboundEmailAdmin(ModelAdmin):
    list_display = [
        "recipients_display",
        "subject",
        "status",
        "attempt_count",
        "next_attempt_at",
        "last_attempt_at",
        "last_error_short",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["message_id", "subject", "recipients"]
    # payload is left out so the stored body is never rendered.
    fields = [
        "message_id",
        "recipients",
        "subject",
        "status",
        "attempt_count",
        "next_attempt_at",
        "last_attempt_at",
        "last_error",
        "created_at",
        "sent_at",
        "scrubbed_at",
        "body_notice",
    ]
    readonly_fields = fields

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OutboundEmail | None = None
    ) -> bool:
        return False

    @admin.display(description="Recipients")
    def recipients_display(self, obj: OutboundEmail) -> str:
        return ", ".join(obj.recipients)

    @admin.display(description="Last error")
    def last_error_short(self, obj: OutboundEmail) -> str:
        return obj.last_error[:LAST_ERROR_LIST_LENGTH]

    @admin.display(description="Body")
    def body_notice(self, obj: OutboundEmail) -> str:
        if obj.scrubbed_at is not None:
            return (
                "The body was removed. To send this email again, repeat the "
                "original action, such as a new password reset."
            )
        return "Stored until the email is sent or its retention period ends."
