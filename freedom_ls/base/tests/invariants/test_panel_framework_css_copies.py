"""FLS's copies of panel-framework stylesheet rules stay in step with the framework.

FLS's `panel-button` override draws `.btn`, not `.panel-btn`, so the framework
rules that select `.panel-btn` are copied onto `.btn` in `tailwind.components.css`.
FLS also keeps its own global `select` rule, which the framework scopes to panel
surfaces; the two must draw the same chevron.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

REPO_ROOT: Path = FREEDOM_LS_PACKAGE_DIR.parent
COMPONENTS_CSS: Path = REPO_ROOT / "tailwind.components.css"
FRAMEWORK_CSS: Path = FREEDOM_LS_PACKAGE_DIR / "panel_framework/css/panel_framework.css"
PANEL_SCOPE = ":is(.panel-surface, .panel-canvas) "


def _rule_body(css: str, selector: str) -> str:
    """The declarations of the one rule whose selector list is exactly `selector`
    (not the tail of a longer list), with whitespace collapsed."""
    pattern = re.compile(
        r"(?:\A|[{}/])\s*" + re.escape(selector) + r"\s*\{(.*?)\}", re.DOTALL
    )
    bodies = pattern.findall(css)
    assert len(bodies) == 1, f"expected one rule for {selector!r}, found {len(bodies)}"
    return " ".join(bodies[0].split())


@pytest.mark.parametrize(
    "selectors",
    [
        ["select"],
        ["select[multiple]", "select[size]"],
    ],
    ids=["select", "list-box"],
)
def test_the_select_chevron_matches_the_frameworks_copy(selectors: list[str]) -> None:
    fls_selector = ",\n    ".join(selectors)
    framework_selector = ",\n    ".join(PANEL_SCOPE + s for s in selectors)

    assert _rule_body(COMPONENTS_CSS.read_text(), fls_selector) == _rule_body(
        FRAMEWORK_CSS.read_text(), framework_selector
    )


def test_the_data_table_actions_nowrap_rule_is_copied_onto_btn() -> None:
    assert (
        "[&_.panel-btn]:whitespace-nowrap"
        in (
            FREEDOM_LS_PACKAGE_DIR
            / "panel_framework/templates/cotton/data-table-actions.html"
        ).read_text()
    )
    assert (
        _rule_body(COMPONENTS_CSS.read_text(), ".panel-data-table-actions .btn")
        == "@apply whitespace-nowrap"
    )
