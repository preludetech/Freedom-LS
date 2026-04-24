"""Read-only admin for browsing events.

Both models are append-only, so the admin returns ``False`` from every
``has_*_permission`` hook. All fields are listed in ``readonly_fields`` to
display detail without offering an edit path.
"""

from __future__ import annotations

from django.contrib import admin

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import ActorErasure, Event


@admin.register(Event)
class EventAdmin(SiteAwareModelAdmin):
    list_display = (
        "timestamp",
        "actor_email",
        "verb_display",
        "object_type",
        "object_definition_summary",
    )
    list_filter = ("verb", "object_type")
    date_hierarchy = "timestamp"
    search_fields = ("actor_email", "actor_display_name")
    # Every column except `site` (hidden by SiteAwareModelAdmin.exclude).
    readonly_fields = (
        "id",
        "site_domain",
        "actor_user",
        "actor_email",
        "actor_display_name",
        "actor_ifi",
        "verb",
        "verb_display",
        "object_type",
        "object_id",
        "object_definition",
        "result",
        "context",
        "statement",
        "timestamp",
        "stored",
        "session_id_hash",
        "user_agent",
        "ip_address",
        "platform",
    )

    @admin.display(description="object")
    def object_definition_summary(self, obj: Event) -> str:
        """Truncated display of the object_definition dict for list view."""
        d = obj.object_definition or {}
        # Prefer the snapshot's title / slug for readability.
        for key in ("topic_title", "form_title", "question_slug", "course_title"):
            if key in d:
                return str(d[key])[:80]
        return str(d)[:80]

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ActorErasure)
class ActorErasureAdmin(SiteAwareModelAdmin):
    list_display = (
        "timestamp",
        "target_user_id",
        "event_count",
        "invoking_os_user",
        "invoking_admin_user_id",
    )
    date_hierarchy = "timestamp"
    readonly_fields = (
        "id",
        "target_user_id",
        "erased_token",
        "event_count",
        "timestamp",
        "invoking_os_user",
        "invoking_hostname",
        "invoking_admin_user_id",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
