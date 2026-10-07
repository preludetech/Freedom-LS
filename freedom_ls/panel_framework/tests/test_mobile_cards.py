"""Below md a table renders its rows as cards instead of a <table>, and its
toolbar collapses to a search box, applied-filter chips and Filter/Sort
buttons that open a shared filter-and-sort sheet.
"""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def test_cards_render_primary_and_secondary_columns(mock_site_context: Site) -> None:
    _make_stub(name="row-x", kind="a")

    html = fetch(_panel_path(_make_stub(name="row-y", kind="b").pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    cards = table.cssselect("ul li")
    assert cards
    card_texts = [card.text_content() for card in cards]
    assert any("row-x" in text and "Alpha" in text for text in card_texts)
    assert any("row-y" in text and "Beta" in text for text in card_texts)


def test_md_only_columns_are_omitted_from_cards(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-z", sat_score=4321)

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    assert "4321" not in card.text_content()
    (row,) = table.cssselect("table tbody tr")
    assert "4321" in row.text_content()


def test_card_template_override_is_used(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-custom")

    html = fetch(f"stubs/{stub.pk}/__tabs/cards").content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#cards-table")
    assert "Custom card for row-custom" in table.text_content()


def test_sheet_hidden_inputs_carry_other_state(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-00")

    html = fetch(
        f"stubs/{stub.pk}/__tabs/pair",
        data={"a-sort": "name", "a-page": "2", "a-kind": "a", "b-page": "2"},
    ).content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (sheet,) = table_a.cssselect("dialog#a-sheet")
    hidden_names = [
        field.get("name") for field in sheet.cssselect('input[type="hidden"]')
    ]
    assert "a-sort" not in hidden_names
    assert "a-page" not in hidden_names
    assert "a-kind" not in hidden_names
    assert "b-page" in hidden_names


def test_filter_and_sort_buttons_render_only_when_declared(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (table_a,) = document.cssselect("#a-table")
    (table_b,) = document.cssselect("#b-table")
    assert table_a.xpath(".//button[normalize-space()='Filter']")
    assert table_a.xpath(".//button[normalize-space()='Sort']")
    assert not table_b.xpath(".//button[normalize-space()='Filter']")
    assert not table_b.xpath(".//button[normalize-space()='Sort']")


def test_card_row_renders_primary_and_secondary_content(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-card", kind="a")

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    assert "row-card" in card.text_content()
    assert "Alpha" in card.text_content()


def test_card_secondary_values_are_labelled_with_their_column_header(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-labelled", kind="a")

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    pairs = [
        (term.text_content().strip(), term.getnext().text_content().strip())
        for term in card.cssselect("dl dt")
    ]
    assert pairs == [("Kind", "Alpha")]
    assert "Name" not in card.text_content()


def test_card_primary_line_ends_with_a_decorative_open_page_icon(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-open-page", kind="a")

    html = fetch(_panel_path(stub.pk)).content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#stub-table")
    (card,) = table.cssselect("ul li")
    (primary_line,) = card.cssselect("[data-card-primary-line]")
    (decoration,) = primary_line.xpath("./*[last()][@aria-hidden='true']")
    assert decoration.cssselect("svg")
    assert "row-open-page" in primary_line.text_content()
    assert not card.xpath("./*[@aria-hidden='true']")


def test_a_card_whose_primary_column_is_plain_text_draws_no_open_page_icon(
    mock_site_context: Site,
) -> None:
    """The icon promises a page to open; table b's name column is text."""
    stub = _make_stub(name="row-plain", kind="a")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (table,) = document.cssselect("#b-table")
    (card,) = table.cssselect("ul li")
    (primary_line,) = card.cssselect("[data-card-primary-line]")
    assert "row-plain" in primary_line.text_content()
    assert not primary_line.cssselect("svg")
    assert not primary_line.xpath("./*[@aria-hidden='true']")


def test_sheet_renders_reset_legends_and_footer_buttons(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect("#a-table dialog#a-sheet")
    assert sheet.xpath(".//a[normalize-space()='Reset']")
    legends = sheet.cssselect("fieldset legend")
    assert legends
    assert "Sort" in [legend.text_content().strip() for legend in legends]
    assert sheet.xpath(".//button[@type='button'][normalize-space()='Cancel']")
    assert sheet.xpath(".//button[@type='submit'][normalize-space()='Show results']")


def test_sheet_without_declared_filters_renders_no_filter_fieldset(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="row-00")

    html = fetch(f"stubs/{stub.pk}/__tabs/sortonly").content.decode()

    document = lxml.html.fromstring(html)
    (sheet,) = document.cssselect("dialog#sortonly-sheet")
    legends = [legend.text_content().strip() for legend in sheet.cssselect("legend")]
    assert legends == ["Sort"]
    assert not sheet.cssselect("select")
