"""Tests for the <c-panel-definition-list /> and <c-panel-definition-row /> cotton components."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


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


def _list(layout: str) -> lxml.html.HtmlElement:
    source = (
        f'<c-panel-definition-list layout="{layout}">'
        '<c-panel-definition-row label="Name">Ada</c-panel-definition-row>'
        '<c-panel-definition-row label="Email">ada@example.com</c-panel-definition-row>'
        "</c-panel-definition-list>"
    )
    return lxml.html.fromstring(f"<div>{render_cotton(source)}</div>")


def test_both_layouts_render_each_row_as_a_term_and_a_value() -> None:
    for layout in ("stacked", "inline"):
        document = _list(layout)

        (dl,) = document.cssselect("dl")
        assert [dt.text_content() for dt in dl.cssselect("dt")] == ["Name", "Email"]
        assert [dd.text_content() for dd in dl.cssselect("dd")] == [
            "Ada",
            "ada@example.com",
        ]


def test_the_layouts_differ_in_how_the_list_arranges_its_rows() -> None:
    stacked = _list("stacked").cssselect("dl")[0].get("class")
    inline = _list("inline").cssselect("dl")[0].get("class")

    assert stacked != inline
    assert "grid-cols-[auto_minmax(0,1fr)]" in inline
    assert "grid-cols-[auto_minmax(0,1fr)]" not in stacked


def test_extra_attributes_land_on_the_list() -> None:
    document = lxml.html.fromstring(
        "<div>"
        + render_cotton(
            '<c-panel-definition-list layout="inline" data-test-list="x">Body</c-panel-definition-list>'
        )
        + "</div>"
    )

    assert document.cssselect("dl[data-test-list]")
