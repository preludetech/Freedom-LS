"""The stylesheet-vs-template boundary.

`tailwind.components.css` carries the `@layer base` element rules, the classes a
theme is expected to reopen, and the classes the markdown renderer emits at render
time. A component's own styling belongs in that component's template, so shadowing
one file replaces its markup and its look together.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

REPO_ROOT: Path = FREEDOM_LS_PACKAGE_DIR.parent
COMPONENTS_CSS: Path = REPO_ROOT / "tailwind.components.css"
INPUT_CSS: Path = REPO_ROOT / "tailwind.input.css"


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
