"""The admin side of force delete: permission, entry points and the confirmation page."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import partial
from typing import cast
from urllib.parse import urlencode

from unfold.decorators import action as unfold_action
from unfold.enums import ActionVariant
from unfold.widgets import UnfoldAdminTextareaWidget

from django import forms
from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.translation import ngettext

from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.audit_log.writer import acting_user
from freedom_ls.learner_progress.force_delete import (
    ForceDeleteBlockedError,
    ForceDeletePlan,
    build_plan,
    force_delete_users,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.admin import admin_page_context, ids_from

FORCE_DELETE_URL_NAME = "freedom_ls_accounts_user_force_delete"


class ForceDeleteForm(forms.Form):
    # CharField strips by default, so whitespace only fails `required`.
    reason = forms.CharField(max_length=REASON_LENGTH, widget=UnfoldAdminTextareaWidget)


def _force_delete_url(ids: Iterable[object]) -> str:
    url = reverse(f"admin:{FORCE_DELETE_URL_NAME}")
    return f"{url}?{urlencode({'ids': ','.join(str(pk) for pk in ids)})}"


def may_force_delete(request: HttpRequest) -> bool:
    return bool(request.user.is_superuser)


class ForceDeleteAdminMixin:
    """Force delete for a model admin of users: a button, a view and a permission."""

    def has_force_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        # Unfold passes an object_id string for detail actions; the stock
        # action list passes nothing. Neither matters: only superusers.
        return may_force_delete(request)

    def get_urls(self) -> list[URLPattern]:
        model_admin = cast(ModelAdmin, self)
        # Before the stock patterns, or <path:object_id>/ swallows it.
        custom = [
            path(
                "force-delete/",
                model_admin.admin_site.admin_view(
                    partial(force_delete_view, model_admin=model_admin)
                ),
                name=FORCE_DELETE_URL_NAME,
            )
        ]
        return custom + list(cast(ModelAdmin, super()).get_urls())

    @unfold_action(
        description="Force delete",
        url_path="force-delete-one",
        permissions=["force_delete"],
        variant=ActionVariant.DANGER,
    )
    def force_delete_one(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        return redirect(_force_delete_url([object_id]))

    @admin.action(
        description="Force delete selected users", permissions=["force_delete"]
    )
    def force_delete_selected(
        self, request: HttpRequest, queryset: QuerySet[Model]
    ) -> HttpResponseRedirect:
        return redirect(_force_delete_url(queryset.values_list("pk", flat=True)))


def force_delete_view(request: HttpRequest, *, model_admin: ModelAdmin) -> HttpResponse:
    """Confirm on GET, force delete on POST, for the users named by `ids`.

    admin_view supplies login and CSRF; the permission is checked here
    because this URL can be typed by hand.
    """
    if not may_force_delete(request):
        raise PermissionDenied
    # The admin queryset is filtered to the host's site, so another site's
    # user is a 404 whichever way its id arrives.
    users = list(
        model_admin.get_queryset(request).filter(
            pk__in=ids_from(request, model_admin.model)
        )
    )
    if not users:
        raise Http404
    plan = _plan_for(users, request, model_admin.admin_site)
    form = ForceDeleteForm(request.POST or None)
    if request.method == "POST" and plan.can_run and form.is_valid():
        # Read before the delete: this may be the actor's own account.
        actor = acting_user(request)
        try:
            count = force_delete_users(
                users,
                actor=actor,
                reason=form.cleaned_data["reason"],
                request=request,
                admin_site=model_admin.admin_site,
            )
        except ForceDeleteBlockedError as blocked:
            # A model began to block between the page and the post.
            plan = ForceDeletePlan(plan.objects, blocked.blocking_models)
        else:
            model_admin.message_user(
                request,
                ngettext(
                    "Force deleted %(count)d user.",
                    "Force deleted %(count)d users.",
                    count,
                )
                % {"count": count},
            )
            return redirect(reverse("admin:freedom_ls_accounts_user_changelist"))
    context = {
        "users": users,
        "plan": plan,
        "form": form,
        "ids": ",".join(str(user.pk) for user in users),
        "acting_on_self": any(user.pk == request.user.pk for user in users),
        "cancel_url": _back_url(users),
        "change_urls": [
            (user, reverse("admin:freedom_ls_accounts_user_change", args=[user.pk]))
            for user in users
        ],
        **admin_page_context(request, model_admin, "Force delete users"),
    }
    return TemplateResponse(
        request,
        "admin/learner_progress/force_delete_confirm.html",
        context,
        status=422 if request.method == "POST" else 200,
    )


def _plan_for(
    users: Sequence[Model], request: HttpRequest, admin_site: AdminSite
) -> ForceDeletePlan:
    progress = list(CourseProgress._base_manager.filter(learner__user__in=users))
    return build_plan(
        targets=users,
        progress_roots=progress,
        request=request,
        admin_site=admin_site,
    )


def _back_url(users: Sequence[Model]) -> str:
    # One user came from their change page; several came from the list.
    if len(users) == 1:
        return reverse("admin:freedom_ls_accounts_user_change", args=[users[0].pk])
    return reverse("admin:freedom_ls_accounts_user_changelist")
