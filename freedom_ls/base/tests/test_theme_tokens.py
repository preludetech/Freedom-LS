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

import re
import shutil
import subprocess
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


# --- first_class theme token contract -------------------------------------


def test_first_class_theme_declares_mono_font_token_with_ibm_plex_first() -> None:
    css = FIRST_CLASS_THEME_CSS.read_text()
    assert "--fls-font-mono:" in css
    assert "IBM Plex Mono" in css
    # No --font-mono inline alias — inherited from default.
    assert "--font-mono:" not in css


def test_first_class_theme_radii_match_design_system() -> None:
    css = FIRST_CLASS_THEME_CSS.read_text()
    assert "--fls-radius-sm: 0.375rem" in css
    assert "--fls-radius-md: 0.5rem" in css
    assert "--fls-radius-lg: 0.75rem" in css


@pytest.mark.parametrize("role", ["success", "warning", "error", "info"])
def test_first_class_theme_declares_status_light_tokens(role: str) -> None:
    css = FIRST_CLASS_THEME_CSS.read_text()
    assert f"--color-{role}-light:" in css
    assert f"--color-on-{role}-light:" in css


def test_first_class_theme_has_layer_components_overrides() -> None:
    css = FIRST_CLASS_THEME_CSS.read_text()
    assert "@layer components" in css
    for cls in (
        ".btn",
        ".chip",
        ".chip-success",
        ".chip-info",
        ".btn-secondary",
        ".alert-success",
        ".surface",
    ):
        assert cls in css, f"Expected first_class theme to override {cls}"


def test_first_class_theme_has_layer_base_heading_overrides() -> None:
    css = FIRST_CLASS_THEME_CSS.read_text()
    assert "@layer base" in css
    # Spot-check the heading rules — match leniently on whitespace.
    for tag in ("h1", "h2", "h3", "h4"):
        assert re.search(rf"\b{tag}\s*\{{", css), f"Missing override for <{tag}>"


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


def test_components_css_no_longer_declares_btn_outline() -> None:
    css = COMPONENTS_CSS.read_text()
    assert re.search(r"\.btn-outline\b", css) is None


# --- Repo-wide call-site audit --------------------------------------------


def test_no_template_uses_btn_outline_or_button_variant_outline() -> None:
    """No button call site uses ``btn-outline`` or a ``variant=outline`` form.

    Catches the rendered class ``btn-outline`` plus three variant-source
    forms — HTML attribute (``variant="outline"``), python kwarg
    (``variant="outline"``), and python dict literal
    (``"variant": "outline"``). Excludes ``freedom_ls/icons/`` where
    ``variant="outline"`` is the icon-style variant (outline vs solid
    icons), not a button variant.
    """
    grep_path = shutil.which("grep")
    assert grep_path is not None, "grep is required for this test"
    result = subprocess.run(  # noqa: S603 - fixed args, no user input
        [
            grep_path,
            "-rln",
            "-E",
            "--include=*.html",
            "--include=*.py",
            r"""\bbtn-outline\b|["']?variant["']?\s*[:=]\s*["']outline["']""",
            str(FREEDOM_LS_PACKAGE_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    hits = [
        line
        for line in result.stdout.splitlines()
        if "/icons/" not in line and "/tests/" not in line
    ]
    assert hits == [], f"Unexpected btn-outline / variant=outline usage: {hits}"
