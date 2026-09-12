"""Admins for the referral-tracking models.

`SignupAttribution` and `FirstTouchCount` are read-only. `ReferralCode` is
writable, with a copy button on its two absolute URLs and a bulk deactivate
action. `ReferralCodeHit` is read-only, like the first two.
"""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.urls import NoReverseMatch
from django.utils.html import format_html

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.referral_tracking.codes import (
    absolute_code_url,
    build_redirect_url,
    inactive_destination_for,
)
from freedom_ls.referral_tracking.forms import ReferralCodeForm
from freedom_ls.referral_tracking.models import (
    Door,
    FirstTouchCount,
    ReferralCode,
    ReferralCodeHit,
    SignupAttribution,
)
from freedom_ls.referral_tracking.resources import (
    FirstTouchCountResource,
    ReferralCodeHitResource,
    ReferralCodeResource,
    SignupAttributionResource,
)
from freedom_ls.site_aware_models.admin import SiteAwareExportModelAdmin

UNSAVED_MESSAGE = "Shown once the code is saved."
UNREVERSABLE_CODE_MESSAGE = (
    "This code predates the current rules and has no working link."
)


def _readonly_field_names(model: type[Model]) -> list[str]:
    return [f.name for f in model._meta.fields if f.name not in ("id", "site")]


@admin.register(SignupAttribution)
class SignupAttributionAdmin(SiteAwareExportModelAdmin):
    date_hierarchy = "signed_up_at"
    list_display = [
        "user",
        "advert_code",
        "referral_code",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "first_seen",
        "signed_up_at",
    ]
    list_select_related = ["user"]
    list_filter = ["utm_source", "utm_medium", "utm_campaign"]
    search_fields = ["user__email", "utm_campaign", "advert_code", "referral_code"]
    readonly_fields = _readonly_field_names(SignupAttribution)
    resource_classes = [SignupAttributionResource]

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


USER_ERASURE_CASCADE_MODELS.add(SignupAttribution)


@admin.register(FirstTouchCount)
class FirstTouchCountAdmin(SiteAwareExportModelAdmin):
    date_hierarchy = "day"
    list_display = [
        "day",
        "advert_code",
        "referral_code",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "is_overflow",
        "count",
    ]
    list_filter = ["utm_source", "utm_medium", "utm_campaign", "is_overflow"]
    search_fields = ["utm_campaign", "advert_code", "referral_code"]
    readonly_fields = _readonly_field_names(FirstTouchCount)
    resource_classes = [FirstTouchCountResource]

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


@admin.register(ReferralCode)
class ReferralCodeAdmin(SiteAwareExportModelAdmin):
    form = ReferralCodeForm
    list_display = [
        "code",
        "label",
        "destination",
        "is_active",
        "hit_count",
        "last_hit_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["code", "label", "notes"]
    readonly_fields = [
        "go_url",
        "d_url",
        "destination_preview",
        "inactive_destination_preview",
        "hit_count",
        "last_hit_at",
        "created_at",
    ]
    fields = [
        "code",
        "label",
        "notes",
        "destination",
        "inactive_destination",
        "is_active",
        "go_url",
        "d_url",
        "destination_preview",
        "inactive_destination_preview",
        "hit_count",
        "last_hit_at",
        "created_at",
    ]
    actions = ["deactivate_referral_codes"]
    resource_classes = [ReferralCodeResource]

    class Media:
        css = {"all": ["referral_tracking/css/copy_button.css"]}
        js = ["referral_tracking/js/copy_button.js"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: ReferralCode | None = None
    ) -> list[str]:
        # `code` is only read-only once a row exists: the text is reserved
        # for good the moment it is saved, so the add form is the one
        # chance to type or generate it.
        return (
            [*self.readonly_fields, "code"]
            if obj is not None
            else list(self.readonly_fields)
        )

    def has_delete_permission(
        self, request: HttpRequest, obj: ReferralCode | None = None
    ) -> bool:
        return False

    @admin.action(description="Deactivate selected referral codes")
    def deactivate_referral_codes(
        self, request: HttpRequest, queryset: QuerySet[ReferralCode]
    ) -> None:
        changed = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {changed} referral code(s).")

    @admin.display(description="Go URL")
    def go_url(self, obj: ReferralCode) -> str:
        return self._copyable_url(obj, Door.GO)

    @admin.display(description="D URL")
    def d_url(self, obj: ReferralCode) -> str:
        return self._copyable_url(obj, Door.D)

    @admin.display(description="Destination preview")
    def destination_preview(self, obj: ReferralCode) -> str:
        if obj._state.adding:
            return UNSAVED_MESSAGE
        return build_redirect_url(obj, "", base=obj.destination)

    @admin.display(description="Inactive destination preview")
    def inactive_destination_preview(self, obj: ReferralCode) -> str:
        if obj._state.adding:
            return UNSAVED_MESSAGE
        preview = build_redirect_url(obj, "", base=inactive_destination_for(obj))
        return preview if obj.inactive_destination else f"{preview} (the default)"

    def _copyable_url(self, obj: ReferralCode, door: Door) -> str:
        if obj._state.adding:
            return UNSAVED_MESSAGE
        try:
            url = absolute_code_url(obj, door)
        except NoReverseMatch:
            # A code written past `full_clean()` (or saved under older,
            # looser rules) can fall outside `CODE_PATTERN`, and the URL
            # patterns exclude it too — there is no route to reverse.
            return UNREVERSABLE_CODE_MESSAGE
        element_id = f"referral-code-{door}-url"
        return format_html(
            '<span id="{}">{}</span> '
            '<button type="button" class="referral-code-copy" data-copy-target="{}" '
            'aria-label="Copy {} URL">Copy</button>',
            element_id,
            url,
            element_id,
            door.label,
        )


@admin.register(ReferralCodeHit)
class ReferralCodeHitAdmin(SiteAwareExportModelAdmin):
    list_display = [
        "hit_at",
        "referral_code",
        "referral_code_label",
        "door",
        "is_machine_fetch",
    ]
    list_select_related = ["referral_code"]
    list_filter = ["door", "is_machine_fetch"]
    date_hierarchy = "hit_at"
    ordering = ["-hit_at"]
    search_fields = ["referral_code__code", "referral_code__label"]
    readonly_fields = _readonly_field_names(ReferralCodeHit)
    resource_classes = [ReferralCodeHitResource]

    @admin.display(description="Label")
    def referral_code_label(self, obj: ReferralCodeHit) -> str:
        return obj.referral_code.label

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ReferralCodeHit | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ReferralCodeHit | None = None
    ) -> bool:
        return False
