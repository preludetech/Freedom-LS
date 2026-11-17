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
    StubChildRowsTablePanel,
    StubClassifyingBulkAction,
    StubCompactTablePanel,
    StubDataTablePanel,
    StubDetailDataTable,
    StubDetailTablePanel,
    StubDiscardBulkAction,
    StubExportBulkAction,
    StubForbiddenBulkAction,
    StubLeadingColumnChildRowsTablePanel,
    StubPlainDataTable,
    StubPurgeBulkAction,
    StubRecordedBulkAction,
    StubSequenceTablePanel,
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
    row_detail_template_name = StubDetailDataTable.row_detail_template_name


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


def test_a_card_lists_its_secondary_values_in_an_inline_definition_list(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubDataTablePanel)

    (card,) = document.cssselect("ul li.panel-data-table-card")
    assert [dt.text_content() for dt in card.cssselect("dl > div > dt")] == ["Kind"]
    assert [dd.text_content().strip() for dd in card.cssselect("dl > div > dd")] == [
        "Alpha"
    ]


def test_a_group_row_has_a_chevron_naming_its_child_rows(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    group = document.cssselect("tbody tr")[0]
    (button,) = group.cssselect("button")
    child_ids = [
        row.get("id")
        for row in document.cssselect("tbody tr")
        if row.get("data-parents") == group.get("id")
    ]
    assert button.get("aria-expanded") == "true"
    assert button.get("aria-controls") == " ".join(child_ids)
    assert button.get("aria-label") == "group"
    assert button.get("data-row") == group.get("id")


def test_a_leaf_row_has_no_chevron_button(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    leaf = document.cssselect("tbody tr")[-1]
    assert leaf.cssselect("button") == []


def test_a_child_rows_data_parents_lists_its_ancestors(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    rows = document.cssselect("tbody tr")
    group, inner, leaf_one = rows[0], rows[1], rows[2]
    assert group.get("data-parents") is None
    assert inner.get("data-parents") == group.get("id")
    assert leaf_one.get("data-parents") == f"{group.get('id')} {inner.get('id')}"
    assert leaf_one.get("x-show") == "shown"


def test_the_table_and_the_card_list_each_run_their_own_child_rows_state(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    assert len(document.cssselect('[x-data="childRows"]')) == 2
    assert len(document.cssselect('table[x-data="childRows"]')) == 1


def test_every_id_in_a_child_rows_region_is_unique(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    ids = [element.get("id") for element in document.cssselect("[id]")]
    assert len(set(ids)) == len(ids)


def test_every_card_id_ends_in_the_card_suffix(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    cards = document.cssselect("ul > li")
    assert [card.get("id").endswith("-card") for card in cards] == [True] * 7


def test_a_deeper_child_row_is_indented_further(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    cells = [row.cssselect("td")[0] for row in document.cssselect("tbody tr")]
    classes = [cell.get("class") or "" for cell in cells]
    assert "ps-" not in classes[0]
    assert "ps-8" in classes[1]
    assert "ps-12" in classes[2]


def test_a_table_without_child_rows_has_no_row_ids_or_child_rows_state(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubBTablePanel)

    assert document.cssselect("tr[id]") == []
    assert document.cssselect('[x-data="childRows"]') == []
    assert document.cssselect("tbody button") == []


def _note_row(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (row,) = [
        row for row in document.cssselect("tbody tr") if row.cssselect("td[colspan]")
    ]
    return row


def test_a_row_with_a_row_template_renders_it_once_in_the_table(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    (template,) = document.cssselect("tbody [data-test-row-template]")
    assert template.get("data-object") == "note"


def test_the_row_template_receives_the_row_dict(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    note = _note_row(document)
    (template,) = note.cssselect("[data-test-row-template]")
    assert template.get("data-row-id") == note.get("id")


def test_a_row_template_keeps_the_rows_id_and_data_parents(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    note = _note_row(document)
    group = document.cssselect("tbody tr")[0]
    assert note.get("data-parents") == group.get("id")
    assert note.get("x-show") == "shown"


def test_a_row_template_spans_every_column_from_the_primary_one(
    mock_site_context: Site,
) -> None:
    document = _render(StubLeadingColumnChildRowsTablePanel)

    note = _note_row(document)
    cells = note.cssselect("td")
    assert [cell.text_content().strip() for cell in cells[:-1]] == [""]
    assert cells[-1].get("colspan") == "2"


def test_a_leading_cell_of_a_row_template_carries_the_columns_cell_class(
    mock_site_context: Site,
) -> None:
    document = _render(StubLeadingColumnChildRowsTablePanel)

    leading = _note_row(document).cssselect("td")[0]
    assert leading.get("class") == "w-12"


def test_a_row_template_is_indented_by_its_depth(mock_site_context: Site) -> None:
    document = _render(StubChildRowsTablePanel)

    assert "ps-8" in _note_row(document).cssselect("td")[0].get("class")


def test_a_row_template_lines_up_with_the_titles_of_its_sibling_rows(
    mock_site_context: Site,
) -> None:
    """The template sat at the cell's start edge, left of the sibling rows' titles.

    A primary cell puts a chevron-wide slot before its value, so the template
    needs the same slot or it is indented less than its siblings.
    """
    document = _render(StubChildRowsTablePanel)

    (template,) = _note_row(document).cssselect("[data-test-row-template]")
    assert "ps-10" in template.getparent().get("class", "")


def test_a_row_template_row_takes_no_hover_and_has_no_chevron(
    mock_site_context: Site,
) -> None:
    document = _render(StubChildRowsTablePanel)

    note = _note_row(document)
    assert note.get("class") == "hover:bg-transparent"
    assert note.cssselect("button") == []


def test_a_table_without_row_templates_renders_every_cell(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-a", kind="a")

    document = _render(StubBTablePanel)

    assert document.cssselect("tbody [data-test-row-template]") == []
    assert document.cssselect("tbody td[colspan]") == []


def test_a_compact_table_root_carries_the_compact_class(
    mock_site_context: Site,
) -> None:
    document = _render(StubCompactTablePanel)

    assert "panel-data-table-compact" in document.get("class").split()


def test_a_default_table_root_does_not_carry_the_compact_class(
    mock_site_context: Site,
) -> None:
    document = _render(StubSequenceTablePanel)

    assert "panel-data-table-compact" not in document.get("class").split()
