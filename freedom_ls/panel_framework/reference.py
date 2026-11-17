"""The component reference page: every panel_framework component, every state.

Static example data only, so the page carries no model access and no query
cost of its own. The table, lazy-panel and reason-dialog examples are drawn by
the framework's own classes and templates from that static data. `component_reference` is the one view; `config/urls.py`
includes it only under `if settings.DEBUG:`, and the isolated test URLconf
(`tests/urls.py`) exposes the same view unconditionally so it can be tested
without a real dev server.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Page
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.safestring import SafeString

from freedom_ls.panel_framework.forms import ReasonForm
from freedom_ls.panel_framework.panels import (
    BulkActionEntry,
    entry_count_text,
    table_region_context,
)
from freedom_ls.panel_framework.tables import Column, DataTable

__all__ = [
    "component_reference",
]

# Two rows for `#attention-list-default`, so the divider between rows is
# visible. Their `href`/`action_href` are fragments on the page itself
# (`#attention-row-target` / `#attention-row-action`), which lets the
# Playwright test assert on the URL after a tap without leaving the page.
EXAMPLE_CONTEXT: dict[str, object] = {
    "attention_rows": [
        {
            "subject": "Thandi Mokoena",
            "user_id": 42,
            "reason": "4 days idle",
            "badge_label": "Stalled",
            "badge_tone": "warning",
            "href": "#attention-row-target",
            "action_label": "Message",
            "action_href": "#attention-row-action",
        },
        {
            "subject": "Sipho Nkosi",
            "user_id": 7,
            "reason": "Last active 6 days ago",
            "badge_label": "",
            "badge_tone": "muted",
            "href": "#attention-row-target",
            "action_label": "Message",
            "action_href": "#attention-row-action",
        },
    ],
}


@dataclass(frozen=True)
class ExampleItem:
    """One row of an example table: a name, a status, a longer description
    for the row detail and the rows nested under it."""

    name: str
    status: str
    description: str = ""
    kind: str = "item"
    children: tuple[ExampleItem, ...] = ()


EXAMPLE_ITEMS: list[ExampleItem] = [
    ExampleItem(
        name="Quarterly report",
        status="Published",
        description="Totals for the quarter, with a breakdown by team.",
    ),
    ExampleItem(
        name="Onboarding checklist",
        status="Draft",
        description="Steps a new member completes in their first week.",
    ),
    ExampleItem(
        name="Annual review",
        status="Archived",
        description="The year in figures, kept for reference.",
    ),
]

EXAMPLE_NESTED_ITEMS: list[ExampleItem] = [
    ExampleItem(
        name="Handbook",
        status="Published",
        children=(
            ExampleItem(
                name="Getting started",
                status="Published",
                children=(
                    ExampleItem(name="Welcome", status="Published"),
                    ExampleItem(name="First steps", status="Draft"),
                ),
            ),
            ExampleItem(name="Glossary", status="Published"),
            ExampleItem(name="Updated each quarter", status="", kind="note"),
        ),
    ),
    ExampleItem(name="Appendix", status="Draft"),
]


class _ExampleTable(DataTable):
    """The shared shape of the example tables: a sequence of `ExampleItem`
    rows, so there is no model behind them."""

    noun = "items"
    noun_singular = "item"

    @staticmethod
    def get_queryset(request: HttpRequest) -> Sequence[object]:
        return EXAMPLE_ITEMS

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Name",
                template_name="cotton/data-table-cells/text.html",
                attr="name",
                card="primary",
            ),
            Column(
                header="Status",
                template_name="cotton/data-table-cells/text.html",
                attr="status",
            ),
        ]

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(ExampleItem, row).name


class RowDetailExampleTable(_ExampleTable):
    row_detail_template_name = "panel_framework/reference/_row_detail.html"


class ChildRowsExampleTable(_ExampleTable):
    has_child_rows = True

    @staticmethod
    def get_queryset(request: HttpRequest) -> Sequence[object]:
        return EXAMPLE_NESTED_ITEMS

    @staticmethod
    def get_child_rows(row: object) -> Sequence[object]:
        return cast(ExampleItem, row).children

    @staticmethod
    def get_row_template_name(row: object) -> str | None:
        if cast(ExampleItem, row).kind == "note":
            return "panel_framework/reference/_note_row.html"
        return None


class CompactExampleTable(_ExampleTable):
    compact = True


def _render_table(
    request: HttpRequest, table: type[DataTable], key: str, region_id: str
) -> SafeString:
    """The table's region as a host gets it: the framework's own context and
    template, over the example rows."""
    query = table.parse_query(request, key)
    context = table.get_context(
        request,
        query,
        table.get_queryset(request),
        base_url=request.path,
        page_url=request.path,
        region_id=region_id,
    )
    no_bulk_actions: list[BulkActionEntry] = []
    context.update(
        table_region_context(
            table,
            noun=table.noun,
            entry_count=entry_count_text(
                cast(Page, context["page_obj"]), table.noun_singular, table.noun
            ),
            bulk_entries=no_bulk_actions,
        )
    )
    return render_to_string(
        "panel_framework/panels/data_table_region.html",
        {**context, "request": request},
    )


def _render_reason_dialog(
    request: HttpRequest, form: ReasonForm, prefix: str
) -> SafeString:
    """The confirm dialog a `ReasonMixin` action shows, around `form`. Its
    own `auto_id` keeps its element ids apart from the other dialogs' on the
    page."""
    form.auto_id = f"{prefix}_%s"
    context: dict[str, object] = {
        "title": "Archive this report",
        "title_id": f"{prefix}_title",
        "action_url": request.path,
        "page_url": request.path,
        "hidden_fields": {},
        "confirm_label": "Archive",
        "confirm_variant": "primary",
        "loading_text": "Archiving",
        "reason_form": form,
        "csrf_token": get_token(request),
    }
    return render_to_string("panel_framework/reference/_reason_dialog.html", context)


def example_context(request: HttpRequest) -> dict[str, object]:
    """Every example's context. The table, lazy-panel and dialog examples
    are rendered by the framework's own classes, so the page shows what a
    host gets rather than a copy that can drift."""
    choices = [("duplicate", "Duplicate"), ("out_of_date", "Out of date")]
    reason_dialogs = {
        "required": _render_reason_dialog(
            request, ReasonForm(required=True), "reason_required"
        ),
        "choices": _render_reason_dialog(
            request, ReasonForm(choices=choices), "reason_choices"
        ),
        "choices_required": _render_reason_dialog(
            request,
            ReasonForm(required=True, choices=choices),
            "reason_choices_required",
        ),
    }
    lazy_panel = render_to_string(
        "panel_framework/reference/_lazy_panel.html",
        {
            "region_id": "lazy-panel-as-of-region",
            "is_loaded": True,
            "show_as_of": True,
            "as_of": datetime.datetime(2026, 1, 15, 9, 30, tzinfo=datetime.UTC),
        },
    )
    data_tables = {
        "row_detail": _render_table(
            request, RowDetailExampleTable, "detail", "data-table-row-detail-region"
        ),
        "child_rows": _render_table(
            request, ChildRowsExampleTable, "childrows", "data-table-child-rows-region"
        ),
        "compact": _render_table(
            request, CompactExampleTable, "compact", "data-table-compact-region"
        ),
    }
    return {
        **EXAMPLE_CONTEXT,
        "reason_dialogs": reason_dialogs,
        "lazy_panel": lazy_panel,
        "data_tables": data_tables,
    }


@staff_member_required
def component_reference(
    request: HttpRequest,
    template_name: str = "panel_framework/reference/component_reference.html",
) -> HttpResponse:
    return render(request, template_name, example_context(request))
