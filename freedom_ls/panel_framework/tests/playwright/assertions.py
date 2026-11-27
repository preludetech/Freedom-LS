"""Shared browser assertions for panel_framework's Playwright tests."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


def expect_no_nested_panel(page: Page, name: str = "default") -> None:
    """Exactly one panel called `name`, holding no other <section>.

    An htmx swap that returned a whole panel into its own region would nest a
    second frame inside the first, and repeat on every swap.
    """
    panel = page.locator(f"[data-panel='{name}']")
    expect(panel).to_have_count(1)
    expect(panel.locator("section")).to_have_count(0)


# Every visible text node and control on the canvas with no box around it.
# A box is a card or boxed stat tile ([data-panel-box]); a raised surface
# (.panel-surface: a card, the header band, a dialog) counts too.
_LOOSE_CANVAS_CONTENT = """
() => {
    const boxed = (element) =>
        element.closest(
            "[data-panel-box], .panel-surface, dialog, template, script, style, noscript"
        ) !== null;
    const shown = (element) => {
        if (!element.checkVisibility({ visibilityProperty: true })) return false;
        const box = element.getBoundingClientRect();
        return box.width > 1 && box.height > 1;
    };
    const loose = [];
    for (const canvas of document.querySelectorAll(".panel-canvas")) {
        const walker = document.createTreeWalker(canvas, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const text = node.textContent.trim();
            const parent = node.parentElement;
            if (text && !boxed(parent) && shown(parent)) loose.push(text.slice(0, 80));
        }
        const controls = "button, a[href], input:not([type=hidden]), select, textarea, img, svg";
        for (const control of canvas.querySelectorAll(controls)) {
            if (boxed(control) || !shown(control)) continue;
            if (control.textContent.trim()) continue;
            loose.push(control.outerHTML.slice(0, 80));
        }
    }
    return [...new Set(loose)];
}
"""


def assert_canvas_holds_only_boxes(page: Page) -> None:
    """Nothing visible sits on the page canvas outside a box.

    A notice, a date line, a button or an empty state belongs inside the card
    it is about, never between or beside the cards.
    """
    loose = page.evaluate(_LOOSE_CANVAS_CONTENT)
    assert loose == [], f"content on the canvas outside any box: {loose}"


def assert_is_error_callout(alert: Locator) -> None:
    """`alert` is the request-error callout: a tinted box with its icon.

    A failed request used to show as a bare red line.
    """
    expect(alert).to_be_visible()
    is_holder, background, icons = alert.evaluate(
        """el => [
            el.hasAttribute("data-request-error"),
            getComputedStyle(el).backgroundColor,
            el.querySelectorAll("svg").length,
        ]"""
    )
    assert is_holder, "the alert is not the request-error callout"
    assert background != "rgba(0, 0, 0, 0)", "the error callout has no tint"
    assert icons == 1, "the error callout has no icon"
