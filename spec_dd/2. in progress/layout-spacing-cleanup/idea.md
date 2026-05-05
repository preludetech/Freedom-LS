Three related spacing issues across the learner experience. Fix them as one piece of work because the page-wrapper changes from #1 are what unblock #3, and the TOC sidebar in #2 lives inside the same layout system.

Background research lives alongside this file:
- `research_spacing.md`

Use playwright mcp to take screenshots before/after every visual change so regressions are caught. Verify each change at desktop, tablet, and mobile widths.

## 1. Spacing — fix top-down

Spacing is currently inconsistent: e.g. http://127.0.0.1:8000/courses/standard-markdown-demo-finance/ has no gap between the site header bar and the page heading. Fix top-down: start at `_base.html`, then page wrappers, then sections. Page templates should not have to add padding manually to compensate for layout decisions made above them.

Conventions to adopt (see `research_spacing.md`):
- Prefer `max-w-* mx-auto px-*` over Tailwind's `container` class.
- A single page-wrapper component owns horizontal padding and top/bottom breathing room, including space under the bottom action buttons.
- Use `scroll-padding-top` on `<html>` so anchor-link targets land below the sticky header.
- Keep the responsive ramp small (one or two breakpoints).
- Watch for double-padding (layout pad + page pad) and margin-collapse on flex/grid.

Verify responsiveness at multiple screen sizes.

## 2. TOC sidebar gap

http://127.0.0.1:8000/courses/standard-markdown-demo-finance/1/ — needs space between the table-of-contents sidebar and main content on large screens. Use a grid layout with `gap-*` (not margins on inner elements). Check spacing on small screens too — when the sidebar collapses there should still be sensible vertical separation.

## 3. Bottom-of-page breathing room

http://127.0.0.1:8000/courses/standard-markdown-demo-finance/2/ — add space at the bottom of the page, beneath the action buttons. This should come from the page wrapper (issue #1), not from per-page tweaks.
