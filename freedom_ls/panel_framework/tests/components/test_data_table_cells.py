"""Render tests for the framework's data table cell templates."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal

import lxml.html

from django.template.loader import render_to_string

from freedom_ls.panel_framework.tables import (
    BadgeColumn,
    Column,
    RelatedListColumn,
)
from freedom_ls.panel_framework.views import StatusBadge


@dataclass
class _Item:
    title: str
    pk: int


@dataclass
class _Row:
    items: list[_Item]
    when: object = None


def _render(template: str, row: object, column: Column) -> str:
    return render_to_string(
        f"cotton/data-table-cells/{template}", {"object": row, "column": column}
    )


def test_badge_cell_renders_the_columns_badge() -> None:
    column = BadgeColumn(
        header="Status",
        template_name="cotton/data-table-cells/badge.html",
        badge=lambda row: StatusBadge("success", "Active"),
    )

    html = _render("badge.html", _Row([]), column)

    assert "chip-success" in html
    assert "Active" in html


def test_badge_cell_renders_nothing_for_a_row_without_a_badge() -> None:
    column = BadgeColumn(
        header="Status",
        template_name="cotton/data-table-cells/badge.html",
        badge=lambda row: None,
    )

    assert _render("badge.html", _Row([]), column).strip() == ""


def test_date_cell_renders_the_value_as_a_date() -> None:
    column = Column(header="When", template_name="x", attr="when")

    html = _render("date.html", _Row([], datetime.date(2026, 11, 3)), column)

    assert "<time" in html
    assert "2026-11-03" in html


def test_date_cell_without_a_value_shows_a_dash() -> None:
    column = Column(header="When", template_name="x", attr="when")

    assert _render("date.html", _Row([]), column).strip() == "-"


def test_date_cell_without_a_value_shows_its_empty_text() -> None:
    column = Column(header="When", template_name="x", attr="when", empty_text="Never")

    assert _render("date.html", _Row([]), column).strip() == "Never"


def _related_column(
    layout: Literal["list", "inline"] = "list", url_name: str = ""
) -> RelatedListColumn:
    return RelatedListColumn(
        header="Items",
        template_name="cotton/data-table-cells/related_list.html",
        relation_set="items",
        item_text_attr="title",
        layout=layout,
        url_name=url_name,
        url_path_template="stubs/{pk}" if url_name else "",
    )


def test_related_list_layout_list_renders_one_list_item_each() -> None:
    row = _Row([_Item("Alpha", 1), _Item("Beta", 2)])

    root = lxml.html.fromstring(_render("related_list.html", row, _related_column()))

    assert [li.text_content().strip() for li in root.findall(".//li")] == [
        "Alpha",
        "Beta",
    ]


def test_related_list_layout_inline_separates_items_with_commas() -> None:
    row = _Row([_Item("Alpha", 1), _Item("Beta", 2)])

    html = _render("related_list.html", row, _related_column(layout="inline"))

    assert "<li" not in html
    assert " ".join(html.split()) == "Alpha, Beta"


def test_related_list_without_items_reads_an_em_dash() -> None:
    html = _render("related_list.html", _Row([]), _related_column())

    assert "—" in html
    assert "<li" not in html


def test_related_list_links_each_item_when_the_column_has_a_url() -> None:
    row = _Row([_Item("Alpha", 1), _Item("Beta", 2)])
    column = _related_column(url_name="panel_framework_test:framework")

    root = lxml.html.fromstring(_render("related_list.html", row, column))

    assert [a.get("href") for a in root.findall(".//a")] == [
        "/test-panel/framework/stubs/1",
        "/test-panel/framework/stubs/2",
    ]
    assert root.xpath('.//a[@aria-controls="quick-view"]') == []
