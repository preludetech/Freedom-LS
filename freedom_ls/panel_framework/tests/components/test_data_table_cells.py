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


@dataclass
class _Named:
    name: str = ""
    fallback: str = ""
    pk: int = 5
    count: object = None
    when: object = None


def _link_column(
    htmx_nav: bool = False,
    quick_view: bool = False,
    fallback_text_attr: str = "",
) -> Column:
    return Column(
        header="Name",
        template_name="cotton/data-table-cells/link.html",
        text_attr="name",
        fallback_text_attr=fallback_text_attr,
        url_name="panel_framework_test:framework",
        url_path_template="stubs/{pk}",
        htmx_nav=htmx_nav,
        quick_view=quick_view,
    )


def test_datetime_cell_renders_the_value_as_a_time_element() -> None:
    column = Column(header="When", template_name="x", attr="when")
    row = _Named(when=datetime.datetime(2026, 11, 3, 14, 30, tzinfo=datetime.UTC))

    root = lxml.html.fromstring(_render("datetime.html", row, column))

    assert root.tag == "time"
    assert root.get("datetime").startswith("2026-11-03T14:30")


def test_datetime_cell_without_a_value_shows_a_dash() -> None:
    column = Column(header="When", template_name="x", attr="when")

    assert _render("datetime.html", _Named(), column).strip() == "-"


def test_text_cell_renders_the_attribute() -> None:
    column = Column(header="Name", template_name="x", attr="name")

    assert _render("text.html", _Named(name="Alpha"), column).strip() == "Alpha"


def test_text_cell_renders_a_zero() -> None:
    column = Column(header="Count", template_name="x", attr="count")

    assert _render("text.html", _Named(count=0), column).strip() == "0"


def test_text_cell_without_a_value_shows_a_dash() -> None:
    column = Column(header="Name", template_name="x", attr="name")

    assert _render("text.html", _Named(name=""), column).strip() == "-"


def test_text_cell_escapes_the_value() -> None:
    column = Column(header="Name", template_name="x", attr="name")

    html = _render("text.html", _Named(name="<b>x</b>"), column)

    assert "<b>" not in html
    assert "&lt;b&gt;" in html


def test_link_cell_links_the_text_to_the_resolved_page() -> None:
    root = lxml.html.fromstring(
        _render("link.html", _Named(name="Alpha"), _link_column())
    )

    assert root.tag == "a"
    assert root.get("href") == "/test-panel/framework/stubs/5"
    assert root.text_content() == "Alpha"
    assert root.get("hx-get") is None


def test_link_cell_with_htmx_nav_swaps_the_main_content() -> None:
    root = lxml.html.fromstring(
        _render("link.html", _Named(name="Alpha"), _link_column(htmx_nav=True))
    )

    assert root.get("hx-get") == "/test-panel/framework/stubs/5"
    assert root.get("hx-target") == "#main-content"
    assert root.get("hx-push-url") == "true"


def test_link_cell_falls_back_to_the_fallback_text_when_the_name_is_blank() -> None:
    column = _link_column(fallback_text_attr="fallback")

    root = lxml.html.fromstring(
        _render("link.html", _Named(name="  ", fallback="Unnamed"), column)
    )

    assert root.text_content() == "Unnamed"


def test_link_cell_with_no_text_is_a_dash_and_not_a_link() -> None:
    html = _render("link.html", _Named(name=""), _link_column())

    assert html.strip() == "-"
    assert "<a" not in html


def test_link_cell_in_a_secondary_line_is_not_bold() -> None:
    row = _Named(name="Alpha")
    column = _link_column()

    primary = lxml.html.fromstring(_render("link.html", row, column))
    secondary = lxml.html.fromstring(
        render_to_string(
            "cotton/data-table-cells/link.html",
            {"object": row, "column": column, "in_secondary_line": True},
        )
    )

    assert "font-bold" in primary.get("class")
    assert "font-bold" not in secondary.get("class")


def test_link_cell_with_quick_view_adds_a_trigger_labelled_by_the_name() -> None:
    root = lxml.html.fromstring(
        _render("link.html", _Named(name="Alpha"), _link_column(quick_view=True))
    )

    (trigger,) = root.xpath('.//*[@aria-controls="quick-view"]')
    assert trigger.get("aria-label") == "Quick view: Alpha"
    assert next(a.get("href") for a in root.findall(".//a")) == (
        "/test-panel/framework/stubs/5"
    )


def test_link_cell_without_quick_view_has_no_trigger() -> None:
    html = _render("link.html", _Named(name="Alpha"), _link_column())

    assert "quick-view" not in html
