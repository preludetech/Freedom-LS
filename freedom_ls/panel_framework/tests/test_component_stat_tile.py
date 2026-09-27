"""Tests for the <c-panel-stat-tile /> and <c-panel-stat-row /> cotton components."""

from __future__ import annotations

import re

import pytest

from .cotton_helpers import render_cotton


def test_label_precedes_value_in_source() -> None:
    """The label is a <dt> before the value's <dd>, so the definition list is
    valid even though CSS reorders them so the value shows on top."""
    html = render_cotton('<c-panel-stat-tile label="Learners" value="42" />')

    assert html.index("<dt") < html.index("<dd")


def test_label_and_value_render() -> None:
    html = render_cotton('<c-panel-stat-tile label="Learners" value="42" />')

    assert "Learners" in html
    assert "42" in html


def test_direction_up_renders_the_decorative_trend_up_icon() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Progress" value="80%" delta="Up 4 points" direction="up" />'
    )

    assert re.search(
        r'<span aria-hidden="true">\s*<svg[^>]*aria-label="trend_up"', html
    )
    assert "Up 4 points" in html


def test_direction_down_renders_the_decorative_trend_down_icon() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Progress" value="60%" delta="Down 2 points" direction="down" />'
    )

    assert re.search(
        r'<span aria-hidden="true">\s*<svg[^>]*aria-label="trend_down"', html
    )
    assert "Down 2 points" in html


def test_direction_flat_renders_no_trend_icon() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Progress" value="60%" delta="No change" direction="flat" />'
    )

    assert "<svg" not in html
    assert "No change" in html


@pytest.mark.parametrize("tone", ["success", "warning", "error", "info", "muted"])
def test_tone_does_not_change_which_icon_renders(tone: str) -> None:
    """The delta's icon is picked from `direction` alone; `tone` only colours
    the text, so every tone renders the same trend_up icon."""
    html = render_cotton(
        f'<c-panel-stat-tile label="Progress" value="80%" delta="Up 4 points" '
        f'direction="up" tone="{tone}" />'
    )

    assert re.search(
        r'<span aria-hidden="true">\s*<svg[^>]*aria-label="trend_up"', html
    )


def test_direction_does_not_change_the_tone_class() -> None:
    """Two tiles with the same tone but different directions get the same
    tone text colour class regardless of direction."""
    up_html = render_cotton(
        '<c-panel-stat-tile label="Progress" value="80%" delta="Up 4 points" '
        'direction="up" tone="success" />'
    )
    down_html = render_cotton(
        '<c-panel-stat-tile label="Progress" value="60%" delta="Down 2 points" '
        'direction="down" tone="success" />'
    )

    up_delta = up_html[up_html.index("order-5") : up_html.index("Up 4 points")]
    down_delta = down_html[
        down_html.index("order-5") : down_html.index("Down 2 points")
    ]

    assert "text-on-success-light" in up_delta
    assert "text-on-success-light" in down_delta


def test_no_delta_dd_when_delta_is_empty() -> None:
    html = render_cotton('<c-panel-stat-tile label="Learners" value="42" />')

    assert "<svg" not in html
    assert html.count("<dd") == 1


def test_default_slot_renders_after_the_value() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Average progress" value="72%">'
        '<progress value="72" max="100"></progress>'
        "</c-panel-stat-tile>"
    )

    value_index = html.index("72%")
    progress_index = html.index("<progress")

    assert value_index < progress_index


def test_sub_line_renders() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Learners" value="42" sub="Across 3 cohorts" />'
    )

    assert "Across 3 cohorts" in html


def test_unknown_variant_renders_the_boxed_default() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="Learners" value="42" variant="unexpected" />'
    )

    assert "Learners" in html
    assert "42" in html


def test_label_is_escaped() -> None:
    html = render_cotton(
        '<c-panel-stat-tile label="<script>alert(1)</script>" value="42" />'
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("variant", ["boxed", "inline"])
def test_stat_row_renders_the_slot_inside_one_root_element(variant: str) -> None:
    html = render_cotton(
        f'<c-panel-stat-row variant="{variant}">'
        '<c-panel-stat-tile label="Learners" value="42" />'
        '<c-panel-stat-tile label="Cohorts" value="3" />'
        "</c-panel-stat-row>"
    )

    assert html.count("Learners") == 1
    assert html.count("Cohorts") == 1
    assert html.count("<div") == 1
