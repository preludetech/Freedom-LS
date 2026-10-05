"""Tests for the <c-panel-definition-list /> and <c-panel-definition-row /> cotton components."""

from __future__ import annotations

from .cotton_helpers import render_cotton


def test_root_is_a_dl() -> None:
    html = render_cotton("<c-panel-definition-list>Body</c-panel-definition-list>")

    assert "<dl" in html
    assert "Body" in html


def test_a_row_renders_one_dt_then_one_dd() -> None:
    html = render_cotton(
        '<c-panel-definition-row label="Name">Value</c-panel-definition-row>'
    )

    assert html.count("<dt") == 1
    assert html.count("<dd") == 1
    assert html.index("<dt") < html.index("<dd")
    assert "Name" in html
    assert "Value" in html


def test_an_unknown_columns_value_still_renders_a_dl() -> None:
    html = render_cotton(
        '<c-panel-definition-list columns="7">Body</c-panel-definition-list>'
    )

    assert "<dl" in html


def test_the_grid_is_two_columns_on_a_phone_and_three_on_a_desktop() -> None:
    html = render_cotton("<c-panel-definition-list>Body</c-panel-definition-list>")

    assert "grid-cols-2 md:grid-cols-3" in html
    assert "grid-cols-1" not in html
