"""Tests for cotton/data-table-cells/link.html's quick_view column key."""

from __future__ import annotations

import lxml.html

from django.template.loader import render_to_string

from .conftest import StubModel
from .cotton_helpers import render_cotton

URL_NAME = "panel_framework_test:framework"


def test_a_quick_view_column_renders_the_trigger_attributes() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'hx-get="/test-panel/framework/stubs/1/__quick-view"' in html
    assert 'aria-controls="quick-view"' in html
    assert 'aria-expanded="false"' in html
    # The drawer's title comes only from the frame it loads, so it can never
    # disagree with what a cell happens to show.
    assert "data-quick-view-title" not in html
    assert 'hx-sync="#quick-view-body:replace"' in html


def test_a_column_without_quick_view_renders_a_plain_link() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'href="/test-panel/framework/stubs/1"' in html
    assert "hx-get" not in html
    assert "aria-controls" not in html


def test_a_blank_text_attr_renders_the_placeholder_without_a_link() -> None:
    row = StubModel(pk=1, name="")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert html.strip() == "-"
    assert "<a" not in html
    assert "hx-get" not in html


def test_a_column_without_quick_view_keeps_its_htmx_nav_link() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "htmx_nav": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'hx-get="/test-panel/framework/stubs/1"' in html
    assert 'hx-target="#main-content"' in html
    assert "aria-controls" not in html


def test_a_quick_view_column_renders_the_name_as_a_link_to_the_page() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
        "htmx_nav": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (name_link,) = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Ada"
    ]
    assert name_link.get("href") == "/test-panel/framework/stubs/1"
    assert name_link.get("hx-get") == "/test-panel/framework/stubs/1"
    assert name_link.get("hx-target") == "#main-content"
    assert name_link.get("aria-controls") is None


def test_a_quick_view_column_renders_a_labelled_icon_trigger_beside_the_name() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (trigger,) = document.cssselect('[aria-controls="quick-view"]')
    assert trigger.get("aria-label") == "Quick view: Ada"
    assert trigger.get("hx-get") == "/test-panel/framework/stubs/1/__quick-view"
    assert trigger.cssselect("svg")
    assert "Ada" not in trigger.text_content()
    links = document.cssselect("a")
    assert links.index(trigger) == len(links) - 1


def test_the_quick_view_trigger_shows_the_quick_view_icon() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (trigger,) = document.cssselect('[aria-controls="quick-view"]')
    (icon,) = trigger.cssselect("svg")
    assert icon.get("aria-label") == "quick_view"


def test_a_link_in_a_card_secondary_line_is_plain_weight() -> None:
    """A card's labelled values are plain body text, so a link cell among
    them must not keep the bold look it has as a table's name column."""
    row = StubModel(pk=1, name="Ada")
    column = {
        "template": "cotton/data-table-cells/link.html",
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
    }

    html = render_cotton(
        "<c-data-table-card :row=row :secondary_columns=columns />",
        row={"object": row, "label": "Ada"},
        columns=[column],
    )

    (link,) = lxml.html.fromstring(html).cssselect("a")
    classes = link.get("class").split()
    assert "font-bold" not in classes
    assert "text-on-surface" in classes


def test_a_link_in_a_table_cell_stays_bold() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    (link,) = lxml.html.fromstring(html).cssselect("a")
    assert "font-bold" in link.get("class").split()
