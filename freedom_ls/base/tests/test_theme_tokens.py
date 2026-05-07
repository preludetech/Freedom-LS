"""Tests for Tier-1 / Tier-2 theme contract assertions.

These tests guard the token + component contract for the FLS default and
``first_class`` themes. They exist as a contract guard for the Tier-1 +
Tier-2 work in
``spec_dd/2. in progress/first-class-theme-implement-tier-1-and-2/``.

Per project conventions we do not test rendered classes / pixel widths /
colours — these tests check the *source* CSS files for the role tokens
and component classes the contract requires.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

REPO_ROOT: Path = FREEDOM_LS_PACKAGE_DIR.parent
DEFAULT_THEME_CSS: Path = (
    FREEDOM_LS_PACKAGE_DIR
    / "themes"
    / "default"
    / "static"
    / "themes"
    / "default"
    / "theme.css"
)
FIRST_CLASS_THEME_CSS: Path = (
    FREEDOM_LS_PACKAGE_DIR
    / "themes"
    / "first_class"
    / "static"
    / "themes"
    / "first_class"
    / "theme.css"
)
COMPONENTS_CSS: Path = REPO_ROOT / "tailwind.components.css"


# --- Default theme token contract -----------------------------------------


def test_default_theme_declares_mono_font_token() -> None:
    css = DEFAULT_THEME_CSS.read_text()
    assert "--fls-font-mono:" in css
    assert "--font-mono: var(--fls-font-mono)" in css


@pytest.mark.parametrize("role", ["success", "warning", "error", "info"])
def test_default_theme_declares_status_light_tokens(role: str) -> None:
    css = DEFAULT_THEME_CSS.read_text()
    assert f"--color-{role}-light:" in css
    assert f"--color-on-{role}-light:" in css


# --- tailwind.components.css contract -------------------------------------


def test_components_css_declares_new_button_classes() -> None:
    css = COMPONENTS_CSS.read_text()
    for cls in (".btn-secondary", ".btn-ghost", ".btn-accent"):
        assert cls in css


def test_components_css_declares_new_chip_classes() -> None:
    css = COMPONENTS_CSS.read_text()
    for cls in (".chip-info", ".chip-secondary", ".chip-muted"):
        assert cls in css


def test_components_css_declares_alert_family() -> None:
    css = COMPONENTS_CSS.read_text()
    for cls in (".alert", ".alert-success", ".alert-error", ".alert-info"):
        assert cls in css
