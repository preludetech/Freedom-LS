"""Viewport sizes and layout assertions shared by panel_framework's Playwright tests."""

from __future__ import annotations

from playwright.sync_api import Page, ViewportSize

# Phone, tablet and desktop widths a flow's layout checks run at.
QA_VIEWPORTS: tuple[ViewportSize, ...] = (
    {"width": 375, "height": 812},
    {"width": 768, "height": 1024},
    {"width": 1920, "height": 1080},
)


def assert_no_horizontal_overflow(page: Page) -> None:
    """The document is no wider than its viewport, once layout has settled."""
    page.wait_for_function("document.documentElement.scrollWidth <= window.innerWidth")


def resize_viewport(page: Page, viewport: ViewportSize) -> None:
    """Resize the page and wait for the shell to apply the new breakpoint.

    The shell docks or undocks its navigation panel from a media-query
    change event that fires after the resize returns, and docking moves the
    content sideways. Measuring before that handler runs reads the old layout
    for some elements and the new one for others.
    """
    page.set_viewport_size(viewport)
    page.wait_for_function(
        """() => {
            const nav = document.querySelector("dialog[data-shell-navigation]");
            if (!nav || !window.Alpine) return true;
            const desktop = window.matchMedia("(min-width: 1024px)").matches;
            return Alpine.$data(nav).isMobile === !desktop;
        }"""
    )
