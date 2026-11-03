"""Render tests for the data table region's row detail: the toggle column,
the hidden detail rows, the spanning cells and the phone disclosure."""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string

from freedom_ls.panel_framework.bulk_actions import BulkAction
from freedom_ls.panel_framework.panels import DataTablePanel

from ..helpers import make_stub
from ..stub_panels import (
    StubBTablePanel,
    StubBulkAction,
    StubCardDataTable,
    StubDetailDataTable,
    StubDetailTablePanel,
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


def test_the_header_ends_with_a_more_column(mock_site_context: Site) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    headers = document.cssselect("thead th")
    assert headers[-1].text_content().strip() == "More"


def test_a_row_with_a_detail_has_a_toggle_naming_its_hidden_detail_row(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    (data_row,) = document.cssselect("tbody tr:not([data-row-detail])")
    button = data_row.cssselect("td:last-child button")[0]
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


def test_a_detail_row_spans_the_columns_plus_the_toggle(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    (cell,) = document.cssselect("tr[data-row-detail] td")
    assert cell.get("colspan") == str(columns)


def test_a_detail_row_spans_the_selection_column_too(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(_BulkDetailTablePanel)

    columns = len(document.cssselect("thead th"))
    (cell,) = document.cssselect("tr[data-row-detail] td")
    assert cell.get("colspan") == str(columns)
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
    assert data_row.cssselect("td:last-child")[0].text_content().strip() == ""
    assert data_row.cssselect("button") == []
    assert document.cssselect("tr[data-row-detail]") == []


def test_the_card_list_gives_a_row_with_a_detail_a_more_disclosure(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")
    make_stub(name="row-b", kind="b")

    document = _render(StubDetailTablePanel)

    summaries = document.cssselect("ul details > summary")
    assert [summary.text_content().strip() for summary in summaries] == ["More"]
    assert document.cssselect("ul details [data-test-detail]")[0].text_content() == (
        "Detail for row-a"
    )


def test_a_custom_card_template_still_gets_the_more_disclosure(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(_CardDetailTablePanel)

    assert document.cssselect("ul .stub-custom-card")
    assert [
        summary.text_content().strip()
        for summary in document.cssselect("ul details > summary")
    ] == ["More"]


def test_a_table_without_a_row_detail_renders_no_toggle_or_detail(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubBTablePanel)

    assert "More" not in [th.text_content().strip() for th in document.cssselect("th")]
    assert document.cssselect("tbody button") == []
    assert document.cssselect("tr[data-row-detail]") == []
    assert document.cssselect("ul details") == []
    assert document.cssselect("table[x-data]") == []
