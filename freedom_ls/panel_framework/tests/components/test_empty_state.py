"""Tests for the <c-panel-empty-state /> cotton component."""

from __future__ import annotations

import re

from ..cotton_helpers import render_cotton


def test_icon_is_decorative() -> None:
    html = render_cotton('<c-panel-empty-state icon="notes" message="No results" />')

    assert re.search(
        r'<span aria-hidden="true"[^>]*>\s*<svg[^>]*data-icon="notes"', html
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


def test_compact_size_is_a_muted_small_paragraph_with_no_icon() -> None:
    html = render_cotton(
        '<c-panel-empty-state size="compact" icon="notes" message="No reports yet." />'
    )

    assert "<svg" not in html
    assert re.search(r'<p class="text-sm text-muted">No reports yet\.</p>', html)
    assert "py-10" not in html


def test_compact_size_renders_the_slot() -> None:
    html = render_cotton(
        '<c-panel-empty-state size="compact" message="None">'
        '<c-button href="/new/">Add</c-button></c-panel-empty-state>'
    )

    assert "Add" in html
