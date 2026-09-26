from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from freedom_ls.panel_framework.context import PanelContext


class PanelAction:
    """A button on a panel, list or instance view, and what submitting it does.

    It renders through `template_name` with `get_context_data(ctx)`, and its
    URL is the owner's `ctx.base_url` plus `/__actions/<action_name>`.
    """

    label: str = ""
    variant: str = "primary"
    action_name: str = ""
    template_name: str = "panel_framework/partials/action_button.html"

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        return True

    def get_action_url(self, ctx: PanelContext) -> str:
        return f"{ctx.base_url}/__actions/{self.action_name}"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return {
            "label": self.label,
            "variant": self.variant,
            "action_url": self.get_action_url(ctx),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        """Process action submission. Override in subclasses."""
        raise NotImplementedError


class FormPanelAction(PanelAction):
    template_name = "panel_framework/partials/modal_form.html"
    form_class: Callable[..., forms.ModelForm]
    form_title: str = ""
    submit_buttons: list[dict[str, str]] = [
        {"label": "Save", "variant": "primary"},
    ]

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        data = request.POST if request.method == "POST" else None
        form = self.form_class(data, instance=instance)
        return form

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        """Process form submission."""
        self._last_form_url = self.get_action_url(ctx)
        form = self.get_form(ctx.request, ctx.instance)
        if form.is_valid():
            return self.form_valid(ctx.request, form)
        return self.form_invalid(ctx.request, form)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        raise NotImplementedError

    def form_invalid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        """Return 422 with re-rendered form."""
        html = render_to_string(
            self.template_name,
            {
                "form": form,
                "form_title": self.form_title,
                "form_url": self._last_form_url,
                "variant": self.variant,
                "label": self.label,
                "submit_buttons": self.submit_buttons,
                "modal_open": "True",
            },
            request=request,
        )
        return HttpResponse(html, status=422)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        """The trigger button and its modal, holding an unbound form."""
        return {
            "form": self.get_form(ctx.request),
            "form_title": self.form_title,
            "form_url": self.get_action_url(ctx),
            "variant": self.variant,
            "label": self.label,
            "submit_buttons": self.submit_buttons,
        }


class CreateInstanceAction(FormPanelAction):
    """Base class for actions that create a new instance via a modal form.

    Subclasses must define: form_class, form_title, label, action_name.
    Subclasses must implement: get_success_url(instance) and get_created_event_name().
    """

    variant: str = "primary"
    submit_buttons: list[dict[str, str]] = [
        {
            "label": "Save and add another",
            "variant": "secondary",
            "name": "action",
            "value": "save_and_add",
        },
        {"label": "Save", "variant": "primary"},
    ]

    def get_success_url(self, instance: Model) -> str:
        """Return the URL to redirect to after successful creation."""
        raise NotImplementedError

    def get_created_event_name(self) -> str:
        """Return the HTMX event name to trigger on 'save and add another'."""
        raise NotImplementedError

    def _render_empty_form(self, request: HttpRequest, form_url: str) -> str:
        """Re-render the modal form with an empty/unbound form."""
        form = self.form_class()
        return render_to_string(
            self.template_name,
            {
                "form": form,
                "form_title": self.form_title,
                "form_url": form_url,
                "variant": self.variant,
                "label": self.label,
                "submit_buttons": self.submit_buttons,
                "modal_open": "True",
            },
            request=request,
        )

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        meta = getattr(self.form_class, "Meta", None)
        if meta is None:
            raise ValueError("form_class must define a Meta class with model")
        model: type[Model] = meta.model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return request.user.has_perm(f"{app_label}.add_{model_name}")

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        instance = form.save()
        if request.POST.get("action") == "save_and_add":
            html = self._render_empty_form(request, self._last_form_url)
            response = HttpResponse(html)
            response["HX-Trigger"] = self.get_created_event_name()
            return response
        response = HttpResponse(status=204)
        response["HX-Redirect"] = self.get_success_url(instance)
        return response


class EditAction(FormPanelAction):
    label = "Edit"
    variant = "secondary"
    action_name = "edit"
    submit_buttons: list[dict[str, str]] = [
        {"label": "Save", "variant": "primary"},
    ]

    def __init__(
        self,
        form_class: Callable[..., forms.ModelForm],
        form_title: str,
        instance: Model,
    ) -> None:
        self.form_class = form_class
        self.form_title = form_title
        self._instance = instance

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        instance = instance or self._instance
        data = request.POST if request.method == "POST" else None
        form = self.form_class(data, instance=instance)
        return form

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        form.save()
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps(
            {"panelChanged": {"instanceTitle": str(form.instance)}}
        )
        return response

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        instance = instance or self._instance
        model_name = instance._meta.model_name
        app_label = instance._meta.app_label
        return request.user.has_perm(f"{app_label}.change_{model_name}", instance)


class DeleteAction(PanelAction):
    """Deletes the instance of whatever it is attached to, after confirmation."""

    label = "Delete"
    variant = "error"
    action_name = "delete"
    template_name = "panel_framework/partials/delete_confirmation.html"

    def __init__(self, success_url: str = ""):
        self.success_url = success_url

    def get_cascade_summary(self, instance: Model) -> list[str]:
        """Use Django's Collector to show what will be cascade-deleted.

        Raises ProtectedError when a protected relation blocks the delete, the
        same way the delete itself would. Callers rendering a preview catch it
        and show get_blocked_reason() in place of the summary.
        """
        from django.db.models.deletion import Collector

        db = instance._state.db or "default"
        collector = Collector(using=db)
        collector.collect([instance])
        summary = []
        for model, objs in collector.data.items():
            if model is not type(instance):
                count = len(objs)
                if count:
                    summary.append(f"{count} {model._meta.verbose_name_plural}")
        return summary

    def get_blocked_reason(self, instance: Model, error: ProtectedError) -> str:
        """One plain sentence naming what still depends on this instance."""
        counts: Counter[type[Model]] = Counter(
            type(obj) for obj in error.protected_objects
        )
        dependents: list[str] = []
        for model in sorted(counts, key=lambda m: str(m._meta.verbose_name)):
            count = counts[model]
            noun = (
                model._meta.verbose_name
                if count == 1
                else model._meta.verbose_name_plural
            )
            dependents.append(f"{count} {noun}")
        return (
            f"This {instance._meta.verbose_name} cannot be deleted because it "
            f"still has {self._join(dependents)}."
        )

    @staticmethod
    def _join(parts: list[str]) -> str:
        """Run a list into readable prose: a, then a and b, then a, b and c."""
        if len(parts) < 2:
            return "".join(parts)
        return f"{', '.join(parts[:-1])} and {parts[-1]}"

    def _confirmation_context(
        self,
        ctx: PanelContext,
        instance: Model,
        *,
        cascade_summary: list[str],
        blocked_reason: str,
        modal_open: bool = False,
    ) -> dict[str, object]:
        return {
            "instance": instance,
            "cascade_summary": cascade_summary,
            "blocked_reason": blocked_reason,
            "delete_url": self.get_action_url(ctx),
            "variant": self.variant,
            "modal_open": "true" if modal_open else "false",
        }

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        """The error-variant button and its confirmation modal.

        A delete that a protected relation would block renders the reason in
        place of the cascade summary, with no live delete button.
        """
        instance = ctx.instance
        if instance is None:
            raise ImproperlyConfigured("DeleteAction needs an instance to delete.")
        try:
            cascade = self.get_cascade_summary(instance)
        except ProtectedError as error:
            return self._confirmation_context(
                ctx,
                instance,
                cascade_summary=[],
                blocked_reason=self.get_blocked_reason(instance, error),
            )
        return self._confirmation_context(
            ctx, instance, cascade_summary=cascade, blocked_reason=""
        )

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        instance = ctx.instance
        if instance is None:
            return HttpResponse(status=400)
        try:
            instance.delete()
        except ProtectedError as error:
            # The render path hides the button, so reaching here means a stale
            # page or a hand-made request. Answer it the way a form does.
            html = render_to_string(
                self.template_name,
                self._confirmation_context(
                    ctx,
                    instance,
                    cascade_summary=[],
                    blocked_reason=self.get_blocked_reason(instance, error),
                    modal_open=True,
                ),
                request=ctx.request,
            )
            return HttpResponse(html, status=422)
        response = HttpResponse(status=204)
        response["HX-Redirect"] = self.success_url
        return response

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        if instance is None:
            return False
        model_name = instance._meta.model_name
        app_label = instance._meta.app_label
        return request.user.has_perm(f"{app_label}.delete_{model_name}", instance)
