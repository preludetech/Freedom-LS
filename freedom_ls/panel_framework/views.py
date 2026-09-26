from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from freedom_ls.panel_framework.actions import CreateInstanceAction, PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import DataTablePanel, Panel, TabSet
from freedom_ls.panel_framework.tables import DataTable


class InstanceView:
    """Used for displaying specific instances. For example one User, Cohort, etc.

    `panel` is the root panel, usually a `PanelStack` or `TabSet`, bound to
    the instance on every request. `get_actions()` holds the actions that
    belong to the instance as a whole rather than to one panel.
    """

    panel: type[Panel]

    def __init__(self, instance: Model):
        self.instance = instance

    def get_actions(self) -> list[PanelAction]:
        return []

    def get_action(self, action_name: str) -> PanelAction | None:
        return _find_action(self.get_actions(), action_name)


class SectionConfigBase:
    """What every sidebar destination shares: its menu entry and access checks."""

    url_name: str = ""
    menu_label: str = ""
    #: A semantic icon name shown beside the menu label.
    icon: str = ""

    #: Set to a short reason string on a config that deliberately does not
    #: authorise its detail views yet. Introspectable, so a test can assert
    #: every exemption is declared rather than accidental.
    check_access_exempt_reason: str | None = None

    #: Names of request attributes that must be resolved and non-None before
    #: a detail view is served. A host app that scopes its requests — to an
    #: organisation, a tenant, a workspace — names those attributes here, and
    #: authorise_instance can then dereference them without a None check of
    #: its own. Empty by default: panel_framework has no scope concept, so a
    #: host that has none serves detail views normally.
    required_request_attrs: tuple[str, ...] = ()

    @classmethod
    def get_menu_count(cls, request: HttpRequest) -> int | None:
        """A number to show beside the menu label, or None to show none."""
        return None

    @classmethod
    def check_request(cls, request: HttpRequest) -> None:
        """The fail-closed prologue: a request with no authenticated user, or
        missing any attribute named in required_request_attrs, is a 404."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise Http404
        for attr in cls.required_request_attrs:
            if getattr(request, attr, None) is None:
                raise Http404

    @classmethod
    def check_access(cls, request: HttpRequest, instance: Model) -> None:
        """Entry point for detail-view authorisation. Do not override —
        override authorise_instance instead.

        Runs check_request before any subclass code runs, so a subclass
        overriding authorise_instance can never turn that denial into an
        AttributeError by dereferencing one of the required attributes.
        """
        cls.check_request(request)
        cls.authorise_instance(request, instance)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        """Raise Http404 unless this request may see this instance.

        Deny by default: a config that does not override this cannot serve
        detail views at all, so a new config that forgets to consider
        authorisation fails closed instead of leaking.
        """
        raise Http404


class ListViewConfig(SectionConfigBase):
    """A section that lists rows in a table, each linking to an instance view."""

    model: type[Model] | None = None
    instance_view: type[InstanceView] | None = None
    list_view: type[DataTable] | None = None

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return []

    @classmethod
    def get_action(cls, request: HttpRequest, action_name: str) -> PanelAction | None:
        return _find_action(cls.get_actions(request), action_name)

    @classmethod
    def get_instance_view(cls, request: HttpRequest, pk: str) -> InstanceView:
        if cls.model is None or cls.instance_view is None:
            raise ValueError(f"{cls.__name__} must define model and instance_view")
        # pk is a raw, visitor-supplied URL segment and these models have UUID
        # primary keys, so anything that isn't a well-formed UUID fails in the
        # field rather than the query: get_object_or_404 only turns
        # DoesNotExist into Http404, and a ValidationError would escape as a
        # 500. A guessed or mistyped URL is a missing page, not a server error.
        try:
            instance = get_object_or_404(cls.model, pk=pk)
        except ValidationError as err:
            raise Http404(f"'{pk}' is not a valid identifier") from err
        cls.check_access(request, instance)
        return cls.instance_view(instance)


class ObjectViewConfig(SectionConfigBase):
    """A section that is the instance view of one object, with no list.

    Its section URL is that instance view's URL.
    """

    instance_view: type[InstanceView] | None = None

    @classmethod
    def get_object(cls, request: HttpRequest) -> Model:
        """The one object this section shows. The framework then runs
        check_access on it."""
        raise NotImplementedError

    @classmethod
    def get_instance_view(cls, request: HttpRequest) -> InstanceView:
        if cls.instance_view is None:
            raise ValueError(f"{cls.__name__} must define instance_view")
        instance = cls.get_object(request)
        cls.check_access(request, instance)
        return cls.instance_view(instance)


class BaseViewConfig(SectionConfigBase):
    """A section that renders one root panel with no instance and no table."""

    panel: type[Panel]


class ListViewPanel(DataTablePanel):
    """The table a ListViewConfig's list page renders.

    The framework binds it as a root panel and sets `data_table` from the
    config's `list_view` on the bound instance, so every list refreshes the
    same way a table panel does.
    """

    title = ""


type SectionConfig = (
    type[ListViewConfig] | type[ObjectViewConfig] | type[BaseViewConfig]
)


@dataclass(frozen=True)
class NavGroup:
    """A headed group of sections in the sidebar."""

    heading: str
    sections: list[SectionConfig]


def sections_by_url_name(config: list[NavGroup]) -> dict[str, SectionConfig]:
    """Every section in `config`, keyed by url_name, which must be unique."""
    sections: dict[str, SectionConfig] = {}
    for group in config:
        for section in group.sections:
            if section.url_name in sections:
                raise ImproperlyConfigured(
                    f"Two sections share the url_name '{section.url_name}'."
                )
            sections[section.url_name] = section
    return sections


@dataclass(frozen=True)
class _ResolvedAction:
    action: PanelAction
    ctx: PanelContext


@dataclass(frozen=True)
class _Resolved:
    section: SectionConfig
    root: Panel
    panel: Panel
    instance: Model | None = None
    instance_view: InstanceView | None = None
    parents: tuple[Panel, ...] = field(default_factory=tuple)
    action: _ResolvedAction | None = None


def _find_action(actions: list[PanelAction], name: str) -> PanelAction | None:
    for action in actions:
        if action.action_name == name:
            return action
    return None


def _resolve_action(
    request: HttpRequest,
    section: SectionConfig,
    instance_view: InstanceView | None,
    root: Panel,
    current: Panel,
    name: str,
) -> _ResolvedAction:
    """An action addressed on the current panel, or on the page it roots."""
    if current is root:
        if issubclass(section, ListViewConfig) and instance_view is None:
            action = section.get_action(request, name)
            if action is not None:
                return _ResolvedAction(action, root.ctx)
        if instance_view is not None:
            action = instance_view.get_action(name)
            if action is not None:
                return _ResolvedAction(action, root.ctx)
    action = _find_action(current.get_actions(), name)
    if action is None:
        raise Http404(f"Action '{name}' not found")
    return _ResolvedAction(action, current.ctx)


def _bind_root(
    request: HttpRequest,
    section: SectionConfig,
    parts: list[str],
    url_prefix: str,
) -> tuple[Panel, InstanceView | None, int]:
    """Bind the section's root panel. Returns it, the instance view if there
    is one, and the index of the first path part after the root."""
    section_url = f"{url_prefix}/{parts[0]}"
    if issubclass(section, ListViewConfig):
        if len(parts) == 1 or parts[1].startswith("__"):
            if section.list_view is None:
                raise ValueError(f"{section.__name__} must define list_view")
            table = ListViewPanel(
                PanelContext(
                    request=request, instance=None, base_url=section_url, name=""
                )
            )
            table.data_table = section.list_view
            return table, None, 1
        instance_view = section.get_instance_view(request, parts[1])
        return (
            instance_view.panel(
                PanelContext(
                    request=request,
                    instance=instance_view.instance,
                    base_url=f"{section_url}/{parts[1]}",
                    name="",
                )
            ),
            instance_view,
            2,
        )
    if issubclass(section, ObjectViewConfig):
        instance_view = section.get_instance_view(request)
        return (
            instance_view.panel(
                PanelContext(
                    request=request,
                    instance=instance_view.instance,
                    base_url=section_url,
                    name="",
                )
            ),
            instance_view,
            1,
        )
    section.check_request(request)
    return (
        section.panel(
            PanelContext(request=request, instance=None, base_url=section_url, name="")
        ),
        None,
        1,
    )


def _resolve_path(
    parts: list[str],
    sections: dict[str, SectionConfig],
    request: HttpRequest,
    url_prefix: str,
) -> _Resolved:
    """Walk the URL path parts down from a section to the panel or action they address.

    `__panels/<name>` and `__tabs/<name>` step into a container's children,
    and `__actions/<name>` must come last.
    """
    try:
        section = sections[parts[0]]
    except KeyError as err:
        raise Http404(f"Unknown path segment '{parts[0]}'") from err

    root, instance_view, i = _bind_root(request, section, parts, url_prefix)
    if not root.is_shown():
        raise Http404("Panel not shown")

    current = root
    parents: list[Panel] = []
    action: _ResolvedAction | None = None
    while i < len(parts):
        segment = parts[i]
        if i + 1 >= len(parts):
            raise Http404(f"Missing name after '{segment}'")
        name = parts[i + 1]
        if segment == "__actions" and i + 2 == len(parts):
            action = _resolve_action(
                request, section, instance_view, root, current, name
            )
        elif segment in ("__panels", "__tabs") and segment == current.child_segment:
            parents.append(current)
            current = current.child(name)
        else:
            raise Http404(f"Cannot resolve path segment '{segment}'")
        i += 2

    return _Resolved(
        section=section,
        root=root,
        panel=current,
        instance=instance_view.instance if instance_view else None,
        instance_view=instance_view,
        parents=tuple(parents),
        action=action,
    )


def _handle_action(request: HttpRequest, resolved: _ResolvedAction) -> HttpResponse:
    """Check permission, then submit (POST, DELETE) or render (GET) the action."""
    action = resolved.action
    ctx = resolved.ctx

    if not action.has_permission(request, ctx.instance):
        return HttpResponse(status=403)

    if request.method in ("POST", "DELETE"):
        return action.handle_submit(ctx)
    return render(request, action.template_name, action.get_context_data(ctx))


def _vary_on_htmx(response: HttpResponse) -> HttpResponse:
    """One URL answers with a page, a bundle or a fragment depending on these
    headers, so a cache must key on them."""
    patch_vary_headers(
        response, ["HX-Request", "HX-Target", "HX-History-Restore-Request"]
    )
    return response


def _url_prefix(request: HttpRequest, path_string: str) -> str:
    """request.path with the path_string cut off: the URL a section hangs off."""
    path = request.path
    if path_string and path.endswith(path_string):
        return path[: -len(path_string)].rstrip("/")
    return path.rstrip("/")


def _main_for(
    request: HttpRequest, resolved: _Resolved
) -> tuple[str, dict[str, object], str]:
    """The view template, its context and the page heading for a resolved path."""
    root = resolved.root
    section = resolved.section
    if resolved.instance_view is not None:
        actions = [
            action
            for action in resolved.instance_view.get_actions()
            if action.has_permission(request, resolved.instance)
        ]
        return (
            "panel_framework/views/instance_view.html",
            {
                "instance": resolved.instance,
                "panel": root,
                "actions": actions,
                "ctx": root.ctx,
            },
            "",
        )
    if issubclass(section, ListViewConfig):
        list_actions = [
            action
            for action in section.get_actions(request)
            if action.has_permission(request)
        ]
        created_events = [
            action.get_created_event_name()
            for action in list_actions
            if isinstance(action, CreateInstanceAction)
        ]
        return (
            "panel_framework/views/list_view.html",
            {
                "heading": section.menu_label,
                "panel": root,
                "actions": list_actions,
                "ctx": root.ctx,
                # Space-separated event names: simple identifiers, so no JSON
                # escaping is needed in the data-* attribute.
                "refresh_events": " ".join(created_events),
                "refresh_url": root.ctx.base_url,
            },
            section.menu_label,
        )
    return (
        "panel_framework/views/base_view.html",
        {"heading": section.menu_label, "panel": root},
        section.menu_label,
    )


def _respond(
    request: HttpRequest,
    resolved: _Resolved | None,
    template_name: str,
    page_context: dict[str, object],
) -> HttpResponse:
    """Pick the response branch for a request that addresses a page or a panel.

    A plain GET, and a history restore, get the full page. htmx requests get
    the navigation bundle, one tab, or one panel's region, chosen by the
    target they name; an unrecognised target gets the navigation bundle, never
    a bare fragment.
    """
    is_htmx = request.headers.get("HX-Request") == "true"
    is_restore = request.headers.get("HX-History-Restore-Request") == "true"
    hx_target = request.headers.get("HX-Target", "")

    if not is_htmx or is_restore:
        return render(request, template_name, page_context)

    navigation_context = {
        **page_context,
        "announcement": getattr(request, "panel_announcement", None),
        "extra_oob": getattr(request, "panel_extra_oob", []),
    }
    if resolved is None or hx_target == "main-content":
        return render(
            request, "panel_framework/navigation_response.html", navigation_context
        )

    panel = resolved.panel
    parent = resolved.parents[-1] if resolved.parents else None
    if isinstance(parent, TabSet) and hx_target == parent.region_id:
        return render(
            request,
            "panel_framework/tab_response.html",
            {"panel": panel, "announcement": f"Showing {panel.title}"},
        )
    if hx_target == panel.region_id:
        return render(
            request,
            panel.region_template_name or panel.template_name,
            panel.get_context_data(),
        )
    return render(
        request, "panel_framework/navigation_response.html", navigation_context
    )


def _build_menu_items(
    config: list[NavGroup],
    url_name: str,
    request: HttpRequest,
    active_section: str = "",
    current_instance: Model | None = None,
    extra_url_kwargs: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Build the sidebar's groups of menu items from the config."""
    extra_url_kwargs = extra_url_kwargs or {}
    groups: list[dict[str, object]] = []
    for group in config:
        items: list[dict[str, object]] = []
        for section in group.sections:
            is_active = section.url_name == active_section
            instance_label = ""
            instance_url = ""
            if (
                is_active
                and current_instance is not None
                and issubclass(section, ListViewConfig)
            ):
                instance_label = str(current_instance)
                instance_url = reverse(
                    url_name,
                    kwargs={
                        "path_string": f"{section.url_name}/{current_instance.pk}",
                        **extra_url_kwargs,
                    },
                )
            items.append(
                {
                    "label": section.menu_label,
                    "url": reverse(
                        url_name,
                        kwargs={"path_string": section.url_name, **extra_url_kwargs},
                    ),
                    "icon": section.icon,
                    "count": section.get_menu_count(request),
                    "active": is_active,
                    "expanded": bool(instance_label),
                    "instance_label": instance_label,
                    "instance_url": instance_url,
                }
            )
        if items:
            groups.append({"heading": group.heading, "items": items})
    return groups


def _build_breadcrumbs(
    parts: list[str],
    sections: dict[str, SectionConfig],
    url_name: str,
    current_instance: Model | None = None,
    extra_url_kwargs: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Build hierarchy-based breadcrumbs.

    Returns list of dicts: [{"label": "...", "url": "..."}, ...]
    Last item has no "url" key (current page).

    Only a list section's instance page gets a second crumb. Tabs and panels
    below it add none, because the tab nav already shows where the reader is,
    and an object or base view is its section alone.
    """
    extra_url_kwargs = extra_url_kwargs or {}
    if not parts or parts[0] not in sections:
        return []

    section = sections[parts[0]]
    section_crumb: dict[str, str] = {"label": section.menu_label}
    if (
        issubclass(section, ListViewConfig)
        and len(parts) >= 2
        and current_instance is not None
    ):
        section_crumb["url"] = reverse(
            url_name, kwargs={"path_string": parts[0], **extra_url_kwargs}
        )
        return [section_crumb, {"label": str(current_instance)}]
    return [section_crumb]


def panel_framework_view(
    config: list[NavGroup],
    request: HttpRequest,
    path_string: str,
    template_name: str,
    url_name: str,
) -> HttpResponse:
    """Generic dispatch view for panel-framework-based interfaces.

    Parameters:
        config: the sidebar's groups of sections
        request: the Django request
        path_string: the captured URL path (e.g. "cohorts/123/__tabs/details")
        template_name: the full-page template to render (e.g. "educator_interface/interface.html")
        url_name: the URL name used for reverse() in menu building (e.g. "educator_interface:interface")

    The full-page template renders the view with
    `{% include main_template_name with main=main request=request only %}`.
    """
    sections = sections_by_url_name(config)
    parts = [p for p in path_string.split("/") if p]
    # Extra reverse() kwargs a hosting view needs on every panel_framework URL
    # (e.g. a scope segment). Read once here so every reverse() call below —
    # menu items, breadcrumbs — stays in sync without a per-call-site fix.
    extra_url_kwargs: dict[str, str] = getattr(request, "panel_url_kwargs", {})

    resolved: _Resolved | None = None
    main: dict[str, object] = {}
    main_template_name = "panel_framework/views/_main_base.html"
    heading = ""
    if parts:
        resolved = _resolve_path(
            parts, sections, request, _url_prefix(request, path_string)
        )
        if resolved.action is not None:
            return _vary_on_htmx(_handle_action(request, resolved.action))
        main_template_name, main, heading = _main_for(request, resolved)

    page_context: dict[str, object] = {
        "menu_groups": _build_menu_items(
            config,
            url_name,
            request,
            active_section=parts[0] if parts else "",
            current_instance=resolved.instance if resolved else None,
            extra_url_kwargs=extra_url_kwargs,
        ),
        "heading": heading,
        "breadcrumbs": _build_breadcrumbs(
            parts,
            sections,
            url_name,
            resolved.instance if resolved else None,
            extra_url_kwargs=extra_url_kwargs,
        ),
        "main": main,
        "main_template_name": main_template_name,
    }
    return _vary_on_htmx(_respond(request, resolved, template_name, page_context))
