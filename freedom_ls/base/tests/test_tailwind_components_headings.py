"""Tests that base-layer heading rules consume the display-font role token.

Headings (h1-h4) must apply ``font-display`` so that themes redeclaring
``--fls-font-display`` (e.g. First Class -> Outfit) actually drive the
heading typeface. The default theme aliases ``--fls-font-display`` to
``--fls-font-sans`` so this is a visual no-op under the default theme.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

REPO_ROOT: Path = FREEDOM_LS_PACKAGE_DIR.parent
TAILWIND_COMPONENTS_CSS: Path = REPO_ROOT / "tailwind.components.css"


def _extract_rule_body(css: str, selector: str) -> str:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(selector)}\s*\{{([^}}]+)\}}"
    match = re.search(pattern, css)
    assert match, f"Could not find rule for selector {selector!r}"
    return match.group(1)


@pytest.mark.parametrize("tag", ["h1", "h2", "h3", "h4"])
def test_heading_rule_applies_font_display(tag: str) -> None:
    css = TAILWIND_COMPONENTS_CSS.read_text()
    body = _extract_rule_body(css, tag)
    assert "font-display" in body, (
        f"<{tag}> base-layer rule must apply `font-display` so that the "
        f"--fls-font-display role token drives the heading typeface."
    )
