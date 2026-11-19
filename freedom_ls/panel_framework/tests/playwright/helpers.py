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
