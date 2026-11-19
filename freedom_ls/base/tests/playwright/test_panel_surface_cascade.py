"""A theme's `.panel-surface` rule still wins over the framework stylesheet."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from freedom_ls.base.tests.tailwind_build import build_fls_css_with_theme

SURFACE_PROBE = '<div id="probe" style="background-color: var(--color-surface)"></div>'
PANEL = '<div id="panel" class="panel-surface">content</div>'
WHITE = "rgb(255, 255, 255)"


def _backgrounds(page: Page, css_path: str) -> tuple[str, str]:
    """The computed backgrounds of a `.panel-surface` and of the `surface` token."""
    page.set_content(f"{PANEL}{SURFACE_PROBE}")
    page.add_style_tag(path=css_path)
    panel = page.evaluate(
        "getComputedStyle(document.getElementById('panel')).backgroundColor"
    )
    surface = page.evaluate(
        "getComputedStyle(document.getElementById('probe')).backgroundColor"
    )
    return panel, surface


@pytest.mark.playwright
def test_the_first_class_theme_panel_surface_is_white_and_not_the_surface_token(
    page: Page, tmp_path_factory: pytest.TempPathFactory
) -> None:
    build_dir = tmp_path_factory.mktemp("first_class_build")
    css = build_fls_css_with_theme(build_dir, "first_class")
    (build_dir / "built.css").write_text(css)

    panel, surface = _backgrounds(page, str(build_dir / "built.css"))

    assert (panel, surface != WHITE) == (WHITE, True)


@pytest.mark.playwright
def test_the_default_theme_panel_surface_is_the_surface_token(
    page: Page, tmp_path_factory: pytest.TempPathFactory
) -> None:
    build_dir = tmp_path_factory.mktemp("default_build")
    css = build_fls_css_with_theme(build_dir, "default")
    (build_dir / "built.css").write_text(css)

    panel, surface = _backgrounds(page, str(build_dir / "built.css"))

    assert panel == surface
