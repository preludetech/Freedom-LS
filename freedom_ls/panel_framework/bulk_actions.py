"""Row selection and bulk actions: the payload a bulk-action POST names, and
the action that runs once over the rows it resolves to."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.panel_framework.context import PanelContext

if TYPE_CHECKING:
    from freedom_ls.panel_framework.panels import DataTablePanel


class BulkAction:
    """One action a table panel offers over a set of selected rows.

    Its URL is the table panel's own base_url plus "/__actions/<action_name>",
    the same shape a PanelAction's URL takes. Unlike a PanelAction, it never
    binds to a single instance: has_permission and execute both work over the
    request alone and the resolved queryset.
    """

    label: str = ""
    action_name: str = ""
    max_rows: int = 500
    confirm_template_name: str = "panel_framework/partials/bulk_confirmation.html"

    def has_permission(self, request: HttpRequest) -> bool:
        return True

    def execute(self, request: HttpRequest, queryset: QuerySet) -> None:
        raise NotImplementedError

    def get_action_url(self, ctx: PanelContext) -> str:
        return f"{ctx.base_url}/__actions/{self.action_name}"


@dataclass(frozen=True)
class Selection:
    """The rows a bulk-action request names.

    Only "keys" mode is resolved today: "all_matching" (every row the
    table's current search, filters and sort would return, across every
    page) has no resolver yet, so a request naming it is answered 422
    rather than guessed at.
    """

    mode: Literal["keys", "all_matching"]
    keys: list[str] = field(default_factory=list)
    query_string: str = ""
    excluded: list[str] = field(default_factory=list)


def parse_selection(request: HttpRequest) -> Selection:
    """This bulk-action POST's own selection payload.

    An unrecognised or missing mode parses as "keys" with whatever keys (if
    any) came with it, so a malformed request falls through to the ordinary
    "zero selected" answer rather than a different error path.
    """
    mode: Literal["keys", "all_matching"] = (
        "all_matching" if request.POST.get("mode") == "all_matching" else "keys"
    )
    return Selection(
        mode=mode,
        keys=request.POST.getlist("keys"),
        query_string=request.POST.get("query_string", ""),
        excluded=request.POST.getlist("excluded"),
    )


def resolve_selection(
    panel: DataTablePanel, request: HttpRequest, selection: Selection
) -> QuerySet:
    """The rows `selection` names, scoped to `panel`.

    Keys mode only; the view has already answered 422 for any other mode. A
    key the model's primary-key field can't parse, or one outside the
    panel's own scope, drops out silently rather than raising: it reaches
    here straight from a form submission that may be stale or tampered with,
    and handlers must never see the raw keys or payload themselves.
    """
    scoped = panel.get_queryset(request)
    pk_field = scoped.model._meta.pk
    parsed: list[object] = []
    for key in selection.keys:
        try:
            parsed.append(pk_field.to_python(key))
        except ValidationError:
            continue
    return scoped.filter(pk__in=parsed)
