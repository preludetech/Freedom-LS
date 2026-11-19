"""FLS's compiled stylesheet carries the panel framework's rules.

The framework stylesheet reaches the build through the generated
`tailwind.panel_framework.css`, so a selector missing from
`static/vendor/tailwind.output.css` means the import or the generated file broke.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

COMPILED_CSS: Path = FREEDOM_LS_PACKAGE_DIR.parent / "static/vendor/tailwind.output.css"


@pytest.mark.parametrize(
    "selector",
    [
        ".panel-surface",
        ".panel-canvas",
        ".panel-heading",
        ".panel-table-selection-bar",
        ".panel-data-table-compact",
        ".modal-backdrop-host::backdrop",
        ".bottom-sheet",
        ".bottom-sheet-bare",
        "@keyframes selection-bar-in",
    ],
)
def test_the_compiled_stylesheet_contains_the_framework_rule(selector: str) -> None:
    assert COMPILED_CSS.is_file(), (
        f"{COMPILED_CSS} is missing: run `npm run tailwind_build` first."
    )
    assert selector in COMPILED_CSS.read_text()
