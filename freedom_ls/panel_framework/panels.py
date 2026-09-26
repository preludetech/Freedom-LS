"""Panels: the units a panel-framework page is built from.

A `Panel` subclass is a definition: its class attributes say which model,
fields, children and template it has. An instance of it is a bound panel,
built fresh for one request from a `PanelContext`, and it is what renders.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from functools import cached_property
from typing import cast

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest

from freedom_ls.panel_framework.actions import EditAction, PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.field_display import (
    display_for_field,
    display_for_value,
    label_for_field,
    lookup_field,
)
from freedom_ls.panel_framework.tables import DataTable


class Panel:
    """One rectangle of an interface page, rendered through `template_name`.

    Containers (`PanelStack`, `TabSet`) declare `children`; every other panel
    is a leaf. A panel that declares `model` needs an instance to bind to. One
    that leaves it `None` renders with or without an instance.
    """

    title: str = ""
    template_name: str = "panel_framework/panels/panel.html"
    #: The template a targeted htmx refresh of this panel renders, when that
    #: refresh should replace only part of the panel. `None` makes the whole
    #: panel its own region, so a refresh re-renders `template_name`.
    region_template_name: str | None = None
    model: type[Model] | None = None
    children: dict[str, type[Panel]] = {}
    #: The URL segment ("__panels" or "__tabs") that addresses a child.
    child_segment: str = ""

    def __init__(self, ctx: PanelContext) -> None:
        if self.model is not None and ctx.instance is None:
            raise ImproperlyConfigured(
                f"{type(self).__name__} declares a model and needs an instance."
            )
        self.ctx = ctx
        self.request = ctx.request
        self.instance = ctx.instance

    def has_permission(self, request: HttpRequest) -> bool:
        """Whether this request may see this panel at all.

        Evaluated per request, before the panel renders or its URL resolves.
        A panel that returns False is left out of its container, and its own
        URL is a 404. The default shows the panel to every request that
        reached the page; the page's own access checks still apply. A
        consumer narrows a panel to a role by overriding this.
        """
        return True

    def is_shown(self) -> bool:
        """Whether this bound panel renders.

        A leaf is shown when `has_permission` allows it. A container also
        needs at least one shown child, so a container whose children are all
        hidden is hidden itself.
        """
        if not self.has_permission(self.request):
            return False
        return not self.children or bool(self.get_children())

    def get_actions(self) -> list[PanelAction]:
        return []

    @cached_property
    def _shown_children(self) -> list[Panel]:
        bound = [
            child_class(
                replace(
                    self.ctx,
                    base_url=f"{self.ctx.base_url}/{self.child_segment}/{name}",
                    name=name,
                )
            )
            for name, child_class in self.children.items()
        ]
        return [child for child in bound if child.is_shown()]

    def get_children(self) -> list[Panel]:
        """The shown children, bound once per request and in declared order."""
        return self._shown_children

    def child(self, name: str) -> Panel:
        """The shown child called `name`. A missing or hidden child is a 404."""
        for child in self.get_children():
            if child.ctx.name == name:
                return child
        raise Http404(f"Panel '{name}' not found")

    @property
    def region_id(self) -> str:
        """The DOM id a targeted htmx refresh of this panel swaps.

        Derived from the panel's own URL, so it is unique on the page and no
        consumer ever writes one by hand.
        """
        return "panel-" + re.sub(r"[^\w-]+", "-", self.ctx.base_url).strip("-")

    def get_context_data(self) -> dict[str, object]:
        """The context `template_name` renders with.

        Subclasses call `super()` and add keys. Actions the request may not
        use are already filtered out.
        """
        actions = [
            action
            for action in self.get_actions()
            if action.has_permission(self.request, self.instance)
        ]
        return {
            "panel": self,
            "request": self.request,
            "name": self.ctx.name,
            "base_url": self.ctx.base_url,
            "title": self.title,
            "actions": actions,
            "region_id": self.region_id,
            "region_template_name": self.region_template_name,
        }


class PanelStack(Panel):
    """Renders its shown children one after another."""

    template_name = "panel_framework/panels/panel_stack.html"
    child_segment = "__panels"

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["children"] = self.get_children()
        return context


class TabSet(Panel):
    """Renders its shown children as tabs, one visible at a time.

    Each child's `title` is its tab label. The active tab comes from the
    request path, so a tab's own URL renders with that tab showing.
    """

    template_name = "panel_framework/panels/tab_set.html"
    child_segment = "__tabs"

    def get_active_child(self) -> Panel:
        path = self.request.path
        children = self.get_children()
        for child in children:
            base = child.ctx.base_url
            # The trailing slash keeps a tab named "details" from claiming
            # "details2".
            if path == base or path.startswith(base + "/"):
                return child
        return children[0]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        active = self.get_active_child()
        context["tabs"] = [
            {
                "name": child.ctx.name,
                "title": child.title,
                "url": child.ctx.base_url,
                "active": child is active,
            }
            for child in self.get_children()
        ]
        context["active_child"] = active
        return context


class DataTablePanel(Panel):
    """A panel holding one `DataTable`, scoped through `get_queryset`."""

    template_name = "panel_framework/panels/data_table.html"
    region_template_name = "panel_framework/panels/data_table_region.html"
    data_table: type[DataTable]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """The rows this panel may show.

        This is the one place a table panel is scoped. Narrow it in a
        subclass with `super().get_queryset(request).filter(...)`, so the
        table's own scoping always applies underneath.
        """
        return self.data_table.get_queryset(request)

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context.update(
            self.data_table.get_context(
                self.request,
                self.get_queryset(self.request),
                base_url=self.ctx.base_url,
                table_id=self.region_id,
            )
        )
        return context


class InstanceDetailsPanel(Panel):
    """Shows `fields` of the bound instance as label and value rows.

    Each entry in `fields` is a field name, a `__` path through relations, a
    property or a method on `model`.
    """

    title = "Details"
    template_name = "panel_framework/panels/instance_details.html"
    fields: list[str] = []
    empty_value_display: str = "-"
    editable: bool = False
    form_class: Callable[..., forms.ModelForm] | None = None

    def __init__(self, ctx: PanelContext) -> None:
        if ctx.instance is None:
            raise ImproperlyConfigured(
                f"{type(self).__name__} shows an instance and needs one."
            )
        super().__init__(ctx)

    def _bound_instance(self) -> Model:
        return cast(Model, self.instance)

    def get_actions(self) -> list[PanelAction]:
        if not (self.editable and self.form_class):
            return []
        instance = self._bound_instance()
        return [
            EditAction(
                form_class=self.form_class,
                form_title=f"Edit {instance}",
                instance=instance,
            )
        ]

    def get_rows(self) -> list[dict[str, object]]:
        instance = self._bound_instance()
        model = self.model or type(instance)
        rows: list[dict[str, object]] = []
        for name in self.fields:
            field, value = lookup_field(name, instance)
            display = (
                display_for_value(value, self.empty_value_display)
                if field is None
                else display_for_field(value, field, self.empty_value_display)
            )
            rows.append(
                {
                    "label": label_for_field(name, model),
                    "value": display,
                    "is_boolean": isinstance(display, bool),
                }
            )
        return rows

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rows"] = self.get_rows()
        return context
