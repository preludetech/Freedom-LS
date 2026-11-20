"""HOST_CONTRACT.md states the lists the code defines."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.panel_framework.checks import REQUIRED_ICON_NAMES

PACKAGE_DIR = Path(__file__).resolve().parents[2]
CONTRACT = (PACKAGE_DIR / "HOST_CONTRACT.md").read_text()
REFERENCE_THEME = (PACKAGE_DIR / "css/reference_theme.css").read_text()
COTTON_DIR = PACKAGE_DIR / "templates/cotton"

FENCED_BLOCK = re.compile(r"```[a-z]*\n(.*?)```", re.S)
HEADING = re.compile(r"^## (.+)$", re.M)
TABLE_ROW = re.compile(r"^\| `(panel-[a-z-]+)` \([^)]*\) \| (.*?) \| .*\|$", re.M)
BACKTICKED = re.compile(r"`(\w+)`")
C_VARS = re.compile(r"<c-vars(.*?)/>", re.S)
C_VARS_ATTRIBUTE = re.compile(r"(\w+)=")

PRIMITIVES = {
    "panel-back-link",
    "panel-button",
    "panel-button-group",
    "panel-callout",
    "panel-chip",
    "panel-date",
    "panel-datetime",
    "panel-dropdown-menu",
    "panel-dropdown-menu-separator",
    "panel-icon",
    "panel-page",
    "panel-pagination",
}


def _section(heading: str) -> str:
    """The text under `## heading`, up to the next `## ` heading."""
    start = CONTRACT.index(f"\n## {heading}\n")
    following = HEADING.search(CONTRACT, start + 4)
    return CONTRACT[start : following.start() if following else len(CONTRACT)]


def _block_lines(heading: str) -> set[str]:
    """The lines of the one fenced block under `## heading`."""
    (block,) = FENCED_BLOCK.findall(_section(heading))
    return set(block.split())


def _props_by_primitive() -> dict[str, set[str]]:
    return {
        name: set(BACKTICKED.findall(props))
        for name, props in TABLE_ROW.findall(_section("Primitives"))
    }


def _c_vars(primitive: str) -> set[str]:
    match = C_VARS.search((COTTON_DIR / f"{primitive}.html").read_text())
    return set(C_VARS_ATTRIBUTE.findall(match.group(1))) if match else set()


def test_the_tokens_block_equals_the_tokens_the_reference_theme_defines() -> None:
    defined = set(re.findall(r"^\s*(--color-[\w-]+):", REFERENCE_THEME, re.M))

    assert _block_lines("Tokens") ^ defined == set()


def test_the_icons_block_equals_the_required_icon_names() -> None:
    assert _block_lines("Icons") ^ REQUIRED_ICON_NAMES == set()


def test_the_primitives_table_has_one_row_per_primitive() -> None:
    assert set(_props_by_primitive()) ^ PRIMITIVES == set()


@pytest.mark.parametrize("anchor_heading", ["Icons"])
def test_a_check_hint_anchor_is_a_heading(anchor_heading: str) -> None:
    assert f"\n## {anchor_heading}\n" in CONTRACT


@pytest.mark.parametrize("primitive", sorted(PRIMITIVES))
def test_the_props_a_primitive_lists_equal_its_c_vars(primitive: str) -> None:
    assert _props_by_primitive()[primitive] ^ _c_vars(primitive) == set()


def test_minimal_shell_styles_headings_and_the_contract_lists_them() -> None:
    """The minimal shell's base layer sized no headings, so every h1 and h2
    rendered at body size and weight, and the contract never told a host to
    supply them."""
    stylesheet = (PACKAGE_DIR / "css/minimal_shell.css").read_text()
    base_layer = stylesheet[stylesheet.index("@layer base") :]
    for heading in ("h1", "h2"):
        rule = re.search(rf"^\s*{heading}\s*\{{(.*?)\}}", base_layer, re.M | re.S)
        assert rule is not None, f"minimal_shell.css has no base rule for {heading}"
        assert "font-bold" in rule.group(1)
        assert re.search(r"text-(xl|lg)", rule.group(1))
    assert "`h1`" in CONTRACT
    assert "`h2`" in CONTRACT
