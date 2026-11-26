"""The admin side of force delete: permission, entry points and the confirmation page."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import Protocol, cast
from urllib.parse import urlencode

from unfold.decorators import action as unfold_action
from unfold.enums import ActionVariant
from unfold.widgets import UnfoldAdminTextareaWidget

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.translation import ngettext

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.audit_log.writer import acting_user
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.force_delete import (
    ForceDeleteBlockedError,
    ForceDeletePlan,
    build_plan,
    force_delete_learners,
    force_delete_users,
    learner_progress_roots,
    user_progress_roots,
)
from freedom_ls.site_aware_models.admin import admin_page_context, ids_from

ActionEntry = tuple[Callable[..., str], str, str]
PlanBuilder = Callable[[Sequence[Model], HttpRequest, AdminSite], ForceDeletePlan]

FORCE_DELETE_MAX_SELECTION = 500


class ForceDeleter(Protocol):
    def __call__(
        self,
        targets: Sequence[Model],
        *,
        actor: User,
        reason: str,
        request: HttpRequest,
        admin_site: AdminSite,
    ) -> int: ...


@dataclass(frozen=True)
class ForceDeleteTarget:
    """What differs between the models a force delete runs on."""

    noun: str
    noun_plural: str
    plan: PlanBuilder
    delete: ForceDeleter
    # The name a row goes by on the confirmation page.
    label: Callable[[Model], str]
    # Where a single row is deactivated instead of deleted.
    deactivate_url: Callable[[Model], str]
    # A sentence naming what a force delete of this model leaves in place.
    stays: str = ""
    # A sentence naming what deactivating this model does not stop.
    deactivate_note: str = ""
    # Relations the confirmation page reads for every row.
    select_related: tuple[str, ...] = ()


class ForceDeleteForm(forms.Form):
    # CharField strips by default, so whitespace only fails `required`.
    reason = forms.CharField(max_length=REASON_LENGTH, widget=UnfoldAdminTextareaWidget)


def force_delete_url_name(model: type[Model]) -> str:
    return f"{model._meta.app_label}_{model._meta.model_name}_force_delete"


def _admin_url_name(model: type[Model], page: str) -> str:
    return f"admin:{model._meta.app_label}_{model._meta.model_name}_{page}"


def _force_delete_url(model: type[Model], ids: Iterable[object]) -> str:
    url = reverse(f"admin:{force_delete_url_name(model)}")
    return f"{url}?{urlencode({'ids': ','.join(str(pk) for pk in ids)})}"


def may_force_delete(request: HttpRequest) -> bool:
    return bool(request.user.is_superuser)


class ForceDeleteAdminMixin:
    """Force delete for a model admin: a button, a view and a permission.

    A plain class, not a `ModelAdmin` subclass, so a concrete admin lists it
    before its own base. The admin sets `force_delete_target`.
    """

    force_delete_target: ForceDeleteTarget

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
                name=force_delete_url_name(model_admin.model),
            )
        ]
        return custom + list(cast(ModelAdmin, super()).get_urls())

    def get_actions(self, request: HttpRequest) -> dict[str, ActionEntry | None]:
        actions = dict(cast(ModelAdmin, super()).get_actions(request))
        entry = actions.get("force_delete_selected")
        if entry is not None:
            func, name, _ = entry
            noun_plural = self.force_delete_target.noun_plural
            actions["force_delete_selected"] = (
                func,
                name,
                f"Force delete selected {noun_plural}",
            )
        return actions

    @unfold_action(
        description="Force delete",
        url_path="force-delete-one",
        permissions=["force_delete"],
        variant=ActionVariant.DANGER,
    )
    def force_delete_one(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        model = cast(ModelAdmin, self).model
        return redirect(_force_delete_url(model, [object_id]))

    @admin.action(description="Force delete selected", permissions=["force_delete"])
    def force_delete_selected(
        self, request: HttpRequest, queryset: QuerySet[Model]
    ) -> HttpResponseRedirect | None:
        # The ids travel in the confirmation page's URL, so the selection is capped.
        if queryset.count() > FORCE_DELETE_MAX_SELECTION:
            cast(ModelAdmin, self).message_user(
                request,
                f"Select at most {FORCE_DELETE_MAX_SELECTION} "
                f"{self.force_delete_target.noun_plural} to force delete at once.",
                level=messages.ERROR,
            )
            return None
        return redirect(
            _force_delete_url(queryset.model, queryset.values_list("pk", flat=True))
        )


def force_delete_view(request: HttpRequest, *, model_admin: ModelAdmin) -> HttpResponse:
    """Confirm on GET, force delete on POST, for the rows named by `ids`.

    admin_view supplies login and CSRF; the permission is checked here
    because this URL can be typed by hand.
    """
    if not may_force_delete(request):
        raise PermissionDenied
    target = cast(ForceDeleteAdminMixin, model_admin).force_delete_target
    model = model_admin.model
    # The admin queryset is filtered to the host's site, so another site's
    # row is a 404 whichever way its id arrives.
    targets = list(
        model_admin.get_queryset(request)
        .filter(pk__in=ids_from(request, model))
        .select_related(*target.select_related)
    )
    if not targets:
        raise Http404
    plan = target.plan(targets, request, model_admin.admin_site)
    form = ForceDeleteForm(request.POST or None)
    if request.method == "POST" and plan.can_run and form.is_valid():
        # Read before the delete: a user target may be the actor's own account.
        actor = acting_user(request)
        try:
            count = target.delete(
                targets,
                actor=actor,
                reason=form.cleaned_data["reason"],
                request=request,
                admin_site=model_admin.admin_site,
            )
        except ForceDeleteBlockedError as blocked:
            # A model began to block between the page and the post.
            plan = replace(plan, blocking_models=blocked.blocking_models)
        else:
            model_admin.message_user(
                request,
                ngettext(
                    "Force deleted %(count)d %(noun)s.",
                    "Force deleted %(count)d %(noun_plural)s.",
                    count,
                )
                % {
                    "count": count,
                    "noun": target.noun,
                    "noun_plural": target.noun_plural,
                },
            )
            return redirect(reverse(_admin_url_name(model, "changelist")))
    change_name = _admin_url_name(model, "change")
    context = {
        "targets": targets,
        "noun": target.noun,
        "noun_plural": target.noun_plural,
        "stays": target.stays,
        "deactivate_note": target.deactivate_note,
        "deactivate_url": target.deactivate_url(targets[0])
        if len(targets) == 1
        else "",
        "plan": plan,
        "form": form,
        "ids": ",".join(str(row.pk) for row in targets),
        "acting_on_self": model is User
        and any(row.pk == request.user.pk for row in targets),
        "cancel_url": _back_url(model, targets),
        "change_urls": [
            (target.label(row), reverse(change_name, args=[row.pk])) for row in targets
        ],
        **admin_page_context(
            request, model_admin, f"Force delete {target.noun_plural}"
        ),
    }
    return TemplateResponse(
        request,
        "admin/learner_progress/force_delete_confirm.html",
        context,
        status=422 if request.method == "POST" else 200,
    )


def user_plan(
    users: Sequence[Model], request: HttpRequest, admin_site: AdminSite
) -> ForceDeletePlan:
    return build_plan(
        targets=users,
        progress_roots=user_progress_roots(cast(Sequence[User], users)),
        request=request,
        admin_site=admin_site,
        unlinked_for=cast(Sequence[User], users),
    )


def learner_plan(
    learners: Sequence[Model], request: HttpRequest, admin_site: AdminSite
) -> ForceDeletePlan:
    return build_plan(
        targets=learners,
        progress_roots=learner_progress_roots(cast(Sequence[Learner], learners)),
        request=request,
        admin_site=admin_site,
    )


def _delete_users(
    targets: Sequence[Model],
    *,
    actor: User,
    reason: str,
    request: HttpRequest,
    admin_site: AdminSite,
) -> int:
    return force_delete_users(
        cast(Sequence[User], targets),
        actor=actor,
        reason=reason,
        request=request,
        admin_site=admin_site,
    )


def _delete_learners(
    targets: Sequence[Model],
    *,
    actor: User,
    reason: str,
    request: HttpRequest,
    admin_site: AdminSite,
) -> int:
    return force_delete_learners(
        cast(Sequence[Learner], targets),
        actor=actor,
        reason=reason,
        request=request,
        admin_site=admin_site,
    )


def _learner_page_url(row: Model) -> str:
    # Learners are deactivated in the educator interface; their admin is read-only.
    learner = cast(Learner, row)
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": learner.organisation.slug,
            "path_string": f"learners/{learner.pk}",
        },
    )


USER_TARGET = ForceDeleteTarget(
    noun="user",
    noun_plural="users",
    plan=user_plan,
    delete=_delete_users,
    label=lambda row: cast(User, row).display_name,
    deactivate_url=lambda row: reverse(_admin_url_name(User, "change"), args=[row.pk]),
)
LEARNER_TARGET = ForceDeleteTarget(
    noun="learner",
    noun_plural="learners",
    plan=learner_plan,
    delete=_delete_learners,
    label=lambda row: cast(Learner, row).user.display_name,
    deactivate_url=_learner_page_url,
    stays="The user account and their learner records in other organisations stay.",
    deactivate_note=(
        "Deactivating stops them using this organisation; "
        "their user account can still sign in."
    ),
    select_related=("user", "organisation"),
)


def _back_url(model: type[Model], targets: Sequence[Model]) -> str:
    # One row came from its change page; several came from the list.
    if len(targets) == 1:
        return reverse(_admin_url_name(model, "change"), args=[targets[0].pk])
    return reverse(_admin_url_name(model, "changelist"))
