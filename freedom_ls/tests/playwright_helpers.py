"""Plain helpers for Playwright flow tests (fixtures live in ``playwright_fixtures``)."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, ViewportSize

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


# Space left under a form's visible children: the form's content-box bottom minus the
# lowest bottom edge (margin included) among its children that generate a box.
_SPACE_BELOW_LAST_CHILD = """(form) => {
    const style = getComputedStyle(form);
    const contentBottom = form.getBoundingClientRect().bottom
        - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth);
    let lowest = -Infinity;
    for (const child of form.children) {
        if (getComputedStyle(child).display === "none") continue;
        const bottom = child.getBoundingClientRect().bottom
            + parseFloat(getComputedStyle(child).marginBottom);
        lowest = Math.max(lowest, bottom);
    }
    return contentBottom - lowest;
}"""


def assert_no_space_below_field_row(form: Locator) -> None:
    """The form's last visible child ends where the form's content box ends."""
    space = form.evaluate(_SPACE_BELOW_LAST_CHILD)
    assert abs(space) <= 1, f"{space}px of space under the form's last visible child"


# An element's computed colours as sRGB. Painting a colour on a 1x1 canvas and
# reading the pixel back makes the browser convert whatever notation the
# computed value uses (oklch(), color-mix(), color(srgb ...)) to 8-bit channels.
# The background is the element's fill and each ancestor's under it, painted over
# white, so a translucent fill resolves to the colour a reader sees.
_SRGB_COLOURS = """(el) => {
    const context = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    context.canvas.width = 1;
    context.canvas.height = 1;
    const toRgb = () => Array.from(context.getImageData(0, 0, 1, 1).data.slice(0, 3));
    const paint = (colour) => {
        context.fillStyle = colour;
        context.fillRect(0, 0, 1, 1);
    };
    paint("white");
    paint(getComputedStyle(el).color);
    const color = toRgb();
    paint("white");
    const chain = [];
    for (let node = el; node; node = node.parentElement) chain.unshift(node);
    for (const node of chain) paint(getComputedStyle(node).backgroundColor);
    return { color, background: toRgb() };
}"""


def _relative_luminance(rgb: list[int]) -> float:
    """WCAG 2 relative luminance of an 8-bit sRGB colour."""
    red, green, blue = (
        channel / 255 / 12.92
        if channel / 255 <= 0.04045
        else ((channel / 255 + 0.055) / 1.055) ** 2.4
        for channel in rgb
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(text: Locator, background: Locator) -> float:
    """The WCAG contrast ratio of ``text``'s colour against ``background``'s fill."""
    foreground = _relative_luminance(text.evaluate(_SRGB_COLOURS)["color"])
    fill = _relative_luminance(background.evaluate(_SRGB_COLOURS)["background"])
    lighter, darker = max(foreground, fill), min(foreground, fill)
    return (lighter + 0.05) / (darker + 0.05)
