"""Tests for the <c-panel-empty-state /> cotton component."""

from __future__ import annotations

import re

from .cotton_helpers import render_cotton


def test_icon_is_decorative() -> None:
    html = render_cotton('<c-panel-empty-state icon="notes" message="No results" />')

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*aria-label="notes"', html
    )


def test_no_icon_renders_no_icon_element() -> None:
    html = render_cotton('<c-panel-empty-state message="No results" />')

    assert "<svg" not in html


def test_message_is_inside_a_paragraph_with_no_heading() -> None:
    html = render_cotton('<c-panel-empty-state message="No results yet" />')

    assert "<p" in html
    assert ">No results yet<" in html.split("<p")[1]
    assert not re.search(r"<h[1-6]", html)


def test_slot_content_renders() -> None:
    html = render_cotton(
        '<c-panel-empty-state message="No results">'
        '<c-button href="/new/">Create one</c-button>'
        "</c-panel-empty-state>"
    )

    assert "Create one" in html
