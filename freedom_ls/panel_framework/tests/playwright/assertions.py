"""Shared browser assertions for panel_framework's Playwright tests."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def expect_no_nested_panel(page: Page, name: str = "default") -> None:
    """Exactly one panel called `name`, holding no other <section>.

    An htmx swap that returned a whole panel into its own region would nest a
    second frame inside the first, and repeat on every swap.
    """
    panel = page.locator(f"[data-panel='{name}']")
    expect(panel).to_have_count(1)
    expect(panel.locator("section")).to_have_count(0)
