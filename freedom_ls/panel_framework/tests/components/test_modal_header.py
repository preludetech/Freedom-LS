"""Tests for the <c-modal-header /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def _render(attrs: str = "") -> lxml.html.HtmlElement:
    return lxml.html.fromstring(
        render_cotton(f"<c-modal-header {attrs}>Move Thandi</c-modal-header>")
    )


def test_the_title_carries_the_id_the_dialog_is_labelled_by() -> None:
    title = _render().find("h2")

    assert title.get("id") == "app-modal-title"
    assert title.text == "Move Thandi"


def test_focus_title_makes_the_heading_take_focus() -> None:
    assert _render('focus_title="true"').find("h2").get("autofocus") is not None
    assert _render().find("h2").get("autofocus") is None


def test_close_href_reaches_the_close_control() -> None:
    close = _render('close_href="/back/"').find("a")

    assert close.get("href") == "/back/"


def test_without_close_href_the_close_control_asks_the_host_to_close() -> None:
    assert _render().find("button").get("x-on:click") == "requestClose"
