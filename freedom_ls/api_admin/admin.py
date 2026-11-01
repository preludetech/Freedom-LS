from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control

from freedom_ls.api.authentication import host_site
from freedom_ls.api.models import ApiKey
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api_admin.forms import ApiKeyAddForm
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin, admin_page_context


def key_details(api_key: ApiKey) -> dict[str, JSONValue]:
    return {
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "scopes": list(api_key.scopes),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
    }


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
        actor = request.user
        if not isinstance(actor, get_user_model()):
            raise PermissionDenied("Only a signed-in user can issue a key.")
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
