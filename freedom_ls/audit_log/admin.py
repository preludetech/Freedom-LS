from django.contrib import admin
from django.http import HttpRequest

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(SiteAwareModelAdmin):
    """Browse and search entries. The log is append-only, so nothing here can
    add, change or delete one."""

    list_display = [
        "created_at",
        "actor_label",
        "action",
        "target_label",
        "organisation",
    ]
    list_filter = ["action", "organisation"]
    search_fields = ["actor_label", "target_label"]
    readonly_fields = [
        "id",
        "created_at",
        "organisation",
        "actor",
        "actor_label",
        "action",
        "target_content_type",
        "target_object_id",
        "target_label",
        "subjects",
        "reason",
        "details",
        "run_id",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: AuditLogEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: AuditLogEntry | None = None
    ) -> bool:
        return False
