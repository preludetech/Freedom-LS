Two issues that share root cause / theme: things rendering when they shouldn't. The picture modal flash is a missing `x-cloak` rule; the empty recommendation/history boxes are sections that should not render at all when their data is empty. Bundled because they live in adjacent territory and the same research file covers both.

Background research lives alongside this file:
- `research_fouc_and_empty_states.md`

Use playwright mcp to take screenshots before/after every visual change so regressions are caught. Verify each change at desktop, tablet, and mobile widths.

## 1. Picture modal flashing open on load

http://127.0.0.1:8000/courses/functionality-demo-show-end-with-quiz/1/ — the `c-picture` zoom modal flashes open for a moment on page load before closing.

**Root cause is already identified** (see `research_fouc_and_empty_states.md` Part A): the `c-picture` template applies `x-cloak` correctly, but there is no global `[x-cloak] { display: none !important; }` rule anywhere in the project. Add the rule inside `@layer base` in `tailwind.input.css` and rebuild Tailwind. While we're there, audit other Alpine components in the project to confirm the same fix resolves any similar flashes.

## 2. Hide empty recommendation / history sections

http://127.0.0.1:8000/ — if there are no recommended courses, don't render that section at all (heading and box). Same for learning history.

Pure hide — no placeholder or empty-state CTA. The section should be entirely absent from the DOM, not just visually hidden, so screen readers don't encounter an empty heading.
