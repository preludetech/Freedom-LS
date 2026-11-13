"""Render tests for the <c-data-table-card /> cotton component."""

from __future__ import annotations

from dataclasses import dataclass

import lxml.html

from freedom_ls.panel_framework.tables import Column

from ..cotton_helpers import render_cotton

_TEXT_CELL = "cotton/data-table-cells/text.html"


@dataclass
class _Item:
    pk: int
    name: str
    kind: str


@dataclass
class _Row:
    object: _Item
    label: str
    has_row_detail: bool = False


def _row(has_row_detail: bool = False) -> _Row:
    item = _Item(pk=7, name="Alpha", kind="Letter")
    return _Row(object=item, label="Alpha", has_row_detail=has_row_detail)


def _name_column() -> Column:
    return Column(header="Name", template_name=_TEXT_CELL, attr="name")


def _kind_column() -> Column:
    return Column(header="Kind", template_name=_TEXT_CELL, attr="kind")


def _card(source: str, **context: object) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(render_cotton(source, **context))


def test_the_primary_value_leads_and_secondary_values_are_labelled() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' "
        ":secondary_columns='secondary' />",
        row=_row(),
        primary=_name_column(),
        secondary=[_kind_column()],
    )

    assert card.tag == "li"
    assert card.cssselect("[data-card-primary-line]")[0].text_content().strip() == (
        "Alpha"
    )
    assert [dt.text_content() for dt in card.cssselect("dl dt")] == ["Kind"]
    assert [dd.text_content().strip() for dd in card.cssselect("dl dd")] == ["Letter"]


def test_a_card_without_secondary_columns_has_no_definition_list() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' />",
        row=_row(),
        primary=_name_column(),
    )

    assert card.cssselect("dl") == []


def test_a_selectable_card_has_a_labelled_checkbox_for_its_row() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' :selectable='True' />",
        row=_row(),
        primary=_name_column(),
    )

    (box,) = card.cssselect("input[type=checkbox][name=keys]")
    assert box.get("value") == "7"
    assert box.get("aria-label") == "Select Alpha"


def test_an_unselectable_card_has_no_checkbox() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' />",
        row=_row(),
        primary=_name_column(),
    )

    assert card.cssselect("input[type=checkbox]") == []


def test_a_detail_toggle_names_the_hidden_detail_it_controls() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' "
        "row_detail_template_name='panel_framework/test_row_detail.html' "
        "detail_id='card-detail-1' />",
        row=_row(has_row_detail=True),
        primary=_name_column(),
    )

    (toggle,) = card.cssselect("button[aria-controls]")
    assert toggle.get("aria-controls") == "card-detail-1"
    assert toggle.get("aria-expanded") == "false"
    assert toggle.get("aria-label") == "More about Alpha"
    (detail,) = card.cssselect("[data-row-detail]")
    assert detail.get("id") == "card-detail-1"
    assert detail.get("hidden") is not None


def test_a_row_without_a_detail_has_an_empty_toggle_slot_and_no_detail() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' "
        "row_detail_template_name='panel_framework/test_row_detail.html' "
        "detail_id='card-detail-1' />",
        row=_row(has_row_detail=False),
        primary=_name_column(),
    )

    assert card.cssselect("button") == []
    assert card.cssselect("[data-row-detail]") == []


def test_a_table_without_a_row_detail_renders_no_toggle() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' />",
        row=_row(has_row_detail=True),
        primary=_name_column(),
    )

    assert card.cssselect("button") == []
    assert card.cssselect("[data-row-detail]") == []


def test_a_card_template_replaces_the_primary_and_secondary_rendering() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' "
        ":secondary_columns='secondary' card_template_name='panel_framework/test_stub_card.html' />",
        row=_row(),
        primary=_name_column(),
        secondary=[_kind_column()],
    )

    assert card.cssselect("[data-card-primary-line]") == []
    assert card.cssselect("dl") == []
    assert card.cssselect(".stub-custom-card")[0].text_content() == (
        "Custom card for Alpha"
    )


def test_a_linked_primary_column_ends_its_line_with_a_decorative_open_icon() -> None:
    column = Column(
        header="Name",
        template_name=_TEXT_CELL,
        attr="name",
        url_name="panel_framework_test:framework",
        url_path_template="stubs/{pk}",
    )
    assert column.is_link

    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' />",
        row=_row(),
        primary=column,
    )

    (icon,) = card.cssselect("[data-card-primary-line] > span[aria-hidden=true]")
    assert icon.cssselect("svg[data-icon=open_page]")


def test_an_unlinked_primary_column_has_no_open_icon() -> None:
    card = _card(
        "<c-data-table-card :row='row' :primary_column='primary' />",
        row=_row(),
        primary=_name_column(),
    )

    assert card.cssselect("svg[data-icon=open_page]") == []
