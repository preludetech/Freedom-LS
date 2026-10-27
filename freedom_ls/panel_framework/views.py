from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from django import forms
from django.contrib import messages
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db.models import Model, QuerySet
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

from freedom_ls.base.csv_import import EchoWriter
from freedom_ls.base.csv_safety import UTF8_BOM
from freedom_ls.panel_framework.actions import (
    PanelAction,
    count_noun,
    denied_response,
)
from freedom_ls.panel_framework.bulk_actions import (
    BackgroundRun,
    BulkAction,
    BulkConfirmForm,
    BulkOutcome,
    BulkResult,
    ConfirmationWording,
    Selection,
    parse_selection,
    resolve_selection,
)
from freedom_ls.panel_framework.bulk_runs import (
    action_for,
    run_label,
    run_summary,
    stopped_after,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import BULK_RUN_STARTED_EVENT, build_hx_trigger
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus, scope_lookup
from freedom_ls.panel_framework.panels import DataTablePanel, Panel, TabSet
from freedom_ls.panel_framework.quick_view import QuickView
from freedom_ls.panel_framework.tables import DataTable


@dataclass(frozen=True)
class StatusBadge:
    """A status chip: a `panel-status-badge` tone and its label."""

    tone: str
    label: str


@dataclass(frozen=True)
class HeaderStat:
    """One labelled figure shown inline under an instance heading."""

    label: str
    value: str


class InstanceView:
    """Used for displaying specific instances. For example one User, Cohort, etc.

    `panel` is the root panel, usually a `PanelStack` or `TabSet`, bound to
    the instance on every request. `get_actions()` holds the actions that
    belong to the instance as a whole rather than to one panel.
    """

    panel: type[Panel]
    #: Domain events that make the page header (stats and tab counts)
    #: re-fetch itself.
    header_refresh_events: tuple[str, ...] = ()

    def __init__(self, instance: Model):
        self.instance = instance

    def get_actions(self) -> list[PanelAction]:
        return []

    def get_status_badge(self) -> StatusBadge | None:
        """A badge beside the heading, or None for none."""
        return None

    def get_stats(self) -> list[HeaderStat]:
        """Inline figures under the heading, in order. Empty for none."""
        return []

    def get_subtitle(self) -> str:
        """One muted line under the heading, or an empty string for none."""
        return ""

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
    #: A template rendered above the list's table, for a section's own help
    #: copy. None renders nothing there.
    intro_template_name: str | None = None

    #: Names of request attributes that must be resolved and non-None before
    #: a detail view is served. A host app that scopes its requests — to an
    #: organisation, a tenant, a workspace — names those attributes here, and
    #: authorise_instance can then dereference them without a None check of
    #: its own. Empty by default: the framework asks get_scope for a scope
    #: object rather than assuming one, so a host that names none here still
    #: requires no request attribute of its own.
    required_request_attrs: tuple[str, ...] = ()

    #: The capability a request needs to see this section at all, asked on
    #: get_scope's object. None means the section shows whenever the
    #: interface itself is reachable. A section the request cannot see is
    #: left out of the menu and every path under it is a 404, so its
    #: existence is never confirmed to someone outside its audience.
    view_capability: str | None = None

    @classmethod
    def is_visible(cls, request: HttpRequest) -> bool:
        """Whether `request` may see this section in the menu and reach its paths."""
        if cls.view_capability is None:
            return True
        scope = cls.get_scope(request)
        if scope is None:
            return False
        return cls.has_capability(request, cls.view_capability, scope)

    @classmethod
    def is_available(cls, request: HttpRequest) -> bool:
        """Whether this section exists for `request`. An unavailable section
        has no menu entry and every path under it is a 404."""
        return True

    @classmethod
    def get_menu_count(cls, request: HttpRequest) -> int | None:
        """A number to show beside the menu label, or None to show none."""
        return None

    @classmethod
    def get_menu_count_url(cls, request: HttpRequest) -> str | None:
        """A URL returning the menu count as an HTML fragment, or None.

        When set, the sidebar renders a self-polling element that fetches the
        count from this URL instead of rendering `get_menu_count` with the
        page, so navigating never pays for the count query."""
        return None

    @classmethod
    def get_menu_count_poll_seconds(cls) -> int:
        """Seconds between polls of `get_menu_count_url`."""
        return 60

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
    def get_intro_context(cls, request: HttpRequest) -> dict[str, object]:
        """Context the intro template renders with. Empty by default."""
        return {}

    @classmethod
    def get_cell_context(cls, request: HttpRequest) -> dict[str, object]:
        """Extra context every cell template of this list renders with,
        computed once per request rather than once per row. Empty by default."""
        return {}

    @classmethod
    def get_action(cls, request: HttpRequest, action_name: str) -> PanelAction | None:
        return _find_action(cls.get_actions(request), action_name)

    @classmethod
    def get_instance_view(cls, request: HttpRequest, pk: str) -> InstanceView:
        if cls.model is None:
            raise ValueError(f"{cls.__name__} must define model")
        if cls.instance_view is None:
            raise Http404(f"{cls.__name__} has no instance pages")
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
    config's `get_bulk_actions`. `cell_context` is set from the config's
    `get_cell_context` and merged into the context the cell templates render
    with.
    """

    title = ""
    actions: list[PanelAction] = []
    bulk_actions: list[BulkAction] = []
    cell_context: dict[str, object] = {}

    def get_actions(self) -> list[PanelAction]:
        return self.actions

    def get_bulk_actions(self) -> list[BulkAction]:
        return self.bulk_actions

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context.update(self.cell_context)
        # The page header renders the footer actions, so the card must not
        # repeat them; an empty-state template renders them from header_actions.
        context["header_actions"] = context["actions"]
        context["actions"] = []
        return context


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
    #: The id of the recorded bulk run whose status the path polls, on
    #: `panel`, the table it was started from.
    run_id: str | None = None


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
            table.actions = section.get_actions(request)
            table.bulk_actions = section.get_bulk_actions(request)
            table.cell_context = section.get_cell_context(request)
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
    and `__actions/<name>` or `__runs/<id>` must come last.
    """
    try:
        section = sections[parts[0]]
    except KeyError as err:
        raise Http404(f"Unknown path segment '{parts[0]}'") from err
    if not (section.is_visible(request) and section.is_available(request)):
        raise Http404("Section not shown")

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
    run_id: str | None = None
    while i < len(parts):
        segment = parts[i]
        if i + 1 >= len(parts):
            raise Http404(f"Missing name after '{segment}'")
        name = parts[i + 1]
        if segment == "__actions" and i + 2 == len(parts):
            action = _resolve_action(
                request, section, instance_view, root, current, name
            )
        elif segment == "__runs" and i + 2 == len(parts):
            run_id = name
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
        run_id=run_id,
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
    wording: ConfirmationWording | None = None
    notice: str = ""
    expected_count: int = 0
    confirm_disabled: bool = False
    form: forms.Form | None = None

    def context(self) -> dict[str, object]:
        return {
            "action": self.action,
            "action_url": self.action_url,
            "selection": self.selection,
            "count": self.count,
            "noun": self.noun,
            "error": self.error,
            "wording": self.wording,
            "notice": self.notice,
            "expected_count": self.expected_count,
            "confirm_disabled": self.confirm_disabled,
            "form": self.form,
        }


@dataclass(frozen=True)
class _BulkResultPage:
    """A confirmed bulk action's result for a JavaScript-off request,
    rendered as a full interface page. `page_url` is the table's page with
    the request's query string, so the link back keeps its state."""

    action: BulkAction
    result: BulkResult
    noun: str
    headline: str
    page_url: str


def _result_response(
    request: HttpRequest,
    panel: DataTablePanel,
    action: BulkAction,
    result: BulkResult,
    noun: str,
    headline: str,
    changed_keys: list[str],
) -> HttpResponse | _BulkResultPage:
    """The summary of a finished run.

    Over htmx it replaces the confirmation in the modal and fires the
    panel's refresh events, so the table updates behind the summary. Without
    JavaScript it is a page of its own.
    """
    if request.headers.get("HX-Request") != "true":
        return _BulkResultPage(
            action, result, noun, headline, _history_url(panel, request)
        )
    return bulk_result_fragment(
        request,
        action,
        result,
        noun,
        headline,
        dict.fromkeys(_table_refresh_events(panel), changed_keys),
    )


def bulk_result_fragment(
    request: HttpRequest,
    action: BulkAction,
    result: BulkResult,
    noun: str,
    headline: str,
    refresh: dict[str, list[str]],
) -> HttpResponse:
    """The result modal fragment, firing `refresh` so the table updates
    behind it. A background run's status poll answers with this too."""
    html = render_to_string(
        action.result_template_name,
        _result_context(action, result, noun, headline),
        request=request,
    )
    response = HttpResponse(html)
    response["HX-Trigger"] = build_hx_trigger(refresh)
    return response


def _table_refresh_events(panel: DataTablePanel) -> tuple[str, ...]:
    """The events that refresh `panel`'s table. A list page's table is
    refreshed by its section's events rather than the panel's own."""
    config = panel.ctx.config
    if issubclass(config, ListViewConfig):
        return config.refresh_events
    return panel.refresh_events


def _result_context(
    action: BulkAction, result: BulkResult, noun: str, headline: str
) -> dict[str, object]:
    return {
        "action": action,
        "result": result,
        "noun": noun,
        "headline": headline,
        "other_counts": [item for item in result.counts if item.status != "changed"],
    }


def _background_response(
    request: HttpRequest, panel: DataTablePanel, action: BulkAction, run: BackgroundRun
) -> HttpResponse:
    """The reader stays on the table. Over htmx the modal closes and the
    table's selection component polls `run.status_url` until the result
    arrives; without JavaScript the table page reloads with a flash."""
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Trigger"] = build_hx_trigger(
            {},
            close_modal=True,
            signals={
                BULK_RUN_STARTED_EVENT: {
                    "region": panel.region_id,
                    "action": action.action_name,
                    "label": action.label,
                    "status_url": run.status_url,
                }
            },
        )
        return response
    messages.info(
        request,
        f"{action.label} is running in the background. "
        "You'll get a notification when it finishes.",
    )
    return HttpResponseRedirect(_history_url(panel, request), status=303)


def _confirmation_response(
    request: HttpRequest, confirmation: _BulkConfirmation
) -> HttpResponse | _BulkConfirmation:
    """The confirmation or error state: an htmx fragment, or the
    `_BulkConfirmation` itself for the page-level render."""
    if request.headers.get("HX-Request") == "true":
        html = render_to_string(
            confirmation.action.confirm_template_name,
            confirmation.context(),
            request=request,
        )
        return HttpResponse(html, status=confirmation.status)
    return confirmation


def _background_wording(queryset: QuerySet, count: int) -> ConfirmationWording:
    """The confirmation for a run too large to preview: the total, and where
    the skips will be reported."""
    return ConfirmationWording(
        sentence=f"This will affect {count_noun(queryset.model, count)}.",
        consequences=[
            "It runs in the background. You'll get a notification when it finishes."
        ],
    )


def _handle_bulk_action(
    request: HttpRequest, action: BulkAction, ctx: PanelContext, panel: DataTablePanel
) -> HttpResponse | _BulkConfirmation | _BulkResultPage:
    """Permission, selection, resolution, confirmation and execution for one
    bulk-action POST.

    An htmx request always gets an HTML fragment back. A plain request gets
    a `_BulkConfirmation` or `_BulkResultPage` instead, since both must
    render with the page's own chrome rather than as a bare fragment.
    """
    if not action.has_permission(request):
        return HttpResponse(status=403)

    action_url = action.get_action_url(ctx)
    noun = str(panel.get_queryset(request).model._meta.verbose_name_plural)

    def error_response(
        selection: Selection, count: int, error: str
    ) -> HttpResponse | _BulkConfirmation:
        return _confirmation_response(
            request,
            _BulkConfirmation(count, noun, action, action_url, selection, error, 422),
        )

    selection = parse_selection(request)
    queryset = resolve_selection(panel, request, selection)
    count = queryset.count()
    if count == 0:
        return error_response(selection, count, "Nothing selected")
    in_background = action.runs_in_background(count)
    # A whole filtered table is bounded only when a task does the work.
    if count > action.max_rows and not (
        selection.mode == "all_matching" and in_background
    ):
        what = "matching" if selection.mode == "all_matching" else "selected"
        message = f"{count} {what}; the limit is {action.max_rows}"
        return error_response(selection, count, message)

    form = BulkConfirmForm(request.POST)
    if not form.is_valid():
        return error_response(selection, count, "The request was not valid")
    confirmed = bool(form.cleaned_data["confirmed"])
    expected_count = form.cleaned_data["expected_count"]
    if confirmed and expected_count is None:
        return error_response(selection, count, "The request was not valid")

    picker = action.get_form(
        request, request.POST if form.cleaned_data["refresh"] or confirmed else None
    )
    cleaned_data: dict[str, object] = {}
    if picker is not None:
        if picker.is_bound and picker.is_valid():
            cleaned_data = picker.cleaned_data
        else:
            # Without a valid choice there is nothing to preview. An unbound
            # picker is the first view of the dialog, so it is not an error;
            # a bound one that failed is.
            return _confirmation_response(
                request,
                _BulkConfirmation(
                    count=count,
                    noun=noun,
                    action=action,
                    action_url=action_url,
                    selection=selection,
                    error="",
                    status=422 if picker.is_bound else 200,
                    wording=ConfirmationWording(
                        sentence=f"{count_noun(queryset.model, count)} selected."
                    ),
                    expected_count=count,
                    confirm_disabled=True,
                    form=picker,
                ),
            )

    classified: dict[str, BulkOutcome] | None = (
        None if in_background else action.classify_all(request, queryset, cleaned_data)
    )
    changed_count = (
        count
        if classified is None
        else sum(1 for item in classified.values() if item.status == "changed")
    )

    def confirmation(status: int = 200, notice: str = "") -> _BulkConfirmation:
        # The wording's cost grows with the selection, so it is built only
        # for a response that shows it; a confirmed run never does.
        wording = (
            _background_wording(queryset, count)
            if in_background
            else action.confirmation_wording(
                request, queryset, classified, cleaned_data
            )
        )
        return _BulkConfirmation(
            count=count,
            noun=noun,
            action=action,
            action_url=action_url,
            selection=selection,
            error="",
            status=status,
            wording=wording,
            notice=notice,
            expected_count=count,
            confirm_disabled=changed_count == 0,
            form=picker,
        )

    if not confirmed:
        return _confirmation_response(request, confirmation())
    if expected_count != count:
        return _confirmation_response(
            request,
            confirmation(422, "The selection changed since you opened this."),
        )
    if changed_count == 0:
        return _confirmation_response(request, confirmation(422))

    selected_keys = [str(pk) for pk in queryset.values_list("pk", flat=True)]
    outcome = action.execute(ctx, queryset, cleaned_data)
    if isinstance(outcome, BackgroundRun):
        return _background_response(request, panel, action, outcome)
    headline = f"{count_noun(queryset.model, outcome.changed)} changed."
    return _result_response(
        request, panel, action, outcome, noun, headline, selected_keys
    )


def _handle_action(
    request: HttpRequest, resolved: _ResolvedAction, panel: Panel | None = None
) -> HttpResponse | _BulkConfirmation | _BulkResultPage:
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
        return denied_response(ctx, action)

    if request.method in ("POST", "DELETE"):
        return action.handle_submit(ctx)
    return render(request, action.template_name, action.get_context_data(ctx))


def _is_htmx_action_request(request: HttpRequest, parts: list[str]) -> bool:
    return (
        request.headers.get("HX-Request") == "true"
        and len(parts) >= 2
        and parts[-2] in ("__actions", "__runs")
    )


def _handle_run_status(request: HttpRequest, resolved: _Resolved) -> HttpResponse:
    """Polled by the table a background run was started from: 204 while it
    runs, then the result modal, which refreshes the table behind it.

    Only the requester sees a run, and only from the table and scope it was
    started on; anyone else, and a run from elsewhere, gets the 404 a missing
    one does. The list root binds without `check_request`, so the
    authentication check is made here rather than assumed.
    """
    panel = resolved.panel
    if not isinstance(panel, DataTablePanel) or not request.user.is_authenticated:
        raise Http404("No such run")
    runs = BulkActionRun.objects.filter(
        requested_by=request.user,
        table_key=panel.table_key,
        **scope_lookup(panel.ctx.scope),
    )
    try:
        run = get_object_or_404(runs, pk=resolved.run_id)
    except ValidationError as err:
        raise Http404(f"'{resolved.run_id}' is not a valid identifier") from err
    if run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
        return HttpResponse(status=204)
    action = action_for(run)
    if action is not None:
        action.on_result_shown(request, run)
    # Not the run's keys: a background run can cover thousands of rows,
    # too many for a header, and only a quick view reads the ids.
    refresh: dict[str, list[str]] = {
        event: [] for event in _table_refresh_events(panel)
    }
    if action is not None and run.status == RunStatus.DONE and run.result is not None:
        model = action.noun_model
        result = BulkResult.from_json(run.result)
        return bulk_result_fragment(
            request,
            action,
            result,
            str(model._meta.verbose_name_plural),
            f"{count_noun(model, result.changed)} changed.",
            refresh,
        )
    # A run whose action has since been renamed or removed has no result
    # template to render, so its stored outcome is summarised instead.
    summary = (
        f"Stopped {stopped_after(run, action)}."
        if run.status == RunStatus.FAILED
        else run_summary(run)
    )
    response = render(
        request,
        "panel_framework/partials/bulk_run_stopped.html",
        {"label": run_label(run, action), "run": run, "summary": summary},
    )
    response["HX-Trigger"] = build_hx_trigger(refresh)
    return response


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
            if action.is_available(root.ctx)
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
                "status_badge": resolved.instance_view.get_status_badge(),
                "stats": resolved.instance_view.get_stats(),
                "header_refresh_events": " ".join(
                    resolved.instance_view.header_refresh_events
                ),
                "subtitle": resolved.instance_view.get_subtitle(),
                "ctx": root.ctx,
            },
            section.get_instance_label(resolved.instance),
        )
    if issubclass(section, ListViewConfig):
        # The same instances the list panel renders, checked once for both.
        list_actions = [
            action for action in root.available_actions if action.renders_in_footer
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
                "intro_template_name": section.intro_template_name,
                "intro": section.get_intro_context(request),
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
        echo = EchoWriter()
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
    a bare fragment. An instance page's header, targeted on its own, gets
    just the header. Before any of that, a table panel's export flag gets a
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
    if hx_target == "instance-header" and resolved.instance_view is not None:
        return render(
            request, "panel_framework/views/_instance_header.html", page_context
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


def build_menu_items(
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
            if not (section.is_visible(request) and section.is_available(request)):
                continue
            is_active = section.url_name == active_section
            # The section stays marked on its own instance pages, but only
            # its list is the page itself.
            if not is_active:
                aria_current = ""
            elif current_instance is None:
                aria_current = "page"
            else:
                aria_current = "true"
            items.append(
                {
                    "label": section.menu_label,
                    "url": reverse(
                        url_name,
                        kwargs={"path_string": section.url_name, **extra_url_kwargs},
                    ),
                    "icon": section.icon,
                    "count": section.get_menu_count(request),
                    "url_name": section.url_name,
                    # Part of the polled count element's id, so switching scope
                    # (for example organisation) yields a fresh element rather
                    # than a preserved one holding the old scope's count.
                    "scope_key": "-".join(extra_url_kwargs.values()),
                    "count_url": section.get_menu_count_url(request),
                    "count_poll_seconds": section.get_menu_count_poll_seconds(),
                    "active": is_active,
                    "aria_current": aria_current,
                }
            )
        if items:
            groups.append({"heading": group.heading, "items": items})
    return groups


def build_breadcrumbs(
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
        result: HttpResponse | _BulkConfirmation | _BulkResultPage | None = None
        try:
            resolved = _resolve_path(parts, sections, request, section_url)
            if resolved.quick_view:
                return _vary_on_htmx(
                    _handle_quick_view(
                        request,
                        resolved.section,
                        resolved.instance,
                        resolved.root.ctx.base_url,
                    )
                )
            if resolved.run_id is not None:
                result = _handle_run_status(request, resolved)
            elif resolved.action is not None:
                result = _handle_action(request, resolved.action, resolved.panel)
        except Http404:
            # htmx drops a bare 404, so an action the page offered would
            # silently do nothing once its object left the user's scope, or
            # when it 404s while rendering or submitting.
            if _is_htmx_action_request(request, parts):
                return _vary_on_htmx(
                    render(
                        request,
                        "panel_framework/partials/action_unavailable.html",
                        status=404,
                    )
                )
            raise
        if result is not None:
            if not isinstance(result, _BulkConfirmation | _BulkResultPage):
                return _vary_on_htmx(result)
            # A JavaScript-off bulk-action POST: render its message and
            # confirm form as this page's main content, with the page's own
            # chrome (menu, breadcrumbs) built the same way as any other
            # request below, rather than as a bare fragment.
            heading = result.action.label
            if isinstance(result, _BulkResultPage):
                main_template_name = "panel_framework/views/bulk_result.html"
                main = {
                    **_result_context(
                        result.action, result.result, result.noun, result.headline
                    ),
                    "page_url": result.page_url,
                }
            else:
                main_template_name = "panel_framework/views/bulk_confirmation.html"
                main = {
                    **result.context(),
                    "page_url": resolved.panel.ctx.page_url,
                }
                bulk_status = result.status
        else:
            main_template_name, main, heading = _main_for(request, resolved)

    page_context: dict[str, object] = {
        "menu_groups": build_menu_items(
            config,
            url_name,
            request,
            active_section=parts[0] if parts else "",
            current_instance=resolved.instance if resolved else None,
            extra_url_kwargs=extra_url_kwargs,
        ),
        "heading": heading,
        "breadcrumbs": build_breadcrumbs(
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
