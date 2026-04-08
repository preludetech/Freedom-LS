from django import forms
from django.contrib import admin
from django.http import HttpRequest

from freedom_ls.feedback.models import FeedbackDismissal, FeedbackForm, FeedbackResponse
from freedom_ls.feedback.registry import get_trigger_points
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(FeedbackForm)
class FeedbackFormAdmin(SiteAwareModelAdmin):
    list_display = [
        "name",
        "trigger_point",
        "is_active",
        "min_occurrences",
        "cooldown_days",
    ]
    list_filter = ["is_active", "trigger_point"]

    def get_form(
        self, request: HttpRequest, obj: FeedbackForm | None = None, **kwargs: object
    ) -> type[forms.ModelForm]:
        form_class: type[forms.ModelForm] = super().get_form(request, obj, **kwargs)
        choices = [("", "---------")] + [
            (k, f"{k} — {v}") for k, v in get_trigger_points().items()
        ]
        form_class.base_fields["trigger_point"].widget = forms.Select(choices=choices)
        return form_class


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(SiteAwareModelAdmin):
    list_display = ["form_name", "user", "rating", "created_at"]
    list_filter = ["form", "rating", "created_at"]
    list_select_related = ["form", "user"]
    search_fields = ["user__email"]
    readonly_fields = [
        "form",
        "user",
        "content_type",
        "object_id",
        "rating",
        "comment",
        "created_at",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: FeedbackResponse | None = None
    ) -> bool:
        return False

    @admin.display(description="Form")
    def form_name(self, obj: FeedbackResponse) -> str:
        return obj.form.name


@admin.register(FeedbackDismissal)
class FeedbackDismissalAdmin(SiteAwareModelAdmin):
    list_display = ["form_name", "user", "created_at"]
    list_filter = ["form", "created_at"]
    list_select_related = ["form", "user"]
    search_fields = ["user__email"]
    readonly_fields = [
        "form",
        "user",
        "content_type",
        "object_id",
        "created_at",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: FeedbackDismissal | None = None
    ) -> bool:
        return False

    @admin.display(description="Form")
    def form_name(self, obj: FeedbackDismissal) -> str:
        return obj.form.name
