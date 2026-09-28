"""Tests for the <c-panel-card /> cotton component."""

from __future__ import annotations

from .cotton_helpers import render_cotton


def test_default_root_is_a_div() -> None:
    html = render_cotton("<c-panel-card>Body content</c-panel-card>")

    assert "<div" in html
    assert "<section" not in html
    assert "Body content" in html


def test_landmark_renders_a_section_labelled_by_the_heading() -> None:
    html = render_cotton('<c-panel-card title="Overview" landmark="true" />')

    assert '<section aria-labelledby="overview-title"' in html
    assert 'id="overview-title"' in html


def test_landmark_uses_the_callers_id_for_the_heading_id() -> None:
    html = render_cotton(
        '<c-panel-card title="Overview" landmark="true" id="custom" />'
    )

    assert '<section aria-labelledby="custom-title"' in html
    assert 'id="custom-title"' in html


def test_no_footer_renders_without_actions() -> None:
    html = render_cotton('<c-panel-card title="Overview">Body</c-panel-card>')

    assert "<footer" not in html


def test_actions_slot_renders_inside_a_footer() -> None:
    html = render_cotton(
        """
        <c-panel-card title="Overview">
            Body
            <c-slot name="actions"><button>Save</button></c-slot>
        </c-panel-card>
        """
    )

    assert "<footer" in html
    assert "<button>Save</button>" in html


def test_no_header_renders_without_a_title() -> None:
    html = render_cotton("<c-panel-card>Body</c-panel-card>")

    assert "<header" not in html


def test_header_action_slot_renders_inside_the_header() -> None:
    html = render_cotton(
        """
        <c-panel-card title="Overview">
            <c-slot name="header_action"><a href="#">View all</a></c-slot>
        </c-panel-card>
        """
    )

    header_start = html.index("<header")
    header_end = html.index("</header>")
    action_index = html.index("View all")

    assert header_start < action_index < header_end


def test_heading_level_3_renders_h3() -> None:
    html = render_cotton('<c-panel-card title="Overview" heading_level="3" />')

    assert "<h3" in html
    assert "Overview</h3>" in html


def test_description_renders_under_the_heading() -> None:
    html = render_cotton('<c-panel-card title="Overview" description="A summary" />')

    assert "A summary" in html


def test_landmark_without_a_title_renders_a_div() -> None:
    html = render_cotton('<c-panel-card landmark="true">Body</c-panel-card>')

    assert "<section" not in html
    assert "aria-labelledby" not in html


def test_landmark_false_string_renders_a_div() -> None:
    html = render_cotton('<c-panel-card title="Overview" landmark="False" />')

    assert "<section" not in html
    assert 'id="overview-title"' not in html
