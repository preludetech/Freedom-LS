from __future__ import annotations

import json
from collections.abc import Callable

from django import forms
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string


class PanelAction:
    label: str = ""
    variant: str = "primary"
    action_name: str = ""

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        return True

    def handle_submit(
        self, request: HttpRequest, instance: Model | None = None, base_url: str = ""
    ) -> HttpResponse:
        """Process action submission. Override in subclasses."""
        raise NotImplementedError

    def render(self, request: HttpRequest, context: object, base_url: str) -> str:
        """Render the action button HTML."""
        return render_to_string(
            "panel_framework/partials/action_button.html",
            {
                "label": self.label,
                "variant": self.variant,
                "action_url": f"{base_url}/__actions/{self.action_name}",
            },
            request=request,
        )


class FormPanelAction(PanelAction):
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

    def get_form_url(self, base_url: str) -> str:
        """URL for form submission via HTMX."""
        return f"{base_url}/__actions/{self.action_name}"

    def handle_submit(
        self, request: HttpRequest, instance: Model | None = None, base_url: str = ""
    ) -> HttpResponse:
        """Process form submission."""
        self._last_form_url = self.get_form_url(base_url)
        form = self.get_form(request, instance)
        if form.is_valid():
            return self.form_valid(request, form)
        return self.form_invalid(request, form)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        raise NotImplementedError

    def form_invalid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        """Return 422 with re-rendered form."""
        html = render_to_string(
            "panel_framework/partials/modal_form.html",
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

    def render(self, request: HttpRequest, context: object, base_url: str) -> str:
        """Render trigger button + modal with form."""
        form = self.get_form(request)
        form_url = self.get_form_url(base_url)
        self._last_form_url = form_url
        return render_to_string(
            "panel_framework/partials/modal_form.html",
            {
                "form": form,
                "form_title": self.form_title,
                "form_url": form_url,
                "variant": self.variant,
                "label": self.label,
                "submit_buttons": self.submit_buttons,
            },
            request=request,
        )


class CreateInstanceAction(FormPanelAction):
    """Base class for actions that create a new instance via a modal form.

    Subclasses must define: form_class, form_title, label, action_name.
    Subclasses must implement: get_success_url(instance) and get_created_event_name().
    """

    variant: str = "primary"
    submit_buttons: list[dict[str, str]] = [
        {
            "label": "Save and add another",
            "variant": "outline",
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
            "panel_framework/partials/modal_form.html",
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
    variant = "outline"
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
    label = "Delete"
    variant = "danger"
    action_name = "delete"

    def __init__(self, success_url: str = ""):
        self.success_url = success_url

    def get_cascade_summary(self, instance: Model) -> list[str]:
        """Use Django's Collector to show what will be cascade-deleted."""
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

    def render(self, request: HttpRequest, context: object, base_url: str) -> str:
        """Render danger button + confirmation modal."""
        if not isinstance(context, Model):
            raise TypeError("DeleteAction.render requires a Model instance")
        instance = context
        cascade = self.get_cascade_summary(instance)
        return render_to_string(
            "panel_framework/partials/delete_confirmation.html",
            {
                "instance": instance,
                "cascade_summary": cascade,
                "delete_url": f"{base_url}/__actions/delete",
                "variant": self.variant,
            },
            request=request,
        )

    def handle_submit(
        self, request: HttpRequest, instance: Model | None = None, base_url: str = ""
    ) -> HttpResponse:
        if instance is None:
            return HttpResponse(status=400)
        instance.delete()
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
