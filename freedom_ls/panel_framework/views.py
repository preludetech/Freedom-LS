from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db.models import Model
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    QueryDict,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.text import slugify

from freedom_ls.base.csv_safety import UTF8_BOM
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.bulk_actions import (
    BulkAction,
    Selection,
    parse_selection,
    resolve_selection,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import DataTablePanel, Panel, TabSet
from freedom_ls.panel_framework.quick_view import QuickView
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
    #: its own. Empty by default: the framework asks get_scope for a scope
    #: object rather than assuming one, so a host that names none here still
    #: requires no request attribute of its own.
    required_request_attrs: tuple[str, ...] = ()

    @classmethod
    def get_menu_count(cls, request: HttpRequest) -> int | None:
        """A number to show beside the menu label, or None to show none."""
        return None

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        """How the page heading, the sidebar sub-item and the back link name
        one of this section's instances. `str(instance)` by default; a
        section whose model's `str()` is not a name overrides this."""
        return str(instance)

    @classmethod
    def get_scope(cls, request: HttpRequest) -> Model | None:
        """The object a list-level action or panel is asked about, when this
        section scopes its requests to one. None by default."""
        return None

    @classmethod
    def has_capability(
        cls, request: HttpRequest, capability: str, scope: Model
    ) -> bool:
        """Whether `request` may exercise `capability` on `scope`.

        Deny by default, like authorise_instance: a config that does not
        override this cannot grant anything, so a new config that forgets to
        wire capability checks fails closed instead of leaking.
        """
        return False

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

    @classmethod
    def get_denied_context(
        cls, request: HttpRequest, capability: str | None, scope: Model | None
    ) -> dict[str, str]:
        """Copy for the 403 fragment shown when a visible action is denied.

        `capability` and `scope` may both be `None`, because a consumer's own
        `has_permission` can deny an action that declares no capability. A
        section with an audience to name overrides this with something more
        specific than the generic default.
        """
        return {"who_to_ask": "Ask an administrator."}


class ListViewConfig(SectionConfigBase):
    """A section that lists rows in a table, each linking to an instance view."""

    model: type[Model] | None = None
    instance_view: type[InstanceView] | None = None
    list_view: type[DataTable] | None = None
    #: The list page's own table key. Required whenever `list_view` is set.
    table_key: str
    #: Domain events that make the list's table region re-fetch itself.
    refresh_events: tuple[str, ...] = ()
    #: The drawer a row's quick-view trigger opens. None means rows have no
    #: quick view and the __quick-view route 404s.
    quick_view: type[QuickView] | None = None

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return []

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
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
        """The one object this section shows. Called after check_request, so
        it may dereference required_request_attrs; the framework then runs
        check_access on the object."""
        raise NotImplementedError

    @classmethod
    def get_instance_view(cls, request: HttpRequest) -> InstanceView:
        if cls.instance_view is None:
            raise ValueError(f"{cls.__name__} must define instance_view")
        cls.check_request(request)
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
    same way a table panel does. `bulk_actions` is set the same way, from the
    config's `get_bulk_actions`.
    """

    title = ""
    bulk_actions: list[BulkAction] = []

    def get_bulk_actions(self) -> list[BulkAction]:
        return self.bulk_actions


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
    action: PanelAction | BulkAction
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
    #: True when the path addresses an instance's quick-view drawer rather
    #: than any panel or action, so panel_framework_view can branch to it
    #: before touching the panel tree at all.
    quick_view: bool = False


class _NamedAction(Protocol):
    action_name: str


def _find_action[T: _NamedAction](actions: list[T], name: str) -> T | None:
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
    panel_action = _find_action(current.get_actions(), name)
    if panel_action is not None:
        return _ResolvedAction(panel_action, current.ctx)
    if isinstance(current, DataTablePanel):
        bulk_action = _find_action(current.get_bulk_actions(), name)
        if bulk_action is not None:
            return _ResolvedAction(bulk_action, current.ctx)
    raise Http404(f"Action '{name}' not found")


def _bind_root(
    request: HttpRequest,
    section: SectionConfig,
    parts: list[str],
    section_url: str,
) -> tuple[Panel, InstanceView | None, int]:
    """Bind the section's root panel. Returns it, the instance view if there
    is one, and the index of the first path part after the root."""
    if issubclass(section, ListViewConfig):
        if len(parts) == 1 or parts[1].startswith("__"):
            if section.list_view is None:
                raise ValueError(f"{section.__name__} must define list_view")
            # No check_request here, as today: the list root binds (and the
            # unauthenticated stub playwright tests browse it) before any
            # access check runs.
            table = ListViewPanel(
                PanelContext(
                    request=request,
                    instance=None,
                    base_url=section_url,
                    name="",
                    config=section,
                    scope=section.get_scope(request),
                    page_url=section_url,
                )
            )
            table.data_table = section.list_view
            table.table_key = section.table_key
            table.bulk_actions = section.get_bulk_actions(request)
            return table, None, 1
        instance_view = section.get_instance_view(request, parts[1])
        instance_base_url = f"{section_url}/{parts[1]}"
        return (
            instance_view.panel(
                PanelContext(
                    request=request,
                    instance=instance_view.instance,
                    base_url=instance_base_url,
                    name="",
                    config=section,
                    scope=section.get_scope(request),
                    page_url=instance_base_url,
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
                    config=section,
                    scope=section.get_scope(request),
                    page_url=section_url,
                )
            ),
            instance_view,
            1,
        )
    section.check_request(request)
    return (
        section.panel(
            PanelContext(
                request=request,
                instance=None,
                base_url=section_url,
                name="",
                config=section,
                scope=section.get_scope(request),
                page_url=section_url,
            )
        ),
        None,
        1,
    )


def _resolve_path(
    parts: list[str],
    sections: dict[str, SectionConfig],
    request: HttpRequest,
    section_url: str,
) -> _Resolved:
    """Walk the URL path parts down from a section to the panel or action they address.

    `__panels/<name>` and `__tabs/<name>` step into a container's children,
    and `__actions/<name>` must come last.
    """
    try:
        section = sections[parts[0]]
    except KeyError as err:
        raise Http404(f"Unknown path segment '{parts[0]}'") from err

    root, instance_view, i = _bind_root(request, section, parts, section_url)
    if not root.is_shown():
        raise Http404("Panel not shown")

    # A terminal __quick-view segment addresses the instance's drawer, not
    # any panel or action, so it is matched before the loop below ever
    # starts. get_instance_view has already run check_access on instance_view
    # by this point, so the drawer route adds no authorisation of its own.
    if (
        parts[i:] == ["__quick-view"]
        and instance_view is not None
        and issubclass(section, ListViewConfig)
    ):
        return _Resolved(
            section=section,
            root=root,
            panel=root,
            instance=instance_view.instance,
            instance_view=instance_view,
            quick_view=True,
        )

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


@dataclass(frozen=True)
class _BulkConfirmation:
    """A bulk action's confirmation or error state for a JavaScript-off
    request. Rendered as a full interface page rather than an htmx fragment,
    so the reader sees the same message with the surrounding page chrome."""

    count: int
    noun: str
    action: BulkAction
    action_url: str
    selection: Selection
    error: str
    status: int


def _handle_bulk_action(
    request: HttpRequest, action: BulkAction, ctx: PanelContext, panel: DataTablePanel
) -> HttpResponse | _BulkConfirmation:
    """Permission, selection, resolution, confirmation and execution for one
    bulk-action POST.

    An htmx request always gets an HTML fragment back. A plain request gets
    one too once confirmed and executed; until then it gets a
    `_BulkConfirmation`, since the confirmation step must render with the
    page's own chrome rather than as a bare fragment.
    """
    if not action.has_permission(request):
        return HttpResponse(status=403)

    is_htmx = request.headers.get("HX-Request") == "true"
    action_url = action.get_action_url(ctx)
    noun = str(panel.get_queryset(request).model._meta.verbose_name_plural)

    def _confirm(
        selection: Selection, count: int, error: str, status: int
    ) -> HttpResponse | _BulkConfirmation:
        if is_htmx:
            html = render_to_string(
                action.confirm_template_name,
                {
                    "action": action,
                    "action_url": action_url,
                    "selection": selection,
                    "count": count,
                    "noun": noun,
                    "error": error,
                },
                request=request,
            )
            return HttpResponse(html, status=status)
        return _BulkConfirmation(
            count, noun, action, action_url, selection, error, status
        )

    selection = parse_selection(request)
    if selection.mode != "keys":
        return _confirm(selection, 0, "Not supported yet", 422)

    queryset = resolve_selection(panel, request, selection)
    count = queryset.count()
    if count == 0:
        return _confirm(selection, count, "Nothing selected", 422)
    if count > action.max_rows:
        message = f"{count} selected; the limit is {action.max_rows}"
        return _confirm(selection, count, message, 422)

    if request.POST.get("confirmed") != "1":
        return _confirm(selection, count, "", 200)

    action.execute(request, queryset)
    redirect_url = _history_url(panel, request)
    if is_htmx:
        response = HttpResponse(status=204)
        response["HX-Redirect"] = redirect_url
        return response
    return HttpResponseRedirect(redirect_url, status=303)


def _handle_action(
    request: HttpRequest, resolved: _ResolvedAction, panel: Panel | None = None
) -> HttpResponse | _BulkConfirmation:
    """Check permission, then submit (POST, DELETE) or render (GET) the action.

    A BulkAction runs the confirm-then-act flow instead, over `panel` — the
    DataTablePanel it was resolved on, always set by the caller for a
    BulkAction.
    """
    action = resolved.action
    ctx = resolved.ctx

    if isinstance(action, BulkAction):
        if not isinstance(panel, DataTablePanel):
            raise ImproperlyConfigured(
                "A BulkAction must resolve with its DataTablePanel."
            )
        return _handle_bulk_action(request, action, ctx, panel)

    if not action.has_permission(ctx):
        if request.headers.get("HX-Request") != "true":
            raise PermissionDenied
        context = {
            "action_label": action.label,
            **ctx.config.get_denied_context(
                request, action.get_capability(ctx), action.permission_object(ctx)
            ),
        }
        return render(
            request, "panel_framework/partials/action_denied.html", context, status=403
        )

    if request.method in ("POST", "DELETE"):
        return action.handle_submit(ctx)
    return render(request, action.template_name, action.get_context_data(ctx))


def _is_htmx_action_request(request: HttpRequest, parts: list[str]) -> bool:
    return (
        request.headers.get("HX-Request") == "true"
        and len(parts) >= 2
        and parts[-2] == "__actions"
    )


def _handle_quick_view(
    request: HttpRequest,
    section: SectionConfig,
    instance: Model | None,
    instance_url: str,
) -> HttpResponse:
    """Render the drawer frame for `instance`, or send a non-htmx request to
    its full page.

    Called only once _resolve_path has matched a terminal __quick-view
    segment against a ListViewConfig with a bound instance, so
    get_instance_view has already run check_access (and therefore
    authorise_instance) on instance.
    """
    if not issubclass(section, ListViewConfig) or section.quick_view is None:
        raise Http404(f"{section.__name__} has no quick view")
    if instance is None:
        raise ValueError("A quick-view route must resolve to a bound instance")
    if request.headers.get("HX-Request") != "true":
        return redirect(instance_url)
    quick_view = section.quick_view(request, instance)
    return render(
        request,
        "panel_framework/quick_view/frame.html",
        {
            "quick_view": quick_view,
            "title": quick_view.get_title(),
            "subtitle": quick_view.get_subtitle(),
            # Space-separated event names: simple identifiers, so no JSON
            # escaping is needed in the data-* attribute.
            "refresh_events": " ".join(quick_view.refresh_events),
            "entity_id": str(instance.pk),
            **quick_view.get_context_data(),
        },
    )


def _vary_on_htmx(
    response: HttpResponse | StreamingHttpResponse,
) -> HttpResponse | StreamingHttpResponse:
    """One URL answers with a page, a bundle or a fragment depending on these
    headers, so a cache must key on them."""
    patch_vary_headers(
        response, ["HX-Request", "HX-Target", "HX-History-Restore-Request"]
    )
    return response


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
            if action.has_permission(root.ctx)
        ]
        if resolved.instance is None:
            raise ValueError("An instance view must resolve with its instance")
        return (
            "panel_framework/views/instance_view.html",
            {
                "instance": resolved.instance,
                "title": section.get_instance_label(resolved.instance),
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
            if action.has_permission(root.ctx)
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
                "refresh_events": " ".join(section.refresh_events),
                "refresh_url": root.ctx.base_url,
            },
            section.menu_label,
        )
    return (
        "panel_framework/views/base_view.html",
        {"heading": section.menu_label, "panel": root},
        section.menu_label,
    )


def _merge_current_url_state(request: HttpRequest, panel: DataTablePanel) -> None:
    """Replace the request's sibling-table state with the browser's live state.

    A table's links are rendered once, so after a sibling table on the same
    page changes they still carry that sibling's old parameters. htmx sends
    the address bar as `HX-Current-URL`; when it names this panel's page,
    every parameter outside this table's own namespace is taken from it, and
    this table's own parameters from the request. Only the header's path and
    query are read, never its host.
    """
    current = urlsplit(request.headers.get("HX-Current-URL", ""))
    if current.path != panel.ctx.page_url:
        return
    prefix = f"{panel.table_key}-"
    merged = QueryDict(mutable=True)
    for name, values in QueryDict(current.query).lists():
        if not name.startswith(prefix):
            merged.setlist(name, values)
    for name, values in request.GET.lists():
        if name.startswith(prefix):
            merged.setlist(name, values)
    query_string = merged.urlencode()
    request.GET = QueryDict(query_string)
    request.META["QUERY_STRING"] = query_string


def _is_current_url(request: HttpRequest, url: str) -> bool:
    """Whether `url` is the path and query already in the address bar, as
    htmx reports it in `HX-Current-URL`, ignoring a trailing slash on the
    path. A swap that lands there, such as a list's refresh after a create,
    leaves history alone rather than stacking a duplicate entry."""
    current = urlsplit(request.headers.get("HX-Current-URL", ""))
    target = urlsplit(url)
    return (current.path.rstrip("/"), current.query) == (
        target.path.rstrip("/"),
        target.query,
    )


def _history_url(panel: DataTablePanel, request: HttpRequest) -> str:
    """The URL a table region's response pushes into the address bar: the
    page this panel's tab owns, carrying the request's full query string."""
    query_string = request.META.get("QUERY_STRING", "")
    if query_string:
        return f"{panel.ctx.page_url}?{query_string}"
    return panel.ctx.page_url


class _Echo:
    """A file-like object whose `write` hands back the string it was given
    instead of buffering it, so `csv.writer` can drive a generator that
    `StreamingHttpResponse` streams one row at a time."""

    def write(self, value: str) -> str:
        return value


def _export_response(
    request: HttpRequest, panel: DataTablePanel
) -> StreamingHttpResponse:
    """Stream `panel`'s current rows as a formula-safe CSV.

    Honours the table's search, filters and sort but never its pagination:
    an export is every matching row, not one page of them. The queryset is
    built here, before the streaming response is returned, so it is scoped
    to the request's site while that scope is still available -- a
    `StreamingHttpResponse`'s body is read after the middleware that clears
    the site thread local has already run.
    """
    columns = panel.data_table.get_export_columns()
    if not columns:
        raise Http404("This table has no CSV export")
    if request.GET.get(f"{panel.table_key}-export") != "csv":
        raise Http404("Unsupported export format")
    _query, queryset = panel.narrow(request)

    def rows() -> Iterator[str]:
        echo = _Echo()
        writer = csv.writer(echo)
        yield UTF8_BOM
        yield writer.writerow([column.header for column in columns])
        for row in queryset.iterator(chunk_size=500):
            yield writer.writerow([column.cell(row) for column in columns])

    response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    scope_slug = slugify(panel.get_export_scope_slug(request))
    scope_part = f"-{scope_slug}" if scope_slug else ""
    filename = f"{panel.table_key}{scope_part}-{timezone.localdate().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _respond(
    request: HttpRequest,
    resolved: _Resolved | None,
    template_name: str,
    page_context: dict[str, object],
) -> HttpResponse | StreamingHttpResponse:
    """Pick the response branch for a request that addresses a page or a panel.

    A plain GET, and a history restore, get the full page. htmx requests get
    the navigation bundle, one tab, or one panel's region, chosen by the
    target they name; an unrecognised target gets the navigation bundle, never
    a bare fragment. Before any of that, a table panel's export flag gets a
    streamed CSV instead.
    """
    if resolved is not None and isinstance(resolved.panel, DataTablePanel):
        table_panel = resolved.panel
        if f"{table_panel.table_key}-export" in request.GET:
            return _export_response(request, table_panel)

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
        if not isinstance(panel, DataTablePanel):
            return render(
                request,
                panel.region_template_name or panel.template_name,
                panel.get_context_data(),
            )
        _merge_current_url_state(request, panel)
        response = render(
            request, "panel_framework/table_response.html", panel.get_context_data()
        )
        history_url = _history_url(panel, request)
        is_search = request.headers.get("HX-Trigger") == f"{panel.table_key}-search"
        if _is_current_url(request, history_url):
            # "false" skips htmx's history update, and with it the
            # beforeHistorySave that closes an open modal or quick view.
            response["HX-Replace-Url"] = "false"
        elif is_search:
            response["HX-Replace-Url"] = history_url
        else:
            response["HX-Push-Url"] = history_url
        return response
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
                instance_label = section.get_instance_label(current_instance)
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
    Last item has no "url" key (current page). The partial renders the trail
    as a back link to the section (partials/breadcrumbs.html).

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
        return [section_crumb, {"label": section.get_instance_label(current_instance)}]
    return [section_crumb]


def panel_framework_view(
    config: list[NavGroup],
    request: HttpRequest,
    path_string: str,
    template_name: str,
    url_name: str,
) -> HttpResponse | StreamingHttpResponse:
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
    bulk_status = 200
    if parts:
        # Reversed rather than sliced off request.path: a host may render a
        # different path_string than the one it was asked for, and request.path
        # would then point every table and action URL at the wrong page.
        section_url = reverse(
            url_name, kwargs={"path_string": parts[0], **extra_url_kwargs}
        )
        try:
            resolved = _resolve_path(parts, sections, request, section_url)
        except Http404:
            # htmx drops a bare 404, so an action the page offered would
            # silently do nothing once its object left the user's scope.
            if _is_htmx_action_request(request, parts):
                return _vary_on_htmx(
                    render(
                        request,
                        "panel_framework/partials/action_unavailable.html",
                        status=404,
                    )
                )
            raise
        if resolved.quick_view:
            return _vary_on_htmx(
                _handle_quick_view(
                    request,
                    resolved.section,
                    resolved.instance,
                    resolved.root.ctx.base_url,
                )
            )
        if resolved.action is not None:
            result = _handle_action(request, resolved.action, resolved.panel)
            if not isinstance(result, _BulkConfirmation):
                return _vary_on_htmx(result)
            # A JavaScript-off bulk-action POST: render its message and
            # confirm form as this page's main content, with the page's own
            # chrome (menu, breadcrumbs) built the same way as any other
            # request below, rather than as a bare fragment.
            main_template_name = "panel_framework/views/bulk_confirmation.html"
            main = {
                "action": result.action,
                "action_url": result.action_url,
                "count": result.count,
                "noun": result.noun,
                "selection": result.selection,
                "error": result.error,
                "page_url": resolved.panel.ctx.page_url,
            }
            heading = result.action.label
            bulk_status = result.status
        else:
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
    response = _vary_on_htmx(_respond(request, resolved, template_name, page_context))
    response.status_code = bulk_status
    return response
