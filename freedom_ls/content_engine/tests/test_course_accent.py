"""Tests for the :data:`PALETTE` contract — pure unit tests, no Django needed."""

from __future__ import annotations

from freedom_ls.content_engine.course_accent import PALETTE


def test_palette_has_five_entries() -> None:
    assert len(PALETTE) == 5


def test_palette_is_decoupled_from_ui_role_names() -> None:
    """Card accents are a separate themeable series, not the UI role tokens.

    Guards the design contract: the slot keys must not be semantic role
    names, so recolouring cards never recolours buttons/badges.
    """
    ui_roles = {"primary", "secondary", "accent", "info", "success", "error", "warning"}
    assert not (set(PALETTE) & ui_roles)
