Make the site header stick to the top of the viewport and blur its background once the page has scrolled.

Background research lives alongside this file:
- `research_sticky_header.md`

Use playwright mcp to take screenshots before/after every visual change so regressions are caught. Verify each change at desktop, tablet, and mobile widths.

## Sticky header that blurs on scroll

On every page, the site header bar should remain in view as the user scrolls, and become a frosted-glass blur once the page has scrolled past the top.

- Use `position: sticky; top: 0` — not `fixed`. Sticky stays in document flow and avoids layout shift.
- At the top of the page, the header is transparent / un-blurred. Once the user scrolls past a threshold (~16–32px), apply a translucent background + `backdrop-filter: blur(...)`. Trigger via Alpine `@scroll.window.passive` with a single boolean.
- Always include `-webkit-backdrop-filter` and a near-opaque fallback for browsers without backdrop-filter support, gated by `@supports` (Tailwind's `supports-[backdrop-filter]:` works).
- Transition only `background-color`, `border-color`, `box-shadow`, and `backdrop-filter` — never width/height/padding — to avoid content jump. Use a transparent border at rest so the on-scroll border doesn't shift layout.
- Respect `prefers-reduced-transparency` and `prefers-reduced-motion` (fall back to a solid bg).
- Verify contrast against the worst-case page background, not just the resting state.
- Z-index discipline: header below modals and dropdowns.
