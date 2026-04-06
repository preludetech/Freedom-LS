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


_Resolved = (
    type[ListViewConfig]
    | InstanceView
    | PanelGetter
    | Panel
    | _ResolvedAction
    | _ResolvedTab
)


def _resolve_panels(current: _Resolved) -> PanelGetter:
    """Resolve a __panels segment to a PanelGetter."""
    if isinstance(current, InstanceView):
        return current.panel_getter()
    if isinstance(current, _ResolvedTab):
        tab = current.instance_view.get_tab(current.tab_name)
        return PanelGetter(tab.panels, current.instance_view.instance)
    raise Http404(f"Cannot resolve __panels on {type(current)}")


def _resolve_tabs(
    current: _Resolved, parts: list[str], i: int
) -> tuple[_ResolvedTab, int]:
    """Resolve a __tabs/{tab_name} segment pair. Returns the resolved tab and updated index."""
    if i + 1 >= len(parts):
        raise Http404("Missing tab name after __tabs")
    tab_name = parts[i + 1]
    if not isinstance(current, InstanceView):
        raise Http404(f"Cannot resolve __tabs on {type(current)}")
    current.get_tab(tab_name)  # validates tab exists
    return _ResolvedTab(current, tab_name), i + 1


def _resolve_action_on_list(
    current: type[ListViewConfig], action_name: str, request: HttpRequest
) -> _ResolvedAction:
    """Resolve an action on a ListViewConfig."""
    action = current.get_action(request, action_name)
    if action is None:
        raise Http404(f"Action '{action_name}' not found")
    return _ResolvedAction(action, instance=None)


def _resolve_action_on_instance(
    current: InstanceView, action_name: str
) -> _ResolvedAction:
    """Resolve an action on an InstanceView."""
    action = current.get_action(action_name)
    if action is None:
        raise Http404(f"Action '{action_name}' not found")
    return _ResolvedAction(action, instance=current.instance)


def _resolve_action_on_panel(
    current: Panel, action_name: str, request: HttpRequest
) -> _ResolvedAction:
    """Resolve an action on a Panel."""
    for a in current.get_actions(request, ""):
        if a.action_name == action_name:
            return _ResolvedAction(a, instance=current.instance)
    raise Http404(f"Action '{action_name}' not found on panel")


def _resolve_actions(
    current: _Resolved, parts: list[str], i: int, request: HttpRequest
) -> tuple[_ResolvedAction, int]:
    """Resolve an __actions/{action_name} segment pair. Returns the resolved action and updated index."""
    if i + 1 >= len(parts):
        raise Http404("Missing action name after __actions")
    action_name = parts[i + 1]
    if isinstance(current, type) and issubclass(current, ListViewConfig):
        resolved = _resolve_action_on_list(current, action_name, request)
    elif isinstance(current, InstanceView):
        resolved = _resolve_action_on_instance(current, action_name)
    elif isinstance(current, Panel):
        resolved = _resolve_action_on_panel(current, action_name, request)
    else:
        raise Http404(f"Cannot resolve __actions on {type(current)}")
    return resolved, i + 1


def _resolve_path(
    parts: list[str],
    config: dict[str, type[ListViewConfig]],
    request: HttpRequest | None = None,
) -> _Resolved:
    """Walk the interface config tree according to URL path parts.

    Special segments like __panels, __tabs, and __actions resolve to the
    corresponding attribute on the current object, allowing further traversal.
    """
    try:
        current: _Resolved = config[parts[0]]
    except KeyError as err:
        raise Http404(f"Unknown path segment '{parts[0]}'") from err

    effective_request = request or HttpRequest()
    i = 1
    while i < len(parts):
        part = parts[i]
        if part == "__panels":
            current = _resolve_panels(current)
        elif part == "__tabs":
            current, i = _resolve_tabs(current, parts, i)
        elif part == "__actions":
            current, i = _resolve_actions(current, parts, i, effective_request)
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


def _strip_actions_from_url(url: str) -> str:
    """Strip __actions/{name} from a URL to get the parent base_url."""
    if "/__actions/" in url:
        return url[: url.index("/__actions/")]
    return url


def _dispatch_tab(
    request: HttpRequest, resolved_tab: _ResolvedTab, base_url: str, is_htmx: bool
) -> HttpResponse | str:
    """Dispatch a resolved tab. Returns an HttpResponse for HTMX, or rendered HTML string for full page."""
    iv = resolved_tab.instance_view
    tab_name = resolved_tab.tab_name
    instance_base_url = base_url.rsplit("/__tabs/", 1)[0]

    if is_htmx:
        html = iv.render_tab(request, tab_name, instance_base_url)
        return HttpResponse(html)

    return iv.render(request, base_url=instance_base_url, active_tab=tab_name)


def _render_list_view_content(
    request: HttpRequest, list_config: type[ListViewConfig], base_url: str
) -> str:
    """Render a list view with its actions."""
    list_actions = [
        action
        for action in list_config.get_actions(request)
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
    table_html = list_config.render(request, base_url=base_url)
    return actions_html + table_html


def _dispatch_resolved(
    request: HttpRequest,
    current: _Resolved,
    base_url: str,
    is_htmx: bool,
    hx_target: str = "",
) -> HttpResponse | tuple[str, str]:
    """Dispatch based on the resolved path object.

    Returns either:
    - An HttpResponse (for actions, HTMX fragments, panels)
    - A (rendered_content, heading) tuple for full-page rendering
    """
    if isinstance(current, _ResolvedAction):
        return _handle_action(
            request, current, base_url=_strip_actions_from_url(base_url)
        )

    if isinstance(current, _ResolvedTab):
        result = _dispatch_tab(request, current, base_url, is_htmx)
        if isinstance(result, HttpResponse):
            return result
        rendered_content = result

    elif isinstance(current, Panel):
        return HttpResponse(current.render(request, base_url=base_url))

    elif isinstance(current, InstanceView):
        rendered_content = current.render(request, base_url=base_url)

    elif isinstance(current, type) and issubclass(current, ListViewConfig):
        rendered_content = _render_list_view_content(request, current, base_url)

    else:
        raise Http404("Unexpected path resolution")

    if (
        is_htmx
        and not isinstance(current, _ResolvedTab)
        and hx_target != "main-content"
    ):
        return HttpResponse(rendered_content)

    heading = current.menu_label if hasattr(current, "menu_label") else ""
    return rendered_content, heading


def _build_menu_items(
    config: dict[str, type[ListViewConfig]],
    url_name: str,
    active_section: str = "",
    current_instance: Model | None = None,
) -> list[dict[str, str | bool]]:
    """Build the sidebar menu items from the config."""
    items: list[dict[str, str | bool]] = []
    for conf in config.values():
        is_active = conf.url_name == active_section
        has_instance = is_active and current_instance is not None
        instance_label = ""
        instance_url = ""
        if has_instance and current_instance is not None:
            instance_label = str(current_instance)
            instance_url = reverse(
                url_name,
                kwargs={"path_string": f"{conf.url_name}/{current_instance.pk}"},
            )
        item: dict[str, str | bool] = {
            "label": conf.menu_label,
            "url": reverse(url_name, kwargs={"path_string": conf.url_name}),
            "active": is_active,
            "expanded": has_instance,
            "instance_label": instance_label,
            "instance_url": instance_url,
        }
        items.append(item)
    return items


def _build_breadcrumbs(
    parts: list[str],
    config: dict[str, type[ListViewConfig]],
    url_name: str,
    current_instance: Model | None = None,
) -> list[dict[str, str]]:
    """Build hierarchy-based breadcrumbs.

    Returns list of dicts: [{"label": "...", "url": "..."}, ...]
    Last item has no "url" key (current page).
    """
    crumbs: list[dict[str, str]] = []

    if not parts:
        # Root landing page — no breadcrumbs needed
        return crumbs

    if parts[0] in config:
        section_config = config[parts[0]]
        section_crumb: dict[str, str] = {"label": section_config.menu_label}

        if len(parts) >= 2 and current_instance is not None:
            # Instance page: section gets a url, instance is current page
            section_crumb["url"] = reverse(url_name, kwargs={"path_string": parts[0]})
            crumbs.append(section_crumb)
            crumbs.append({"label": str(current_instance)})
        else:
            # List page: section is the current page (no url)
            crumbs.append(section_crumb)

    return crumbs


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
    hx_target = request.headers.get("HX-Target", "")
    is_navigation = is_htmx and hx_target == "main-content"
    base_url = request.path

    current_instance: Model | None = None

    if not parts:
        rendered_content = ""
        heading = ""
    else:
        current = _resolve_path(parts, config, request=request)
        result = _dispatch_resolved(
            request, current, base_url, is_htmx, hx_target=hx_target
        )
        if isinstance(result, HttpResponse):
            return result
        rendered_content, heading = result

        if isinstance(current, InstanceView):
            current_instance = current.instance
        elif isinstance(current, _ResolvedTab):
            current_instance = current.instance_view.instance

    menu_items = _build_menu_items(
        config,
        url_name,
        active_section=parts[0] if parts else "",
        current_instance=current_instance,
    )
    breadcrumbs = _build_breadcrumbs(parts, config, url_name, current_instance)

    if is_navigation:
        heading_html = f"<h1>{escape(heading)}</h1>" if heading else ""
        main_html = (
            f'<div id="main-content" class="space-y-4 pl-2 sm:pl-6">'
            f"{heading_html}{rendered_content}</div>"
        )

        breadcrumb_html = render_to_string(
            "panel_framework/partials/breadcrumbs.html",
            {"breadcrumbs": breadcrumbs, "oob": True},
            request=request,
        )

        sidebar_html = render_to_string(
            "panel_framework/partials/sidebar_nav.html",
            {"menu_items": menu_items, "oob": True},
            request=request,
        )

        return HttpResponse(main_html + breadcrumb_html + sidebar_html)

    context = {
        "menu_items": menu_items,
        "content": rendered_content,
        "heading": heading,
        "breadcrumbs": breadcrumbs,
    }

    return render(request, template_name, context)
