"""Plain helpers for Playwright flow tests (fixtures live in ``playwright_fixtures``)."""

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


# The left edge of what is drawn inside the elements a selector matches: text and
# anything with a border, background or replaced content. Empty wrappers are
# ignored, so a centred narrow column inside a wide wrapper reports the column.
_INK_LEFT = """(selector) => {
    let left = Infinity;
    const shown = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const paints = (el) => {
        const style = getComputedStyle(el);
        return ["IMG", "svg", "INPUT", "BUTTON"].includes(el.tagName)
            || parseFloat(style.borderLeftWidth) > 0
            || parseFloat(style.borderTopWidth) > 0
            || !/rgba\\(.*,\\s*0\\)$|transparent/.test(style.backgroundColor);
    };
    for (const root of document.querySelectorAll(selector)) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
        for (let node = walker.currentNode; node; node = walker.nextNode()) {
            if (node.nodeType === Node.TEXT_NODE) {
                if (!node.textContent.trim() || !shown(node.parentElement)) continue;
                const range = document.createRange();
                range.selectNodeContents(node);
                for (const rect of range.getClientRects()) left = Math.min(left, rect.left);
            } else if (shown(node) && paints(node)) {
                left = Math.min(left, node.getBoundingClientRect().left);
            }
        }
    }
    return left;
}"""


def assert_header_lines_up_with_content(page: Page) -> None:
    """The content header (breadcrumbs, title) starts where the page's content starts."""
    header_left = page.evaluate(_INK_LEFT, "#interface-main > div:first-of-type")
    content_left = page.evaluate(_INK_LEFT, "#interface-main > :not(div:first-of-type)")
    assert abs(header_left - content_left) <= 2, (
        f"header starts at x={header_left}, content at x={content_left}"
    )
