"""Tests for the <c-panel-page-header /> cotton component."""

from __future__ import annotations

import pytest

from .cotton_helpers import render_cotton


def test_default_heading_level_is_h1() -> None:
    html = render_cotton('<c-panel-page-header title="Overview" />')

    assert "<h1>Overview</h1>" in html


def test_heading_level_3_renders_h3() -> None:
    html = render_cotton('<c-panel-page-header title="Overview" heading_level="3" />')

    assert "<h3>Overview</h3>" in html


@pytest.mark.parametrize("heading_level", ["0", "7", "abc", ""])
def test_an_unknown_heading_level_falls_back_to_h1(heading_level: str) -> None:
    html = render_cotton(
        f'<c-panel-page-header title="Overview" heading_level="{heading_level}" />'
    )

    assert "<h1>Overview</h1>" in html


def test_title_id_lands_on_the_heading_element() -> None:
    html = render_cotton(
        '<c-panel-page-header title="Overview" title_id="instance-title" />'
    )

    assert '<h1 id="instance-title">Overview</h1>' in html


def test_badge_slot_content_renders_outside_the_heading_element() -> None:
    html = render_cotton(
        """
        <c-panel-page-header title="Overview">
            <c-slot name="badge"><span data-testid="badge">Active</span></c-slot>
        </c-panel-page-header>
        """
    )

    heading_end = html.index("</h1>")
    badge_start = html.index("data-testid")
    assert badge_start > heading_end


def test_meta_slot_renders_when_given() -> None:
    html = render_cotton(
        """
        <c-panel-page-header title="Overview">
            <c-slot name="meta">learner@example.com</c-slot>
        </c-panel-page-header>
        """
    )

    assert "learner@example.com" in html


def test_no_action_group_renders_when_the_actions_slot_is_absent() -> None:
    html = render_cotton('<c-panel-page-header title="Overview" />')

    assert "flex justify-end gap-3" not in html


def test_no_action_group_renders_when_the_actions_slot_is_whitespace() -> None:
    html = render_cotton(
        """
        <c-panel-page-header title="Overview">
            <c-slot name="actions">   </c-slot>
        </c-panel-page-header>
        """
    )

    assert "flex justify-end gap-3" not in html


def test_actions_slot_renders_inside_a_button_group() -> None:
    html = render_cotton(
        """
        <c-panel-page-header title="Overview">
            <c-slot name="actions"><button>Save</button></c-slot>
        </c-panel-page-header>
        """
    )

    assert "flex justify-end gap-3" in html
    assert "<button>Save</button>" in html


def test_title_is_escaped() -> None:
    html = render_cotton('<c-panel-page-header title="<script>" />')

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
