from __future__ import annotations

from django.db.models import Model
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.html import escape

from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.tabs import Tab


class PanelGetter:
    """Subscriptable object that instantiates panels bound to an instance."""

    def __init__(self, panel_classes: dict[str, type[Panel]], instance: Model):
        self._panel_classes = panel_classes
        self._instance = instance

    def __getitem__(self, name: str) -> Panel:
        if name not in self._panel_classes:
            raise Http404(f"Panel '{name}' not found")
        return self._panel_classes[name](self._instance)


class InstanceView:
    """Used for displaying specific instances. For example one User, Cohort, etc."""

    panels: dict[str, type[Panel]] = {}
    tabs: dict[str, Tab] | None = None

    def __init__(self, instance: Model):
        self.instance = instance

    def get_actions(self) -> list[PanelAction]:
        return []

    def get_action(self, action_name: str) -> PanelAction | None:
        for action in self.get_actions():
            if action.action_name == action_name:
                return action
        return None

    def panel_getter(self) -> PanelGetter:
        return PanelGetter(self.panels, self.instance)

    def get_tab(self, tab_name: str) -> Tab:
        """Get a tab by name."""
        if not self.tabs or tab_name not in self.tabs:
            raise Http404(f"Tab '{tab_name}' not found")
        return self.tabs[tab_name]

    def get_panel_from_tab(self, tab_name: str, panel_name: str) -> type[Panel]:
        """Look up a panel class within a specific tab."""
        tab = self.get_tab(tab_name)
        if panel_name not in tab.panels:
            raise Http404(f"Panel '{panel_name}' not found in tab '{tab_name}'")
        return tab.panels[panel_name]

    def render(
        self, request: HttpRequest, base_url: str = "", active_tab: str | None = None
    ) -> str:
        if self.tabs:
            return self._render_tabbed(request, base_url, active_tab=active_tab)
        return self._render_flat(request, base_url)

    def _render_instance_actions(self, request: HttpRequest, base_url: str) -> str:
        """Render instance-level actions (delete, etc.)."""
        instance_actions = [
            action
            for action in self.get_actions()
            if action.has_permission(request, self.instance)
        ]
        if not instance_actions:
            return ""
        rendered_actions = [
            action.render(request, self.instance, base_url)
            for action in instance_actions
        ]
        return render_to_string(
            "panel_framework/partials/instance_actions.html",
            {"actions": rendered_actions},
            request=request,
        )

    def _render_flat(self, request: HttpRequest, base_url: str) -> str:
        getter = self.panel_getter()
        rendered_panels = []
        for name in self.panels:
            panel_url = f"{base_url.rstrip('/')}/__panels/{name}"
            rendered_panels.append(
                getter[name].render(request, base_url=panel_url, panel_name=name)
            )

        instance_actions_html = self._render_instance_actions(request, base_url)
        title = f"<h1>{escape(str(self.instance))}</h1>"
        panels_html = '<div class="space-y-6">' + "\n".join(rendered_panels) + "</div>"
        return title + "\n" + instance_actions_html + panels_html

    def _render_tabbed(
        self, request: HttpRequest, base_url: str, active_tab: str | None = None
    ) -> str:
        if not self.tabs:
            return self._render_flat(request, base_url)

        tab_names = list(self.tabs.keys())
        default_tab = tab_names[0]
        active = active_tab if active_tab and active_tab in self.tabs else default_tab

        # Build tab context list
        tab_contexts = []
        for name, tab in self.tabs.items():
            tab_url = f"{base_url.rstrip('/')}/__tabs/{name}"
            rendered_panels = ""
            if name == active:
                rendered_panels = self.render_tab(request, name, base_url)
            tab_contexts.append(
                {
                    "name": name,
                    "label": tab.label,
                    "load_url": tab_url,
                    "rendered_panels": rendered_panels,
                }
            )

        instance_actions_html = self._render_instance_actions(request, base_url)
        title = f"<h1>{escape(str(self.instance))}</h1>"
        tabs_html = render_to_string(
            "panel_framework/partials/tab_container.html",
            {
                "tabs": tab_contexts,
                "active_tab": active,
                "base_url": base_url,
            },
            request=request,
        )
        return title + "\n" + instance_actions_html + tabs_html

    def render_tab(self, request: HttpRequest, tab_name: str, base_url: str) -> str:
        """Render panels for a specific tab (used by lazy-load HTMX calls)."""
        if not self.tabs:
            raise Http404("No tabs defined")
        tab = self.tabs[tab_name]
        tab_url = f"{base_url.rstrip('/')}/__tabs/{tab_name}"
        rendered_panels = []
        for name, panel_class in tab.panels.items():
            panel_url = f"{tab_url}/__panels/{name}"
            panel = panel_class(instance=self.instance)
            rendered_panels.append(
                panel.render(request, base_url=panel_url, panel_name=name)
            )
        return render_to_string(
            "panel_framework/partials/tab_panels.html",
            {"rendered_panels": rendered_panels},
            request=request,
        )


class ListViewConfig:
    model: type[Model] | None = None
    instance_view: type[InstanceView] | None = None
    list_view: type[DataTable] | None = None
    url_name: str = ""
    menu_label: str = ""

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return []

    @classmethod
    def get_action(cls, request: HttpRequest, action_name: str) -> PanelAction | None:
        for action in cls.get_actions(request):
            if action.action_name == action_name:
                return action
        return None

    @classmethod
    def get_instance_view(cls, pk: str) -> InstanceView:
        if cls.model is None or cls.instance_view is None:
            raise ValueError(f"{cls.__name__} must define model and instance_view")
        instance = get_object_or_404(cls.model, pk=pk)
        return cls.instance_view(instance)

    @classmethod
    def render(cls, request: HttpRequest, base_url: str = "") -> str:
        if cls.list_view is None:
            raise ValueError(f"{cls.__name__} must define list_view")
        return cls.list_view.render(request, base_url=base_url)
