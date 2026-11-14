"""Tests for the <c-panel-table /> cotton component and its card parts."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton

PLAIN = """
<c-panel-table caption="Generated reports" data-report-rows="true">
    <c-slot name="head"><tr><th scope="col">Generated</th><th scope="col">By</th></tr></c-slot>
    <tr><td>Today</td><td>Ada</td></tr>
</c-panel-table>
"""

WITH_CARDS = """
<c-panel-table caption="Rows" cards="true">
    <c-slot name="head"><tr><th scope="col">Email</th><th scope="col">Line</th></tr></c-slot>
    <tr><td>a@example.com</td><td>2</td></tr>
    <c-slot name="card_rows">
        <c-panel-table-card primary="a@example.com">
            <c-panel-definition-row label="Line">2</c-panel-definition-row>
        </c-panel-table-card>
    </c-slot>
</c-panel-table>
"""


def _parse(source: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(f"<div>{render_cotton(source)}</div>")


def test_the_table_has_a_caption_and_column_header_cells() -> None:
    document = _parse(PLAIN)

    (caption,) = document.cssselect("table > caption")
    assert caption.text_content().strip() == "Generated reports"
    headers = document.cssselect("thead th")
    assert [header.get("scope") for header in headers] == ["col", "col"]
    assert [
        row.cssselect("td")[1].text_content() for row in document.cssselect("tbody tr")
    ] == ["Ada"]


def test_the_scroll_region_is_focusable_and_named_from_the_caption() -> None:
    document = _parse(PLAIN)

    (region,) = document.cssselect("[role=region]")
    assert region.get("tabindex") == "0"
    assert region.get("aria-label") == "Generated reports"
    assert region.cssselect("table")


def test_other_attributes_land_on_the_table() -> None:
    document = _parse(PLAIN)

    assert document.cssselect("table[data-report-rows]")


def test_without_cards_no_card_list_renders() -> None:
    document = _parse(PLAIN)

    assert not document.cssselect("ul[data-row-cards]")
    assert not document.cssselect("[role=region].hidden")


def test_without_capped_the_region_is_not_marked_capped() -> None:
    document = _parse(PLAIN)

    assert not document.cssselect("[data-capped]")


def test_capped_marks_the_region() -> None:
    document = _parse(
        PLAIN.replace(
            'caption="Generated reports"', 'caption="Generated reports" capped="true"'
        )
    )

    (region,) = document.cssselect("[role=region][data-capped]")
    assert region.get("tabindex") == "0"


def test_with_cards_each_card_row_is_a_labelled_definition_list() -> None:
    document = _parse(WITH_CARDS)

    (card,) = document.cssselect("ul[data-row-cards] > li")
    assert "a@example.com" in card.text_content()
    assert [dt.text_content() for dt in card.cssselect("dl dt")] == ["Line"]
    assert [dd.text_content() for dd in card.cssselect("dl dd")] == ["2"]


def test_with_cards_the_card_list_is_its_own_labelled_focusable_region() -> None:
    document = _parse(WITH_CARDS)

    regions = document.cssselect("[role=region]")
    assert [region.get("aria-label") for region in regions] == ["Rows", "Rows"]
    assert all(region.get("tabindex") == "0" for region in regions)
    assert regions[1].cssselect("ul[data-row-cards]")
