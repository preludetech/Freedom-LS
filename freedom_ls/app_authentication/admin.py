from django.contrib import admin
from .models import Client
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(Client)
class ClientAdmin(SiteAwareModelAdmin):
    list_display = ("name", "api_key_preview", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "api_key")
    readonly_fields = ("api_key", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "is_active")}),
        (
            "API Key",
            {
                "fields": ("api_key",),
                "description": "API key is automatically generated when the client is created.",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def api_key_preview(self, obj):
        """Show a preview of the API key (first 8 chars + ...)"""
        if obj.api_key:
            return f"{obj.api_key[:8]}..."
        return "-"

    api_key_preview.short_description = "API Key"
