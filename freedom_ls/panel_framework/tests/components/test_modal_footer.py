"""Tests for the <c-modal-footer /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def _render() -> lxml.html.HtmlElement:
    html = render_cotton(
        "<c-modal-footer>"
        '<c-slot name="cancel"><button type="button">Cancel</button></c-slot>'
        '<button type="submit">Save</button>'
        "</c-modal-footer>"
    )
    return lxml.html.fromstring(html)


def test_cancel_sits_in_the_first_box_and_the_actions_in_the_last() -> None:
    footer = _render()

    boxes = footer.findall("div")

    assert footer.tag == "footer"
    assert [button.text for button in boxes[0].findall("button")] == ["Cancel"]
    assert [button.text for button in boxes[1].findall("button")] == ["Save"]


def test_the_footer_pushes_cancel_and_the_actions_apart_and_stays_in_view() -> None:
    footer = _render()

    classes = footer.get("class", "").split()

    assert {"flex", "justify-between", "sticky", "bottom-0"} <= set(classes)
    assert "justify-end" in footer.findall("div")[1].get("class", "").split()
