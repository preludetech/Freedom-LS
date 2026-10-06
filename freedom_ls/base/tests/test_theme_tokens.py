"""Tests for Tier-1 / Tier-2 theme contract assertions.

These tests guard the token + component contract for the FLS default and
``first_class`` themes.

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


def test_default_theme_declares_footer_tokens() -> None:
    css = DEFAULT_THEME_CSS.read_text()
    assert "--color-footer:" in css
    assert "--color-on-footer:" in css


def _theme_colour(css: str, name: str) -> str:
    match = re.search(rf"--color-{name}:\s*(#[0-9A-Fa-f]{{6}})\b", css)
    assert match is not None, f"--color-{name} is not a #RRGGBB value"
    return match.group(1)


def _relative_luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(
    "theme_css",
    [DEFAULT_THEME_CSS, FIRST_CLASS_THEME_CSS],
    ids=["default", "first_class"],
)
def test_muted_text_reaches_4_5_to_1_on_every_page_surface(theme_css: Path) -> None:
    """Muted text sits on white cards, the surface canvas and surface-2 fills
    (table headers), so it must clear WCAG AA body-text contrast on all three."""
    css = theme_css.read_text()
    muted = _theme_colour(css, "muted")
    for background in (
        "#FFFFFF",
        _theme_colour(css, "surface"),
        _theme_colour(css, "surface-2"),
    ):
        assert _contrast_ratio(muted, background) >= 4.5, (
            f"--color-muted {muted} on {background} is "
            f"{_contrast_ratio(muted, background):.2f}:1"
        )


# --- tailwind.components.css contract -------------------------------------


def test_components_css_declares_new_button_classes() -> None:
    css = COMPONENTS_CSS.read_text()
    for cls in (".btn-secondary", ".btn-ghost", ".btn-accent"):
        assert cls in css


def test_components_css_declares_new_chip_classes() -> None:
    css = COMPONENTS_CSS.read_text()
    for cls in (".chip-info", ".chip-secondary", ".chip-muted"):
        assert cls in css


@pytest.mark.parametrize("role", ["success", "warning", "error", "info"])
def test_status_chip_classes_use_the_light_token_pair(role: str) -> None:
    """The status chips must clear 4.5:1, which the `-light` token pair does
    and the base role tokens (used directly) do not."""
    css = COMPONENTS_CSS.read_text()
    rule_match = re.search(rf"\.chip-{role}\s*\{{([^}}]*)\}}", css)
    assert rule_match is not None

    rule = rule_match.group(1)
    assert f"bg-{role}-light" in rule
    assert f"text-on-{role}-light" in rule


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
