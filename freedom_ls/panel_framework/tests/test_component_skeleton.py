"""Tests for the <c-panel-skeleton /> cotton component."""

from __future__ import annotations

from .cotton_helpers import render_cotton


def test_root_is_aria_hidden() -> None:
    html = render_cotton('<c-panel-skeleton shape="text" />')

    assert html.strip().startswith('<div aria-hidden="true"')


def test_lines_five_renders_five_line_markers_for_the_text_shape() -> None:
    html = render_cotton('<c-panel-skeleton shape="text" lines="5" />')

    assert html.count("data-skeleton-line") == 5


def test_unknown_shape_falls_back_to_the_text_shape_line_count() -> None:
    html = render_cotton('<c-panel-skeleton shape="not-a-real-shape" lines="4" />')

    assert html.count("data-skeleton-line") == 4


def test_tile_shape_renders_one_line_marker() -> None:
    html = render_cotton('<c-panel-skeleton shape="tile" />')

    assert html.count("data-skeleton-line") == 1


def test_row_shape_renders_two_line_markers() -> None:
    html = render_cotton('<c-panel-skeleton shape="row" />')

    assert html.count("data-skeleton-line") == 2
