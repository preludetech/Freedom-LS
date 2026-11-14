"""Tests for the <c-panel-status-badge /> cotton component."""

from __future__ import annotations

import pytest

from ..cotton_helpers import render_cotton


@pytest.mark.parametrize("tone", ["success", "warning", "error", "info", "muted"])
def test_known_tone_renders_its_own_chip_variant(tone: str) -> None:
    html = render_cotton(f'<c-panel-status-badge tone="{tone}" label="Active" />')

    assert f"chip-{tone}" in html


@pytest.mark.parametrize("tone", ["primary", "secondary", "unknown", ""])
def test_unmapped_tone_falls_back_to_muted(tone: str) -> None:
    html = render_cotton(f'<c-panel-status-badge tone="{tone}" label="Active" />')

    assert "chip-muted" in html


def test_label_is_escaped() -> None:
    html = render_cotton('<c-panel-status-badge tone="success" label="<script>" />')

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_caller_attribute_lands_on_the_chip() -> None:
    html = render_cotton(
        '<c-panel-status-badge tone="success" label="Active" data-testid="status" />'
    )

    assert 'data-testid="status"' in html


class _Badge:
    tone = "warning"
    label = "Pending"


def test_a_badge_object_supplies_the_tone_and_the_label() -> None:
    html = render_cotton("<c-panel-status-badge :badge='badge' />", badge=_Badge())

    assert "chip-warning" in html
    assert "Pending" in html


def test_a_badge_object_wins_over_separate_attributes() -> None:
    html = render_cotton(
        '<c-panel-status-badge :badge="badge" tone="success" label="Active" />',
        badge=_Badge(),
    )

    assert "chip-warning" in html
    assert "Active" not in html
