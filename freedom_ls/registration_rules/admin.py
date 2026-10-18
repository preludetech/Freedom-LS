from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest, HttpResponse

from freedom_ls.registration_rules.models import RegistrationRule
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(RegistrationRule)
class RegistrationRuleAdmin(SiteAwareModelAdmin):
    list_display = ["name", "organisation", "course", "is_enabled", "last_evaluated_at"]
    list_filter = ["organisation", "is_enabled", "course"]
    list_select_related = ["organisation", "course"]
    search_fields = ["name"]
    autocomplete_fields = ["organisation", "course"]
    readonly_fields = ["last_evaluated_at", "created_at", "updated_at"]

    def get_fields(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> list[str]:
        # The add page takes the three things a rule cannot change afterwards.
        # Conditions and the switch wait for the change page, where the
        # organisation is known and a preview can be shown.
        if obj is None:
            return ["name", "organisation", "course"]
        return [
            "name",
            "organisation",
            "course",
            "is_enabled",
            "last_evaluated_at",
            "created_at",
            "updated_at",
        ]

    def get_readonly_fields(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> list[str]:
        readonly = list(super().get_readonly_fields(request, obj))
        # Changing either would silently retract one group and register
        # another. Staff disable the rule and make a new one instead.
        return readonly if obj is None else [*readonly, "organisation", "course"]

    def response_add(
        self,
        request: HttpRequest,
        obj: RegistrationRule,
        post_url_continue: str | None = None,
    ) -> HttpResponse:
        # Always on to the change page, where conditions are added. Forcing
        # "_continue" keeps the stock "added" message and redirect.
        post = request.POST.copy()
        post["_continue"] = "1"
        setattr(request, "POST", post)  # noqa: B010 - POST is typed read-only
        response: HttpResponse = super().response_add(request, obj, post_url_continue)
        return response
