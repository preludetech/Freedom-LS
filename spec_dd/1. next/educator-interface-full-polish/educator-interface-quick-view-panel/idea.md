# Feature: Educator quick-view side panel

When an educator clicks a topic-progress or form-progress block in the cohort course-progress table (e.g. `/educator/cohorts/<uuid>`), open a right-hand "quick view" panel showing details about that cell.

The panel is a reusable component — this is the first consumer, but it is built as a general-purpose mechanism so other parts of the app can adopt it later.

## Behaviour

### Desktop (≥ 768px)

- Non-modal right-hand drawer; ~480px wide, fixed position, internal vertical scroll, sticky panel header.
- Page underneath stays fully interactive — no backdrop, no scroll-lock, no focus trap.
- Trigger: click the cell. The cell's clickable element is a `<button>` (not a div with onclick) and gets a visible "selected" highlight while it is the source of the open panel.
- Dismiss:
  - X button in panel header.
  - `Esc`.
  - Click the same already-active cell (toggle).
  - Click-outside does **not** dismiss — clicks elsewhere on the page (especially other cells) are legitimate.
- Click another cell while open → in-place swap of panel contents (never stack).
- Layout uses CSS logical properties so RTL flips automatically.
- Respects `prefers-reduced-motion`.

### Mobile (< 768px)

- Flip to a true modal: `role="dialog"`, `aria-modal="true"`, `inert` applied to siblings, focus trapped, Esc/X both close.
- Push exactly one history entry on open so the back gesture dismisses; pop on close.
- `inert` must be removed when the user resizes back to desktop or closes the panel.

### Loading

- Open the panel immediately, populated with whatever the cell already knows (student name, topic/form name, status).
- HTMX-fetch the rich detail; render skeletons (one per section) while in flight; `aria-busy="true"` on the panel until loaded.
- Cancel in-flight requests on new cell clicks.
- On error, render an inline error + retry inside the panel — do **not** auto-close.

### Accessibility

- Desktop panel: `role="region"`, `aria-labelledby="quickview-heading"`, polite live region announcing context on open and on swap. **No** `role="dialog"` / `aria-modal` on desktop.
- Mobile panel: `role="dialog"` + `aria-modal="true"` (see above).
- Cell trigger exposes `aria-controls="quickview-panel"` and toggles `aria-expanded` to mark the active cell.
- Focus on open: stays on the cell so educators can keep arrow/Tab-ing through cells; users can `Tab` into the panel. Esc returns focus to the source cell.
- Print: panel is hidden via `@media print`.

## Content shown in the panel

Minimum from the original idea, plus obvious adjacent fields that are already available without new computation/queries:

### Topic progress
- Topic name (header, with breadcrumb to course/module).
- When the student started and finished the topic.
- Time on task if it can be computed from existing progress data.
- Link to open the topic full-page (educator-side view of the student's topic).

### Form progress
- Form name (header).
- One row per attempt with: attempt number, started/submitted timestamps, score (if scored), pass/fail status.
- Latest score / best score summary at the top.
- Link to open the full form attempt detail.

If a "naturally available" field needs new querying or computation, defer it — flag in the spec phase rather than expanding here.

## Out of scope (future enhancements)

- Pin / side-by-side compare of two cells.
- Deep-linking the open panel via URL.
- Live updates (panel re-fetching when underlying data changes).
- Drag-to-resize the panel.

## Reference research

- `research_ux_patterns.md` — survey of Linear, Notion, Asana, Stripe, GitHub, Gmail, etc. and synthesised recommendations.
- `research_ux_pitfalls.md` — accessibility model, keyboard/focus, screen-reader, mobile-flip pitfalls, table-cell trigger specifics.
