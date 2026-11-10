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
    StubArchiveBulkAction,
    StubBTablePanel,
    StubBulkAction,
    StubCardDataTable,
    StubClassifyingBulkAction,
    StubDetailDataTable,
    StubDetailTablePanel,
    StubDiscardBulkAction,
    StubExportBulkAction,
    StubForbiddenBulkAction,
    StubPlainDataTable,
    StubPurgeBulkAction,
    StubRecordedBulkAction,
)
from ..test_tables import _bind_table_panel

pytestmark = pytest.mark.django_db


class _BulkDetailTablePanel(StubDetailTablePanel):
    def get_bulk_actions(self) -> list[BulkAction]:
        return [StubBulkAction()]


def _bulk_panel(actions: list[BulkAction]) -> type[DataTablePanel]:
    class _Panel(StubDetailTablePanel):
        def get_bulk_actions(self) -> list[BulkAction]:
            return actions

    return _Panel


_SEVEN_ACTIONS: list[BulkAction] = [
    StubBulkAction(),
    StubDiscardBulkAction(),
    StubArchiveBulkAction(),
    StubExportBulkAction(),
    StubRecordedBulkAction(),
    StubClassifyingBulkAction(),
    StubPurgeBulkAction(),
]
_FOUR_ACTIONS: list[BulkAction] = [
    StubBulkAction(),
    StubArchiveBulkAction(),
    StubExportBulkAction(),
    StubRecordedBulkAction(),
]


def _bar_labels(elements: list[lxml.html.HtmlElement]) -> list[str]:
    return [element.text_content().strip() for element in elements]


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


def test_the_bar_promotes_the_first_four_non_destructive_actions_as_buttons(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel(_SEVEN_ACTIONS))

    buttons = document.cssselect("fieldset > button[type='submit']")
    assert _bar_labels(buttons) == ["Mark processed", "Archive", "Export", "Deactivate"]


def test_the_more_menu_lists_the_remaining_then_the_destructive_actions(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel(_SEVEN_ACTIONS))

    (menu,) = document.cssselect("fieldset > span [role='menu']")
    assert _bar_labels(menu.cssselect("[role='menuitem']")) == [
        "Mark processed (classified)",
        "Discard",
        "Purge",
    ]


def test_the_more_menu_rule_sits_between_the_two_groups(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel(_SEVEN_ACTIONS))

    (menu,) = document.cssselect("fieldset > span [role='menu']")
    roles = [child.get("role") for child in menu]
    assert roles == ["menuitem", "separator", "menuitem", "menuitem"]


def test_only_destructive_menu_items_read_in_error_text(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel(_SEVEN_ACTIONS))

    items = document.cssselect("fieldset > span [role='menuitem']")
    red = [i.text_content().strip() for i in items if "text-error" in i.get("class")]
    assert red == ["Discard", "Purge"]


def test_four_non_destructive_actions_render_no_menu(mock_site_context: Site) -> None:
    document = _render(_bulk_panel(_FOUR_ACTIONS))

    assert document.cssselect("fieldset [role='menu']") == []


def test_a_menu_of_destructive_actions_alone_has_no_rule(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel([*_FOUR_ACTIONS, StubDiscardBulkAction()]))

    assert (
        len(document.cssselect("fieldset > span [role='menu'] [role='menuitem']")) == 1
    )
    assert document.cssselect("fieldset [role='separator']") == []


def test_an_action_the_user_may_not_run_is_in_neither_the_bar_nor_the_menu(
    mock_site_context: Site,
) -> None:
    document = _render(_bulk_panel([*_FOUR_ACTIONS, StubForbiddenBulkAction()]))

    assert (
        "Forbidden bulk action" not in document.cssselect("fieldset")[0].text_content()
    )


def test_no_bar_button_takes_a_filled_variant(mock_site_context: Site) -> None:
    document = _render(_bulk_panel(_SEVEN_ACTIONS))

    for button in document.cssselect("fieldset .btn"):
        classes = button.get("class").split()
        assert not {"btn-secondary", "btn-error", "btn-primary"} & set(classes)


def test_a_bulk_table_without_controls_keeps_the_toolbars_row_height(
    mock_site_context: Site,
) -> None:
    """The bar takes the toolbar's row from lg, so a toolbar with nothing in
    it still holds that row's height, or the table would move under it."""
    document = _render(_bulk_panel([StubBulkAction()]))

    (toolbar,) = document.xpath('//*[@*[name()="x-bind:class"]="toolbarClass"]')
    assert "lg:min-h-16.75" in toolbar.get("class").split()


def _positions(document: lxml.html.HtmlElement) -> dict[str, int]:
    order = list(document.iter())
    return {
        name: order.index(found[0])
        for name, selector in {
            "table": "table",
            "footer": "[data-entry-count]",
        }.items()
        if (found := document.cssselect(selector))
    }


def test_a_bulk_table_renders_its_entry_count_after_the_table(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(_bulk_panel([StubBulkAction()]))

    (count,) = document.cssselect("[data-entry-count]")
    assert count.text_content().strip()
    assert _positions(document)["footer"] > _positions(document)["table"]


def test_a_table_without_bulk_actions_renders_its_entry_count(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubBTablePanel)

    assert len(document.cssselect("[data-entry-count]")) == 1


def test_the_bar_sticks_above_the_table_at_every_width(
    mock_site_context: Site,
) -> None:
    """One position at every width: sticky in the toolbar's place, never
    fixed to the bottom of the viewport."""
    make_stub(name="row-a", kind="a")

    document = _render(_bulk_panel([StubBulkAction()]))

    (bar,) = document.cssselect("[data-total-count]")
    classes = bar.get("class").split()
    assert "sticky" in classes
    assert not {"fixed", "bottom-0", "lg:static"} & set(classes)
    assert document.cssselect("[data-selection-bar-space]") == []
