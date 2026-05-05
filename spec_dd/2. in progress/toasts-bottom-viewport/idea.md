Move Django messages out of the top-of-page heading area and turn them into proper toasts.

Background research lives alongside this file:
- `research_toasts.md`

Use playwright mcp to take screenshots before/after every visual change so regressions are caught. Verify each change at desktop, tablet, and mobile widths.

## Django messages — move to bottom of viewport

Currently Django messages render center-top, overlapping the page heading. Move them out of the heading area.

- Desktop: bottom-right corner, stacked.
- Mobile: full-width along the bottom edge (avoids thumb-zone / iOS home-indicator collisions). Use `env(safe-area-inset-bottom)` for the offset.
- Errors are persistent — they stay until the user dismisses them. Success / info / warning auto-dismiss (success/info ~5s, warning ~7s).
- Pause auto-dismiss on hover and on window blur.
- Pre-render two ARIA live regions in the base layout: one polite (`role="status"`) for success/info, one assertive (`role="alert"`) for errors. Toasts get appended into the appropriate region so screen readers announce them correctly.
- Animate via `transform` + `opacity` only; respect `prefers-reduced-motion`.
- Pick a single HTMX delivery mechanism (OOB swap *or* `HX-Trigger` header) and stick with it — mixing causes duplicate announcements.
