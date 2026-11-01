from collections.abc import Iterable
from functools import partial
from urllib.parse import urlencode

from unfold.dataclasses import UnfoldAction
from unfold.decorators import action as unfold_action

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control

from freedom_ls.api.authentication import host_site
from freedom_ls.api.models import ApiKey
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api_admin.audit import acting_user, key_details
from freedom_ls.api_admin.filters import ApiKeyStatusFilter
from freedom_ls.api_admin.forms import ApiKeyAddForm
from freedom_ls.api_admin.views import revoke_view
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin, admin_page_context


def _revoke_url(ids: Iterable[object]) -> str:
    url = reverse("admin:freedom_ls_api_apikey_revoke")
    return f"{url}?{urlencode({'ids': ','.join(str(pk) for pk in ids)})}"


@admin.register(ApiKey)
class ApiKeyAdmin(SiteAwareModelAdmin):
    list_display = [
        "name",
        "key_prefix",
        "scope_list",
        "status",
        "expires_at",
        "last_used_at",
        "created_at",
    ]
    list_filter = [ApiKeyStatusFilter]
    search_fields = ["name", "key_prefix"]
    fields = [
        "name",
        "key_prefix",
        "scope_list",
        "status",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    readonly_fields = [
        "key_prefix",
        "scope_list",
        "status",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    actions = ["revoke_selected"]
    actions_detail = ["revoke_key"]

    def has_delete_permission(
        self, request: HttpRequest, obj: ApiKey | None = None
    ) -> bool:
        return False

    def get_readonly_fields(
        self, request: HttpRequest, obj: ApiKey | None = None
    ) -> list[str]:
        if obj is None:
            return []
        if not obj.is_active(timezone.now()):
            return list(self.fields)
        return list(self.readonly_fields)

    def get_actions_detail(
        self, request: HttpRequest, object_id: int
    ) -> list[UnfoldAction]:
        key = self.get_queryset(request).filter(pk=object_id).first()
        if key is None or not key.is_active(timezone.now()):
            return []
        actions: list[UnfoldAction] = super().get_actions_detail(request, object_id)
        return actions

    def get_urls(self) -> list[URLPattern]:
        custom = [
            path(
                "revoke/",
                self.admin_site.admin_view(partial(revoke_view, model_admin=self)),
                name="freedom_ls_api_apikey_revoke",
            )
        ]
        return custom + list(super().get_urls())

    @admin.action(description="Revoke selected keys")
    def revoke_selected(
        self, request: HttpRequest, queryset: QuerySet[ApiKey]
    ) -> HttpResponseRedirect:
        return redirect(_revoke_url(queryset.values_list("pk", flat=True)))

    @unfold_action(
        description="Revoke this key", url_path="revoke-key", permissions=["change"]
    )
    def revoke_key(self, request: HttpRequest, object_id: str) -> HttpResponseRedirect:
        return redirect(_revoke_url([object_id]))

    def get_form(
        self,
        request: HttpRequest,
        obj: ApiKey | None = None,
        change: bool = False,
        **kwargs: object,
    ) -> type[forms.ModelForm]:
        # The add form declares the scope checkboxes; the change form must not
        # inherit them, so the form is chosen per view rather than set once.
        if obj is None:
            kwargs["form"] = ApiKeyAddForm
        form_class: type[forms.ModelForm] = super().get_form(
            request, obj, change=change, **kwargs
        )
        return form_class

    def get_fields(self, request: HttpRequest, obj: ApiKey | None = None) -> list[str]:
        if obj is None:
            return list(ApiKeyAddForm.Meta.fields)
        fields: list[str] = super().get_fields(request, obj)
        return fields

    def save_model(
        self, request: HttpRequest, obj: ApiKey, form: forms.ModelForm, change: bool
    ) -> None:
        if change:
            super().save_model(request, obj, form, change)
            return
        site = host_site(request)
        if site is None:
            raise PermissionDenied("This host has no site to issue a key for.")
        actor = acting_user(request)
        obj.issued_key = ApiKey.issue(obj, site=site)
        record_entry(
            action="api_key.issued",
            actor=actor,
            target=obj,
            target_label=str(obj),
            organisation=None,
            details=key_details(obj),
        )

    def response_add(
        self, request: HttpRequest, obj: ApiKey, post_url_continue: str | None = None
    ) -> HttpResponse:
        # No redirect and no messages call: the key must be shown once, and
        # a message would store it in the messages cookie or the session.
        context = {
            "api_key": obj,
            "key_text": obj.issued_key,
            "changelist_url": reverse("admin:freedom_ls_api_apikey_changelist"),
            **admin_page_context(request, self, "API key issued"),
        }
        response = TemplateResponse(request, "admin/api_admin/key_issued.html", context)
        patch_cache_control(response, no_store=True)
        return response

    @admin.display(description="Scopes")
    def scope_list(self, obj: ApiKey) -> str:
        return ", ".join(ApiScope(scope).label for scope in obj.scopes)

    @admin.display(description="Status")
    def status(self, obj: ApiKey) -> str:
        return obj.status(timezone.now()).label
