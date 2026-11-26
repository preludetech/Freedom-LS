"""Tests for the <c-panel-progress-bar /> cotton component."""

from __future__ import annotations

import pytest

from ..cotton_helpers import render_cotton


def test_renders_a_native_progress_element_with_an_aria_label() -> None:
    html = render_cotton(
        '<c-panel-progress-bar percentage="72" label="Course progress" />'
    )

    assert "<progress" in html
    assert 'aria-label="Course progress"' in html


def test_has_no_progressbar_role() -> None:
    html = render_cotton('<c-panel-progress-bar percentage="72" />')

    assert 'role="progressbar"' not in html


def test_percentage_text_appears_outside_the_progress_element() -> None:
    html = render_cotton('<c-panel-progress-bar percentage="72" />')

    progress_end = html.index("</progress>")

    assert "72%" not in html[: html.index("<progress")]
    assert "72%" in html[progress_end:]


@pytest.mark.parametrize(
    ("percentage", "expected_value"), [("-5", "0"), ("150", "100")]
)
def test_percentage_out_of_range_clamps_the_progress_value(
    percentage: str, expected_value: str
) -> None:
    html = render_cotton(f'<c-panel-progress-bar percentage="{percentage}" />')

    assert f'value="{expected_value}"' in html


def test_show_label_renders_the_label_as_visible_text() -> None:
    html = render_cotton(
        '<c-panel-progress-bar percentage="50" label="Reading" show_label="true" />'
    )

    assert ">Reading<" in html


def test_label_is_not_visible_text_without_show_label() -> None:
    html = render_cotton('<c-panel-progress-bar percentage="50" label="Reading" />')

    assert ">Reading<" not in html


def test_show_label_false_string_hides_the_visible_label() -> None:
    html = render_cotton(
        '<c-panel-progress-bar percentage="72" label="Course progress" show_label="False" />'
    )

    assert "Course progress</span>" not in html


def test_empty_percentage_renders_0() -> None:
    html = render_cotton('<c-panel-progress-bar percentage="" />')

    assert 'value="0"' in html
    assert "0%</span>" in html


def test_small_size_keeps_the_label_value_and_percentage_text() -> None:
    html = render_cotton(
        '<c-panel-progress-bar size="small" percentage="40" label="Intro progress" />'
    )

    assert 'aria-label="Intro progress"' in html
    assert 'value="40"' in html
    assert "40%" in html[html.index("</progress>") :]


def test_small_size_draws_a_thinner_bar_than_the_default() -> None:
    default = render_cotton('<c-panel-progress-bar percentage="40" />')
    small = render_cotton('<c-panel-progress-bar size="small" percentage="40" />')

    assert "h-2 " in default
    assert "h-1.5 " in small
    assert "h-2 " not in small
