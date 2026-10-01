"""Tests for cotton/data-table-cells/link.html's quick_view column key."""

from __future__ import annotations

from django.template.loader import render_to_string

from .conftest import StubModel

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
