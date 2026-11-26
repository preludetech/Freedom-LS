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


def test_the_button_is_disabled_while_the_dialog_is_running() -> None:
    close = _render("<c-panel-close-button />")

    assert close.get("x-bind:disabled") == "running"


def test_the_button_renders_describedby_when_given() -> None:
    close = _render('<c-panel-close-button describedby="run-status" />')

    assert close.get("aria-describedby") == "run-status"


def test_the_button_has_no_description_by_default() -> None:
    assert _render("<c-panel-close-button />").get("aria-describedby") is None


def test_the_link_has_neither_a_disabled_binding_nor_a_description() -> None:
    close = _render('<c-panel-close-button href="/back/" describedby="run-status" />')

    assert close.get("x-bind:disabled") is None
    assert close.get("aria-describedby") is None
