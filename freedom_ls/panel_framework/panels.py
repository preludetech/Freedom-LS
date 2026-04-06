from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Model
from django.http import HttpRequest
from django.template.loader import render_to_string

from freedom_ls.panel_framework.tables import DataTable

if TYPE_CHECKING:
    from freedom_ls.panel_framework.actions import PanelAction


class Panel:
    title: str = ""

    def __init__(self, instance: Model):
        self.instance = instance

    def get_actions(
        self, request: HttpRequest, base_url: str = ""
    ) -> list[PanelAction]:
        return []

    def get_content(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        raise NotImplementedError

    def render(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        content = self.get_content(request, base_url=base_url, panel_name=panel_name)
        actions = [
            action.render(request, self, base_url)
            for action in self.get_actions(request, base_url)
            if action.has_permission(request, self.instance)
        ]
        return render_to_string(
            "panel_framework/partials/panel_container.html",
            {"title": self.title, "content": content, "actions": actions},
            request=request,
        )


class DataTablePanel(Panel):
    data_table: type[DataTable]

    def get_filters(self) -> dict:
        return {}

    def get_content(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        table_id = f"table-{panel_name}" if panel_name else "data-table-container"
        return self.data_table.render(
            request,
            filters=self.get_filters(),
            base_url=base_url,
            table_id=table_id,
        )

    def render(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        return super().render(request, base_url=base_url, panel_name=panel_name)


class InstanceDetailsPanel(Panel):
    title = "Details"
    fields: list[str] = []
    editable: bool = False
    form_class: type | None = None

    def get_actions(self, request: HttpRequest, base_url: str = "") -> list:
        from freedom_ls.panel_framework.actions import EditAction

        actions = []
        if self.editable and self.form_class:
            actions.append(
                EditAction(
                    form_class=self.form_class,
                    form_title=f"Edit {self.instance}",
                    instance=self.instance,
                )
            )
        return actions

    def _resolve_field(self, field_path: str) -> tuple[str, object]:
        """Resolve a dot-notation field path to (label, value).

        Supports paths like "user.email" by traversing related objects.
        """
        parts = field_path.split(".")
        obj: Model = self.instance
        for part in parts[:-1]:
            related = getattr(obj, part)
            if not isinstance(related, Model):
                raise ValueError(f"Expected Model at '{part}', got {type(related)}")
            obj = related
        field_name = parts[-1]
        field = obj._meta.get_field(field_name)
        label = str(getattr(field, "verbose_name", field_name)).title()
        value = getattr(obj, field_name)
        return label, value

    def get_content(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        field_data = []
        for field_path in self.fields:
            label, value = self._resolve_field(field_path)
            field_data.append({"label": label, "value": value})
        return render_to_string(
            "panel_framework/partials/instance_details_panel.html",
            {"fields": field_data},
            request=request,
        )
