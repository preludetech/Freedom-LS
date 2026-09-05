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
INPUT_CSS: Path = REPO_ROOT / "tailwind.input.css"


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


# --- Stylesheet-vs-template boundary --------------------------------------
#
# `tailwind.components.css` carries the `@layer base` element rules, the classes
# a theme is expected to reopen, and the classes the markdown renderer emits at
# render time. A component's own styling belongs in that component's template,
# so shadowing one file replaces its markup and its look together.


@pytest.mark.parametrize(
    ("selector", "owner"),
    [
        (".flashcard-", "freedom_ls/content_engine/templates/cotton/flashcard.html"),
        (".accordion", "freedom_ls/content_engine/templates/cotton/accordion.html"),
        (".picture-figure-", "freedom_ls/content_engine/templates/cotton/picture.html"),
        (
            ".spotlight-dialog",
            "freedom_ls/content_engine/templates/cotton/picture.html",
        ),
        (".side-panel-", "freedom_ls/base/templates/_base_interface.html"),
        (".htmx-hide-on-request", "freedom_ls/base/templates/cotton/button.html"),
        (".htmx-show-on-request", "freedom_ls/base/templates/cotton/button.html"),
    ],
)
def test_component_styling_stays_out_of_the_shared_stylesheet(
    selector: str, owner: str
) -> None:
    css = COMPONENTS_CSS.read_text()
    assert selector not in css, (
        f"`{selector}` styles one component and belongs in {owner}, "
        f"not in tailwind.components.css."
    )


def test_input_css_imports_only_the_three_project_stylesheets() -> None:
    """No per-widget stylesheets: a component's CSS lives in its template."""
    imports = re.findall(r'@import\s+"(\./[^"]+)"', INPUT_CSS.read_text())
    assert imports == [
        "./freedom_ls/themes/default/static/themes/default/theme.css",
        "./tailwind.components.css",
        "./tailwind.active_theme.css",
    ]
