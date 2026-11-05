"""Render tests for the data table region's row detail: the toggle column,
the hidden detail rows, the spanning cells and the card toggle."""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string

from freedom_ls.panel_framework.bulk_actions import BulkAction
from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import ExportColumn

from ..helpers import make_stub
from ..stub_panels import (
    StubBTablePanel,
    StubBulkAction,
    StubCardDataTable,
    StubDetailDataTable,
    StubDetailTablePanel,
    StubPlainDataTable,
)
from ..test_tables import _bind_table_panel

pytestmark = pytest.mark.django_db


class _BulkDetailTablePanel(StubDetailTablePanel):
    def get_bulk_actions(self) -> list[BulkAction]:
        return [StubBulkAction()]


class _CardDetailDataTable(StubCardDataTable):
    row_detail_template = StubDetailDataTable.row_detail_template


class _CardDetailTablePanel(DataTablePanel):
    title = "Card detail"
    data_table = _CardDetailDataTable
    table_key = "carddetail"


def _render(panel_class: type[DataTablePanel]) -> lxml.html.HtmlElement:
    panel = _bind_table_panel(panel_class)
    html = render_to_string(
        panel.region_template_name, panel.get_context_data(), request=panel.request
    )
    return lxml.html.fromstring(html)


def test_the_header_opens_with_a_details_column(mock_site_context: Site) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    headers = document.cssselect("thead th")
    assert headers[0].text_content().strip() == "Details"


def test_a_row_with_a_detail_has_a_toggle_naming_its_hidden_detail_row(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    (data_row,) = document.cssselect("tbody tr:not([data-row-detail])")
    button = data_row.cssselect("td:first-child button")[0]
    detail_row = data_row.getnext()
    assert button.get("aria-expanded") == "false"
    assert detail_row.get("data-row-detail") is not None
    assert detail_row.get("hidden") is not None
    assert button.get("aria-controls") == detail_row.get("id")
    assert detail_row.cssselect("[data-test-detail]")[0].text_content() == (
        "Detail for row-a"
    )


def test_detail_rows_have_unique_ids(mock_site_context: Site) -> None:
    make_stub(name="row-a", kind="a")
    make_stub(name="row-b", kind="a")

    document = _render(StubDetailTablePanel)

    ids = [row.get("id") for row in document.cssselect("tr[data-row-detail]")]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_a_detail_row_leaves_the_toggle_cell_empty_and_spans_the_rest(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    toggle_cell, content_cell = document.cssselect("tr[data-row-detail] td")
    assert toggle_cell.text_content().strip() == ""
    assert content_cell.get("colspan") == str(columns - 1)
    assert content_cell.cssselect("[data-test-detail]")


def test_a_detail_row_spans_the_selection_column_too(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(_BulkDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    select_cell, toggle_cell, content_cell = document.cssselect(
        "tr[data-row-detail] td"
    )
    assert select_cell.text_content().strip() == ""
    assert toggle_cell.text_content().strip() == ""
    assert content_cell.get("colspan") == str(columns - 2)
    assert columns == 3


def test_the_empty_state_spans_the_columns_plus_the_toggle(
    mock_site_context: Site,
) -> None:
    document = _render(StubDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    (cell,) = document.cssselect("tbody td[colspan]")
    assert cell.get("colspan") == str(columns)


def test_the_empty_state_spans_the_selection_column_too(
    mock_site_context: Site,
) -> None:
    document = _render(_BulkDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    (cell,) = document.cssselect("tbody td[colspan]")
    assert cell.get("colspan") == str(columns)


def test_a_row_the_predicate_rejects_has_an_empty_toggle_cell_and_no_detail_row(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-b", kind="b")

    document = _render(StubDetailTablePanel)

    (data_row,) = document.cssselect("tbody tr")
    assert data_row.cssselect("td:first-child")[0].text_content().strip() == ""
    assert data_row.cssselect("button") == []
    assert document.cssselect("tr[data-row-detail]") == []


def _card_toggles(document: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    return list(document.cssselect("ul[x-data='rowDetail'] li button[aria-controls]"))


def test_a_card_with_a_detail_has_a_toggle_naming_its_hidden_detail(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")
    make_stub(name="row-b", kind="b")

    document = _render(StubDetailTablePanel)

    (button,) = _card_toggles(document)
    (detail,) = document.cssselect("ul li div[data-row-detail]")
    assert button.get("aria-expanded") == "false"
    assert button.get("aria-controls") == detail.get("id")
    assert detail.get("hidden") is not None
    assert detail.cssselect("[data-test-detail]")[0].text_content() == (
        "Detail for row-a"
    )
    assert document.cssselect("ul details") == []


def test_card_detail_ids_differ_from_the_table_detail_ids(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    ids = [element.get("id") for element in document.cssselect("[data-row-detail]")]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_a_custom_card_template_still_gets_the_toggle(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(_CardDetailTablePanel)

    assert document.cssselect("ul .stub-custom-card")
    assert len(_card_toggles(document)) == 1


def test_a_table_without_a_row_detail_renders_no_toggle_or_detail(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubBTablePanel)

    assert "Details" not in [
        th.text_content().strip() for th in document.cssselect("th")
    ]
    assert document.cssselect("tbody button") == []
    assert document.cssselect("tr[data-row-detail]") == []
    assert document.cssselect("[data-row-detail]") == []
    assert document.cssselect("table[x-data]") == []
    assert document.cssselect("ul[x-data]") == []


class _PlainExportDataTable(StubPlainDataTable):
    """No filters and no sortable columns, with export columns."""

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        return [ExportColumn("Name", "name")]


class _PlainExportTablePanel(DataTablePanel):
    title = "Plain export"
    data_table = _PlainExportDataTable
    table_key = "plainexport"


class _PlainNoExportTablePanel(DataTablePanel):
    title = "Plain"
    data_table = StubPlainDataTable
    table_key = "plain"


def test_a_table_with_only_an_export_has_an_export_link_in_the_phone_toolbar(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a")

    document = _render(_PlainExportTablePanel)

    (link,) = [
        a
        for a in document.cssselect(".md\\:hidden a")
        if a.text_content().strip() == "Export CSV"
    ]
    assert "plainexport-export=csv" in link.get("href")
    assert not document.cssselect("[x-data=sidePanel]")


def test_a_table_without_export_columns_renders_no_export_link(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a")

    document = _render(_PlainNoExportTablePanel)

    assert "Export CSV" not in document.text_content()
