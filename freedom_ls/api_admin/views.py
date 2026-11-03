from __future__ import annotations

from uuid import UUID

from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ngettext

from freedom_ls.api.models import ApiKey
from freedom_ls.api_admin.audit import acting_user, key_details
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.site_aware_models.admin import admin_page_context


def revoke_view(request: HttpRequest, *, model_admin: ModelAdmin) -> HttpResponse:
    """Confirm on GET, revoke on POST, for the keys named by `ids`.

    admin_view supplies login and CSRF; the change permission is checked
    here because neither the list action nor the detail button can be
    reached without it, and this URL can be typed by hand.
    """
    if not model_admin.has_change_permission(request):
        raise PermissionDenied
    # The admin queryset is filtered to the host's site, so another site's
    # key is a 404 whichever way its id arrives.
    keys = list(model_admin.get_queryset(request).filter(pk__in=_ids_from(request)))
    if not keys:
        raise Http404
    if request.method == "POST":
        count = _revoke(request, keys)
        if count == 0:
            # A stale confirmation page can still post keys revoked since.
            model_admin.message_user(
                request,
                "No API keys revoked: they were already revoked.",
                level=messages.WARNING,
            )
        else:
            message = ngettext(
                "Revoked %(count)d API key. Scripts using it stop at once.",
                "Revoked %(count)d API keys. Scripts using them stop at once.",
                count,
            )
            model_admin.message_user(request, message % {"count": count})
        return redirect(_back_url(keys))
    context = {
        "to_revoke": [key for key in keys if key.revoked_at is None],
        "already_revoked": [key for key in keys if key.revoked_at is not None],
        "ids": ",".join(str(key.pk) for key in keys),
        "cancel_url": _back_url(keys),
        **admin_page_context(request, model_admin, "Revoke API keys"),
    }
    return TemplateResponse(request, "admin/api_admin/revoke_confirm.html", context)


def _ids_from(request: HttpRequest) -> list[UUID]:
    source = request.POST if request.method == "POST" else request.GET
    try:
        return [UUID(part) for part in source.get("ids", "").split(",") if part]
    except ValueError as exc:
        raise Http404 from exc


def _revoke(request: HttpRequest, keys: list[ApiKey]) -> int:
    """Revoke the keys that are still live, under a row lock.

    The rows are re-read locked: `keys` came from before the confirmation
    page was shown, and a concurrent or repeated post of the same ids must
    not revoke and audit a key twice.
    """
    actor = acting_user(request)
    now = timezone.now()
    revoked = 0
    with transaction.atomic():
        locked = ApiKey._base_manager.filter(
            pk__in=[key.pk for key in keys]
        ).select_for_update()
        for key in locked:
            if key.revoked_at is not None:
                continue
            key.revoke(now)
            record_entry(
                action="api_key.revoked",
                actor=actor,
                target=key,
                target_label=str(key),
                organisation=None,
                details=key_details(key),
            )
            revoked += 1
    return revoked


def _back_url(keys: list[ApiKey]) -> str:
    # One key came from its change page; several came from the list.
    if len(keys) == 1:
        return reverse("admin:freedom_ls_api_apikey_change", args=[keys[0].pk])
    return reverse("admin:freedom_ls_api_apikey_changelist")
