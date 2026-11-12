"""Tests for the <c-panel-close-button /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def _render(source: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(render_cotton(source))


def test_with_href_it_is_a_link() -> None:
    close = _render('<c-panel-close-button href="/back/" />')

    assert close.tag == "a"
    assert close.get("href") == "/back/"
    assert close.get("aria-label") == "Close"


def test_without_href_it_is_a_button_calling_request_close() -> None:
    close = _render("<c-panel-close-button />")

    assert close.tag == "button"
    assert close.get("type") == "button"
    assert close.get("x-on:click") == "requestClose"
    assert close.get("aria-label") == "Close"
