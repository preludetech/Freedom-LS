"""Read-only admins for the two referral-tracking models."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.referral_tracking.exports import export_as_csv
from freedom_ls.referral_tracking.models import FirstTouchCount, SignupAttribution
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


def _readonly_field_names(model: type[Model]) -> list[str]:
    return [f.name for f in model._meta.fields if f.name not in ("id", "site")]


@admin.register(SignupAttribution)
class SignupAttributionAdmin(SiteAwareModelAdmin):
    date_hierarchy = "signed_up_at"
    list_display = [
        "user",
        "advert_code",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "first_seen",
        "signed_up_at",
    ]
    list_select_related = ["user"]
    list_filter = ["utm_source", "utm_medium", "utm_campaign"]
    search_fields = ["user__email", "utm_campaign", "advert_code"]
    readonly_fields = _readonly_field_names(SignupAttribution)
    actions = [export_as_csv]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: SignupAttribution | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: SignupAttribution | None = None
    ) -> bool:
        return False


@admin.register(FirstTouchCount)
class FirstTouchCountAdmin(SiteAwareModelAdmin):
    date_hierarchy = "day"
    list_display = [
        "day",
        "advert_code",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "is_overflow",
        "count",
    ]
    list_filter = ["utm_source", "utm_medium", "utm_campaign", "is_overflow"]
    search_fields = ["utm_campaign", "advert_code"]
    readonly_fields = _readonly_field_names(FirstTouchCount)
    actions = [export_as_csv]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: FirstTouchCount | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: FirstTouchCount | None = None
    ) -> bool:
        return False
