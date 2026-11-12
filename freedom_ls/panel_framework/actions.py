from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from typing import cast
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import (
    NON_FIELD_ERRORS,
    ImproperlyConfigured,
    ValidationError,
)
from django.db import transaction
from django.db.models import Model, QuerySet
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.panel_framework.forms import ReasonForm


def _model_capability(model: type[Model] | Model, verb: str) -> str:
    """The capability string for `verb`-ing `model`, in `app_label.codename` form."""
    meta = model._meta
    return f"{meta.app_label}.{verb}_{meta.model_name}"


def navigation_response(path: str) -> HttpResponse:
    """204 that closes the modal and navigates the main content to `path`."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = build_hx_trigger({}, close_modal=True)
    response["HX-Location"] = json.dumps(
        {"path": path, "target": "#main-content", "swap": "outerHTML"}
    )
    return response


def current_page_within(request: HttpRequest, root: str) -> str:
    """The path of the page the request was made from, when it lies
    under `root`; otherwise `root`. The header is client-supplied, so
    only its path is used and only within the page the action belongs to.
    Its host is not checked: a proxy that rewrites Host would fail that
    check for every request, and the path alone names nothing off-site."""
    path = urlsplit(request.headers.get("HX-Current-URL", "")).path
    if path == root or path.startswith(root.rstrip("/") + "/"):
        return path
    return root


def changed_response(events: dict[str, list[str]]) -> HttpResponse:
    """204 that closes the modal and fires the domain events."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = build_hx_trigger(events, close_modal=True)
    return response


def refusal_response(
    ctx: PanelContext, *, title: str, message: str, status: int = 422
) -> HttpResponse:
    """A message dialog saying a change was not made, and why."""
    return render(
        ctx.request,
        "panel_framework/modal/message.html",
        {"title": title, "message": message},
        status=status,
    )


def count_phrase(count: int, singular: object, plural: object) -> str:
    """A count and a noun, singular for exactly one."""
    return f"{count} {singular if count == 1 else plural}"


def count_noun(model: type[Model], count: int) -> str:
    """A count and the model's name, singular for exactly one."""
    return count_phrase(
        count, model._meta.verbose_name, model._meta.verbose_name_plural
    )


def join_prose(parts: list[str]) -> str:
    """Run a list into readable prose: a, then a and b, then a, b and c."""
    if len(parts) < 2:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


class PanelAction:
    """A button on a panel, list or instance view, and what submitting it does.

    It renders through `template_name` with `get_context_data(ctx)`, and its
    URL is the owner's `ctx.base_url` plus `/__actions/<action_name>`.
    """

    label: str = ""
    variant: str = "primary"
    action_name: str = ""
    #: Rendered by {% render_action %} from get_trigger_context(ctx): cheap,
    #: never form- or cascade-related.
    trigger_template_name: str = "panel_framework/partials/action_button.html"
    #: The action's fragment, rendered only by _handle_action on GET, from
    #: get_context_data(ctx). An action that only takes a POST leaves it None.
    template_name: str | None = None
    #: The capability this action asks about, or None to allow it whenever
    #: the config lets the action render at all.
    capability: str | None = None
    #: Domain events this action's mutation fires on success. An action whose
    #: mutation touches an entity other than its own instance overrides
    #: get_success_events instead of relying on the default mapping.
    success_events: tuple[str, ...] = ()
    #: False for a row-scoped action: it still resolves on its panel's URL,
    #: but its trigger renders per row (the panel exposes its URL through
    #: `row_action_urls`) rather than in the panel's footer.
    renders_in_footer: bool = True
    #: The request parameter naming the row a row-scoped action acts on.
    row_param: str | None = None

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Model]:
        """The rows this action may act on, already narrowed to what the
        request may reach. It has no default: a row action must state its
        scope, so the lookup never runs against an unscoped manager."""
        raise NotImplementedError

    def get_row_object(self, ctx: PanelContext) -> Model:
        """The row `row_param` names, from `get_row_queryset`. A missing,
        malformed or out-of-scope value is a 404."""
        if self.row_param is None:
            raise ImproperlyConfigured(f"{type(self).__name__} sets no row_param.")
        params = ctx.request.POST if ctx.request.method == "POST" else ctx.request.GET
        # A value the pk field cannot parse is the same miss as an unknown one.
        try:
            return get_object_or_404(
                self.get_row_queryset(ctx), pk=params.get(self.row_param, "")
            )
        except (ValueError, ValidationError):
            raise Http404 from None

    def get_capability(self, ctx: PanelContext) -> str | None:
        return self.capability

    def permission_object(self, ctx: PanelContext) -> Model | None:
        """The object a capability is asked about: the instance, or, on a
        list-level action, the list's own scope."""
        return ctx.scope_object()

    def has_permission(self, ctx: PanelContext) -> bool:
        capability = self.get_capability(ctx)
        if capability is None:
            return True
        scope = self.permission_object(ctx)
        if scope is None:
            return False
        return ctx.config.has_capability(ctx.request, capability, scope)

    def is_offered(self, ctx: PanelContext) -> bool:
        """Whether the trigger renders. An action that is permitted but not
        offered still resolves, so a stale submit reaches handle_submit and
        is refused with a reason instead of a 404."""
        return True

    def is_available(self, ctx: PanelContext) -> bool:
        """Whether the trigger renders for this request: permitted and offered."""
        return self.has_permission(ctx) and self.is_offered(ctx)

    def get_success_events(self, instance: Model | None) -> dict[str, list[str]]:
        ids = [str(instance.pk)] if instance is not None else []
        return {name: list(ids) for name in self.success_events}

    def get_action_url(self, ctx: PanelContext) -> str:
        return f"{ctx.base_url}/__actions/{self.action_name}"

    def get_trigger_context(self, ctx: PanelContext) -> dict[str, object]:
        return {
            "label": self.label,
            "variant": self.variant,
            "action_url": self.get_action_url(ctx),
        }

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return self.get_trigger_context(ctx)

    def render_fragment(self, ctx: PanelContext) -> HttpResponse:
        """The response to a GET: the action's template with its context. An
        action that can refuse the dialog before it opens overrides this."""
        return render(
            ctx.request, self.get_fragment_template_name(), self.get_context_data(ctx)
        )

    def get_fragment_template_name(self) -> str:
        if self.template_name is None:
            raise ImproperlyConfigured(
                f"{type(self).__name__} has no template_name, so it cannot render "
                "a fragment on GET."
            )
        return self.template_name

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        """Process action submission. Override in subclasses."""
        raise NotImplementedError


def field_error_count(form: forms.BaseForm) -> int:
    """How many fields of a bound form carry an error."""
    return sum(1 for name in form.errors if name != NON_FIELD_ERRORS)


def form_fragment_context(
    form: forms.BaseForm,
    *,
    form_title: str,
    action_url: str,
    submit_buttons: list[dict[str, str]],
    empty_message: str | None = None,
    autofocus: bool = True,
) -> dict[str, object]:
    """Mark the form's first visible field for autofocus and build the
    context `modal/form.html` renders.

    Skipped when the form carries errors: a browser moves focus to a
    freshly-inserted `autofocus` field as soon as it renders, which would
    override the error-summary focus appModal sets for a 422 re-render.
    Skipped too with `autofocus` off, for a form rendered as part of a page
    rather than a dialog, which must not take focus on load.

    `empty_message`, when set, replaces the form with that sentence and a
    Close button, for a picker with nothing to offer.
    """
    fields = form.visible_fields()
    if autofocus and fields and not form.errors:
        fields[0].field.widget.attrs["autofocus"] = True
    return {
        "form": form,
        "field_error_count": field_error_count(form),
        "form_title": form_title,
        "action_url": action_url,
        "submit_buttons": submit_buttons,
        "empty_message": empty_message,
    }


def denied_response(ctx: PanelContext, action: PanelAction) -> HttpResponse:
    """The 403 fragment for an action the user may not perform."""
    context = {
        "action_label": action.label,
        **ctx.config.get_denied_context(
            ctx.request, action.get_capability(ctx), action.permission_object(ctx)
        ),
    }
    return render(
        ctx.request, "panel_framework/partials/action_denied.html", context, status=403
    )


class ModalPanelAction(PanelAction):
    """An action whose button opens its fragment in the app modal."""

    trigger_template_name = "panel_framework/partials/modal_trigger.html"


class FormPanelAction(ModalPanelAction):
    """An action whose dialog is a form.

    Every hook reads the request through `ctx`, so an action holds no request
    state. `form_class` is any form class or factory; a `ModelForm` class
    also receives the page's instance.
    """

    template_name = "panel_framework/modal/form.html"
    form_class: Callable[..., forms.BaseForm]
    form_title: str = ""
    submit_buttons: list[dict[str, str]] = [
        {"label": "Save", "variant": "primary"},
    ]
    #: Off for a form rendered inside a panel rather than a dialog: a page
    #: must not move focus to a field as it loads.
    autofocus_first_field: bool = True
    #: Fields whose change re-renders the dialog, so later fields can depend on them.
    refresh_on_change: tuple[str, ...] = ()

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "data": ctx.request.POST if ctx.request.method == "POST" else None
        }
        # form_class may be a factory function, which issubclass() rejects.
        if isinstance(self.form_class, type) and issubclass(
            self.form_class, forms.ModelForm
        ):
            kwargs["instance"] = ctx.instance
        return kwargs

    def get_form(self, ctx: PanelContext) -> forms.BaseForm:
        """The form for this request. A GET that carries a `refresh_on_change`
        field renders the form bound to the query when the query is valid, so
        the dialog can react to the choice; a stale choice is not a
        submission and earns no error."""
        kwargs = self.get_form_kwargs(ctx)
        form = self.form_class(**kwargs)
        if ctx.request.method != "POST" and any(
            name in ctx.request.GET for name in self.refresh_on_change
        ):
            queried = self.form_class(**{**kwargs, "data": ctx.request.GET})
            if queried.is_valid():
                form = queried
        self._mark_refresh_fields(ctx, form)
        return form

    def get_unbound_form(self, ctx: PanelContext) -> forms.BaseForm:
        """A form with no data, for the dialog after a save that stays open."""
        form = self.form_class(**{**self.get_form_kwargs(ctx), "data": None})
        self._mark_refresh_fields(ctx, form)
        return form

    def _mark_refresh_fields(self, ctx: PanelContext, form: forms.BaseForm) -> None:
        """Make a change to each `refresh_on_change` field re-render the dialog
        from the action URL with the form's values. Without JavaScript the
        dialog keeps its generic form and the submit still works."""
        url = self.get_action_url(ctx)
        for name in self.refresh_on_change:
            form.fields[name].widget.attrs.update(
                {
                    "hx-get": url,
                    "hx-include": "closest form",
                    "hx-trigger": "change",
                    "hx-target": "#app-modal-body",
                    "hx-swap": "innerHTML",
                }
            )

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        return self.form_title

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        """The sentence that replaces a picker with nothing to offer."""
        return None

    def get_fragment_context(
        self, ctx: PanelContext, form: forms.BaseForm
    ) -> dict[str, object]:
        return form_fragment_context(
            form,
            form_title=self.get_form_title(ctx, form),
            action_url=self.get_action_url(ctx),
            submit_buttons=self.submit_buttons,
            # A submitted form shows its errors; the empty message stands in
            # only for the form a person has not yet filled in.
            empty_message=None if form.is_bound else self.get_empty_message(ctx, form),
            autofocus=self.autofocus_first_field,
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        """The modal fragment for the form this request holds."""
        return self.get_fragment_context(ctx, self.get_form(ctx))

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        """Process form submission."""
        form = self.get_form(ctx)
        if form.is_valid():
            return self.form_valid(ctx, form)
        return self.form_invalid(ctx, form)

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        raise NotImplementedError

    def form_invalid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        """Re-render the dialog with the form's errors and status 422."""
        html = render_to_string(
            self.get_fragment_template_name(),
            self.get_fragment_context(ctx, form),
            request=ctx.request,
        )
        return HttpResponse(html, status=422)


class CreateInstanceAction(FormPanelAction):
    """Base class for actions that create a new instance via a modal form.

    Subclasses must define: form_class, form_title, label, action_name.
    Subclasses must implement: get_success_url(ctx, instance).
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

    def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
        """Return the URL to redirect to after successful creation."""
        raise NotImplementedError

    def get_capability(self, ctx: PanelContext) -> str | None:
        if self.capability is not None:
            return self.capability
        meta = getattr(self.form_class, "Meta", None)
        if meta is None:
            raise ValueError("form_class must define a Meta class with model")
        model: type[Model] = meta.model
        return _model_capability(model, "add")

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        instance = cast(forms.ModelForm, form).save()
        events = self.get_success_events(instance)
        if ctx.request.POST.get("action") == "save_and_add":
            html = render_to_string(
                self.get_fragment_template_name(),
                self.get_fragment_context(ctx, self.get_unbound_form(ctx)),
                request=ctx.request,
            )
            response = HttpResponse(html)
            response["HX-Trigger"] = build_hx_trigger(events)
            return response
        response = navigation_response(self.get_success_url(ctx, instance))
        response["HX-Trigger"] = build_hx_trigger(events, close_modal=True)
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
        success_events: tuple[str, ...] = (),
    ) -> None:
        self.form_class = form_class
        self.form_title = form_title
        self._instance = instance
        self.success_events = success_events

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {
            **super().get_form_kwargs(ctx),
            "instance": ctx.instance or self._instance,
        }

    def event_instance(self, form: forms.ModelForm) -> Model:
        """The instance the success events and the page title are about.

        The form's own instance by default. An action that edits an object
        related to the page's instance returns the page's own instance here.
        """
        return cast(Model, form.instance)

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        model_form = cast(forms.ModelForm, form)
        model_form.save()
        instance = self.event_instance(model_form)
        response = HttpResponse(status=204)
        # The page heading is named by the section, not by str(instance), so
        # the title a save sends back has to come from the same place.
        response["HX-Trigger"] = build_hx_trigger(
            self.get_success_events(instance),
            close_modal=True,
            title=ctx.config.get_instance_label(instance),
        )
        return response

    def get_capability(self, ctx: PanelContext) -> str | None:
        return self.capability or _model_capability(self._instance, "change")


class ConfirmAction(ModalPanelAction):
    """An action that asks for one decision in a dialog before it runs.

    The dialog is `modal/confirm.html`: a title, a body, hidden fields and one
    confirm button. A subclass's template extends it and fills `body`.
    """

    template_name = "panel_framework/modal/confirm.html"
    variant = "secondary"
    #: The confirm button's label; the action's own label when empty.
    confirm_label: str = ""
    confirm_variant: str = "primary"
    loading_text: str = "Saving…"

    def get_title(self, ctx: PanelContext) -> str:
        return self.label

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        """Row parameters the submit needs, posted as hidden inputs."""
        return {}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        """What the dialog's body says, beyond the title and the buttons."""
        return {}

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return {
            **super().get_context_data(ctx),
            "title": self.get_title(ctx),
            "hidden_fields": self.get_hidden_fields(ctx),
            "confirm_label": self.confirm_label or self.label,
            "confirm_variant": self.confirm_variant,
            "loading_text": self.loading_text,
            **self.get_confirm_context(ctx),
        }

    def refuse(self, ctx: PanelContext, message: str, *, title: str) -> HttpResponse:
        """A message dialog saying the change was not made, and why."""
        return refusal_response(ctx, title=title, message=message)


class DeleteAction(ConfirmAction):
    """Deletes the instance of whatever it is attached to, after confirmation.

    With a success_url, a delete navigates there and sends no domain events.
    Without one it stays on the page and sends success_events, so the panels
    still showing the deleted row can refetch themselves.
    """

    label = "Delete"
    variant = "error"
    action_name = "delete"
    template_name = "panel_framework/modal/delete_confirmation.html"
    confirm_variant = "error"
    loading_text = "Deleting…"

    def __init__(self, success_url: str = "", success_events: tuple[str, ...] = ()):
        self.success_url = success_url
        self.success_events = success_events

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
        counts: Counter[type[Model]] = Counter()
        for model, objs in collector.data.items():
            counts[model] += len(objs)
        # Rows with no signals or dependents of their own are bulk-deleted
        # later rather than loaded into collector.data.
        for fast_delete in collector.fast_deletes:
            counts[fast_delete.model] += fast_delete.count()
        return [
            count_noun(model, count)
            for model, count in counts.items()
            if count and model is not type(instance)
        ]

    def get_blocked_reason(self, instance: Model, error: ProtectedError) -> str:
        """One plain sentence naming what still depends on this instance."""
        counts: Counter[type[Model]] = Counter(
            type(obj) for obj in error.protected_objects
        )
        dependents = [
            count_noun(model, counts[model])
            for model in sorted(counts, key=lambda m: str(m._meta.verbose_name))
        ]
        return (
            f"This {instance._meta.verbose_name} cannot be deleted because it "
            f"still has {join_prose(dependents)}."
        )

    def _instance(self, ctx: PanelContext) -> Model:
        if ctx.instance is None:
            raise ImproperlyConfigured("DeleteAction needs an instance to delete.")
        return ctx.instance

    def _blocked_response(
        self, ctx: PanelContext, instance: Model, reason: str
    ) -> HttpResponse:
        """The confirmation re-rendered with `reason` in place of a live
        delete button, the way a form answers an invalid submit."""
        context = {
            **self.get_context_data(ctx),
            "cascade_summary": [],
            "blocked_reason": reason,
        }
        html = render_to_string(self.template_name, context, request=ctx.request)
        return HttpResponse(html, status=422)

    def before_delete(self, ctx: PanelContext, instance: Model) -> HttpResponse | None:
        """Runs inside the delete's transaction, just before the row goes.
        Returning a response sends it instead of deleting; a subclass that
        does so must not have written anything first."""
        return None

    def get_title(self, ctx: PanelContext) -> str:
        return f"Delete {self._instance(ctx)}"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        """The cascade summary, or, for a delete that a protected relation
        would block, the reason in its place."""
        instance = self._instance(ctx)
        context: dict[str, object] = {
            "instance": instance,
            "noun": instance._meta.verbose_name,
            "cascade_summary": [],
            "blocked_reason": "",
        }
        try:
            context["cascade_summary"] = self.get_cascade_summary(instance)
        except ProtectedError as error:
            context["blocked_reason"] = self.get_blocked_reason(instance, error)
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        instance = ctx.instance
        if instance is None:
            return HttpResponse(status=400)
        # Read before delete(): Django sets the pk to None once the row is
        # gone, and the event still needs to name what was deleted.
        events = self.get_success_events(instance)
        try:
            with transaction.atomic():
                refusal = self.before_delete(ctx, instance)
                if refusal is not None:
                    return refusal
                instance.delete()
        except ProtectedError as error:
            # The render path hides the button, so reaching here means a stale
            # page or a hand-made request. Rendered after the block, since
            # a transaction marked for rollback cannot run queries.
            return self._blocked_response(
                ctx, instance, self.get_blocked_reason(instance, error)
            )
        if not self.success_url:
            response = HttpResponse(status=204)
            response["HX-Trigger"] = build_hx_trigger(events, close_modal=True)
            return response
        # htmx handles HX-Trigger before HX-Location, so domain events would
        # reach the page being left while it is still on screen, and its
        # panels would refetch URLs scoped to the row just deleted. The page
        # navigated to renders fresh and needs none of them.
        return navigation_response(self.success_url)

    def permission_object(self, ctx: PanelContext) -> Model | None:
        """The instance to delete only -- never a list-level scope fallback,
        since there is nothing to delete without one."""
        return ctx.instance

    def get_capability(self, ctx: PanelContext) -> str | None:
        if ctx.instance is None:
            return self.capability
        return self.capability or _model_capability(ctx.instance, "delete")

    def has_permission(self, ctx: PanelContext) -> bool:
        return ctx.instance is not None and super().has_permission(ctx)


class ReasonMixin(PanelAction):
    """A confirm dialog that takes an optional reason, which the submit reads
    from `ctx.reason`. List it first in the bases, as RequiresActiveCohortMixin
    is, so the reason is validated before any other submit handling. An
    action with its own submit overrides handle_confirmed_submit, never
    handle_submit, and one that builds its own context calls
    super().get_context_data so the reason field is in it."""

    reason_form_class: type[ReasonForm] = ReasonForm

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        context = super().get_context_data(ctx)
        context.setdefault("reason_form", self.reason_form_class())
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        form = self.reason_form_class(ctx.request.POST)
        if not form.is_valid():
            context = {**self.get_context_data(ctx), "reason_form": form}
            html = render_to_string(
                self.get_fragment_template_name(), context, request=ctx.request
            )
            return HttpResponse(html, status=422)
        return self.handle_confirmed_submit(
            replace(ctx, reason=str(form.cleaned_data["reason"]))
        )

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        """The submit once the reason is valid and on `ctx`: the next
        handle_submit in the MRO."""
        return super().handle_submit(ctx)
