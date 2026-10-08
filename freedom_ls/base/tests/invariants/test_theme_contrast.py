"""Muted text must stay readable on every page surface of the shipped themes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

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
