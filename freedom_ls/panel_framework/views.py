from __future__ import annotations

from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
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
        title = f'<h1 id="instance-title">{escape(str(self.instance))}</h1>'
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
        title = f'<h1 id="instance-title">{escape(str(self.instance))}</h1>'
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


class _ResolvedTab:
    """Wrapper returned by _resolve_path when a tab is resolved."""

    def __init__(self, instance_view: InstanceView, tab_name: str):
        self.instance_view = instance_view
        self.tab_name = tab_name


class _ResolvedAction:
    """Wrapper returned by _resolve_path when an action is resolved."""

    def __init__(self, action: PanelAction, instance: Model | None = None):
        self.action = action
        self.instance = instance


def _resolve_path(
    parts: list[str],
    config: dict[str, type[ListViewConfig]],
    request: HttpRequest | None = None,
) -> (
    type[ListViewConfig]
    | InstanceView
    | PanelGetter
    | Panel
    | _ResolvedAction
    | _ResolvedTab
):
    """Walk the interface config tree according to URL path parts.

    Special segments like __panels, __tabs, and __actions resolve to the
    corresponding attribute on the current object, allowing further traversal.
    """
    try:
        current: (
            type[ListViewConfig]
            | InstanceView
            | PanelGetter
            | Panel
            | _ResolvedAction
            | _ResolvedTab
        ) = config[parts[0]]
    except KeyError as err:
        raise Http404(f"Unknown path segment '{parts[0]}'") from err

    i = 1
    while i < len(parts):
        part = parts[i]
        if part == "__panels":
            if isinstance(current, InstanceView):
                current = current.panel_getter()
            elif isinstance(current, _ResolvedTab):
                # __tabs/{tab}/__panels/{panel} — resolve panel within tab
                tab = current.instance_view.get_tab(current.tab_name)
                current = PanelGetter(tab.panels, current.instance_view.instance)
            else:
                raise Http404(f"Cannot resolve __panels on {type(current)}")
        elif part == "__tabs":
            if i + 1 >= len(parts):
                raise Http404("Missing tab name after __tabs")
            tab_name = parts[i + 1]
            i += 1
            if not isinstance(current, InstanceView):
                raise Http404(f"Cannot resolve __tabs on {type(current)}")
            current.get_tab(tab_name)  # validates tab exists
            current = _ResolvedTab(current, tab_name)
        elif part == "__actions":
            if i + 1 >= len(parts):
                raise Http404("Missing action name after __actions")
            action_name = parts[i + 1]
            i += 1
            if isinstance(current, type) and issubclass(current, ListViewConfig):
                action = current.get_action(request or HttpRequest(), action_name)
                if action is None:
                    raise Http404(f"Action '{action_name}' not found")
                current = _ResolvedAction(action, instance=None)
            elif isinstance(current, InstanceView):
                action = current.get_action(action_name)
                if action is None:
                    raise Http404(f"Action '{action_name}' not found")
                current = _ResolvedAction(action, instance=current.instance)
            elif isinstance(current, Panel):
                action = None
                for a in current.get_actions(request or HttpRequest(), ""):
                    if a.action_name == action_name:
                        action = a
                        break
                if action is None:
                    raise Http404(f"Action '{action_name}' not found on panel")
                current = _ResolvedAction(action, instance=current.instance)
            else:
                raise Http404(f"Cannot resolve __actions on {type(current)}")
        elif isinstance(current, PanelGetter):
            current = current[part]
        elif isinstance(current, type) and issubclass(current, ListViewConfig):
            current = current.get_instance_view(part)
        else:
            raise Http404(f"Cannot resolve path segment '{part}'")
        i += 1

    return current


def _handle_action(
    request: HttpRequest, resolved: _ResolvedAction, base_url: str = ""
) -> HttpResponse:
    """Handle a resolved action: check permission, then dispatch."""
    action = resolved.action
    instance = resolved.instance

    if not action.has_permission(request, instance):
        return HttpResponse(status=403)

    if request.method == "POST":
        return action.handle_submit(request, instance, base_url=base_url)
    if request.method == "DELETE":
        return action.handle_submit(request, instance, base_url=base_url)

    # GET: render the action form
    if hasattr(action, "render"):
        html = action.render(request, instance, base_url)
        return HttpResponse(html)
    return HttpResponse(status=405)


def panel_framework_view(
    config: dict[str, type[ListViewConfig]],
    request: HttpRequest,
    path_string: str,
    template_name: str,
    url_name: str,
) -> HttpResponse:
    """Generic dispatch view for panel-framework-based interfaces.

    Parameters:
        config: mapping of URL name → ListViewConfig subclass
        request: the Django request
        path_string: the captured URL path (e.g. "cohorts/123/__tabs/details")
        template_name: the full-page template to render (e.g. "educator_interface/interface.html")
        url_name: the URL name used for reverse() in menu building (e.g. "educator_interface:interface")
    """
    parts = [p for p in path_string.split("/") if p]
    is_htmx = request.headers.get("HX-Request") == "true"
    base_url = request.path

    if not parts:
        rendered_content = ""
        heading = ""
    else:
        current = _resolve_path(parts, config, request=request)

        if isinstance(current, _ResolvedAction):
            # Strip __actions/{name} from the URL to get the parent base_url
            action_base_url = base_url
            if "/__actions/" in action_base_url:
                action_base_url = action_base_url[
                    : action_base_url.index("/__actions/")
                ]
            return _handle_action(request, current, base_url=action_base_url)

        if isinstance(current, _ResolvedTab):
            iv = current.instance_view
            tab_name = current.tab_name
            if is_htmx:
                # HTMX lazy-load: return just the tab's panels as a fragment
                html = iv.render_tab(
                    request, tab_name, base_url.rsplit("/__tabs/", 1)[0]
                )
                return HttpResponse(html)
            # Non-HTMX: render full page with the tab active
            instance_base_url = base_url.rsplit("/__tabs/", 1)[0]
            rendered_content = iv.render(
                request, base_url=instance_base_url, active_tab=tab_name
            )
            # Fall through to full page rendering below

        elif isinstance(current, Panel):
            return HttpResponse(current.render(request, base_url=base_url))

        elif isinstance(current, InstanceView):
            rendered_content = current.render(request, base_url=base_url)
        elif isinstance(current, type) and issubclass(current, ListViewConfig):
            # Render list view with actions
            list_actions = [
                action
                for action in current.get_actions(request)
                if action.has_permission(request)
            ]
            actions_html = ""
            if list_actions:
                rendered_actions = [
                    action.render(request, None, base_url) for action in list_actions
                ]
                actions_html = render_to_string(
                    "panel_framework/partials/instance_actions.html",
                    {"actions": rendered_actions},
                    request=request,
                )
            table_html = current.render(request, base_url=base_url)
            rendered_content = actions_html + table_html
        else:
            raise Http404("Unexpected path resolution")

        if is_htmx and not isinstance(current, _ResolvedTab):
            return HttpResponse(rendered_content)

        heading = current.menu_label if hasattr(current, "menu_label") else ""

    menu_items = [
        {
            "label": conf.menu_label,
            "url": reverse(url_name, kwargs={"path_string": conf.url_name}),
        }
        for conf in config.values()
    ]

    context = {
        "menu_items": menu_items,
        "content": rendered_content,
        "heading": heading,
    }

    return render(request, template_name, context)
