# Research: UX patterns for an educator admin consistency pass

Scope: spec 12 (docs and polish). Patterns for naming, confirmations, empty states, badges, 390px tables, dark mode and focus, tied to what the project already says. Web claims were fetched; items marked "(not fetched)" are from background knowledge.

## What the project already settles (use it, do not re-research)

- **Verbs** (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, "Changes" section): buttons and dialogs use Deactivate, Reactivate, Remove, Delete, Register, Assign. The state of an `is_active=False` row is **Inactive**, never Removed, Suspended or Deactivated. "Remove" and "Delete" are only for rows actually deleted (`CohortMembership`, `Cohort`). List entries (`JobTitle`, `Department`, `Location`) are **retired**. "Unregister" is explicitly banned. A registration that exists reads "Registered"; a switched-off one reads "Registration deactivated". Audit labels are in `freedom_ls/audit_log/README.md`.
- **Badges** (`.claude/skills/brand-guidelines/visual.md`, lines 73-76): `<c-panel-status-badge tone="success|warning|error|info|muted" label="...">` for the state of a record; `<c-chip>` for tags, levels, categories. Destructive buttons use `variant="error"`, "reserved for irreversible actions". Status text on pale tint uses the `-light` pair (Sand and Forest fail contrast as text). Themes repoint tokens, so dark mode parity means no raw colours, only role tokens.
- **Modal and drawer mechanics** (`spec_dd/1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md`): native `<dialog>` with `showModal()`, initial focus on Cancel for destructive confirmations, on first field for forms, on a `tabindex="-1"` heading for long content; 422 re-render moves focus to the error summary or first `aria-invalid` field; on close, return focus to the invoker, falling back to a stable anchor (the table heading) if a refresh replaced it. The drawer on desktop is not a focus trap; it flips to modal on mobile. Known gap in the old `cotton/modal.html`: no focus move, no trap, no focus return. The polish pass should verify this was closed, not assume it.
- Mockups live in `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/` (Dashboard, Learners, Cohorts and Admin, each with a Mobile variant, plus Sidebar). There are no mockups for courses, members, history or reports, so those are checked against the sibling screens for density and pattern, not against a mockup. The idea file says fidelity by eye is fine.

## Patterns and recommendations

### 1. Destructive vs reversible naming
- Reversible (flag flip) gets the **plain verb with no ceremony**: Deactivate and Reactivate. Deleting a row gets Remove or Delete plus a confirmation. This matches the glossary and keeps the cost of confirmation proportional.
- Label the button with the specific action, sentence case, and put the object in the label when the surface is ambiguous (GOV.UK: "describe the specific action the button performs"; sentence case). Source: https://design-system.service.gov.uk/components/button/
- Do not rely on red alone: wording must make the effect clear (GOV.UK, same page). Warning/error buttons "should be rare", with a different button style for the first call to action and the warning style only on the final confirmation.
- Consistency-pass audit method: grep templates, view messages, toasts, `aria-label`s, docs and tests for `unregister`, `suspend`, `revoke`, `Removed` (as a state), `Deactivated` (as a state). Row action menu, bulk action bar, confirmation title, confirmation button, success message and audit label must all use the same verb.

### 2. Confirmation dialog anatomy
- Use confirmation only when consequences are serious and hard to undo; routine use trains click-through, and undo is preferable where possible. Restate the request, name the affected items with counts, state the outcome; avoid "Are you sure?"; replace Yes/No with outcome verbs; require typing only for the rarest, most dangerous actions or it loses its force. Source: https://www.nngroup.com/articles/confirmation-dialog/
- Suggested shape for FLS (a recommendation, tied to the above):
  1. Title as a question naming the object: "Deactivate Thandi Nkosi?" / "Remove 12 learners from Cohort A?"
  2. One or two lines of consequence, in domain words: what stops, what is kept ("keeps their registrations, memberships and progress", per the glossary: nothing cascades), and whether it can be reversed and how.
  3. Buttons: a verb-labelled confirm ("Deactivate learner") and "Cancel". Error variant only for the irreversible ones (Delete, Remove).
  4. Initial focus on Cancel for destructive ones (W3C APG: focus the least destructive action). Source: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
  5. Typing the name: probably only for deleting a cohort with members or a bulk action over a large count. Flag as an open decision; do not add it for deactivate/reactivate, which are reversible.
- Bulk actions: the title carries the count, the body lists or summarises the first few names, and the result message reports counts of done and skipped.

### 3. Empty states
- Two kinds, and they must not share copy. **First use** (no data exist): say what will appear and how to add it; positive title ("Start by adding a cohort"); one primary action. **No results** (after search or filter): give the reason and a next step (clear filters, change terms); skip extra text if there is no next step. Replace the empty table so a screen reader does not read bare headers; decorative illustrations get empty `alt`. Source: https://carbondesignsystem.com/patterns/empty-states-pattern/
- For FLS: each list screen needs both variants, and the filter variant must keep the filter controls visible and offer "Clear filters". History/audit log and reports often legitimately start empty, so their first-use copy is informational, with no action button when the educator cannot create the thing. Dashboard widgets need an empty state per widget.
- Role-based variant to check: an educator with no visible learners (scope) differs from a site with none; the first-use call to action should not show for someone without permission.

### 4. Status badge vocabulary and colour
- Semantic colour only for shared meanings (success, warning, error, info); neutral for the rest; colour never alone, always a label; sentence case; short labels; badges are not focusable, so truncated text cannot be read, so avoid truncation. Source: https://atlassian.design/components/lozenge/usage
- Proposed FLS mapping to verify, using existing tones:
  - Active / Registered / Complete: `success`
  - Inactive / Registration deactivated: `muted` (not `error`; it is a reversible state, not a failure)
  - Stalled / Missed deadline: `warning` or `error` (glossary says learner copy says "Missed deadline", never "Overdue"; check the educator side agrees, since `is_overdue` is the code name only)
  - Draft / Pending: `info` or `muted`
  - Tags, levels, categories: `c-chip`, not a status badge.
- Same word, same tone, on every screen (learners table, quick view, cohort members, history). Make a one-table vocabulary (state, label, tone) in the product doc and test the badge component against it.

### 5. Responsive tables at 390px
- Options: horizontal scroll inside a labelled, focusable scroll container with sticky first column; or reflow rows to stacked cards with per-cell labels; or hide low-priority columns. Recommendation: scroll container with sticky identity column for wide matrix-like tables (the learners/progress table), stacked rows for simple lists. The mobile mockups (Learners, Dashboard, Cohorts and Admin) show what the design chose; check them first. (Not fetched: Adrian Roselli, "Under-Engineered Responsive Tables", and the WCAG 1.4.10 reflow exception for data tables.)
- Check at 390px: no page-level horizontal scroll, touch targets at least 44px (WCAG 2.5.5 AAA / 24px 2.5.8 AA minimum), row actions reachable without hover, bulk-action bar not covering the last row, pagination wraps, and the quick view becomes a full-height modal.
- Do not break table semantics with `display:block` unless the roles are restored.

### 6. Dark mode parity
- Check by role token: any hard-coded `bg-white`, `text-gray-*`, hex values or `-light` pair used without its dark counterpart is a defect. Status text on tint must keep contrast in both themes. Check focus ring, disabled state, table zebra/hover, dialog backdrop, charts/progress bars, and the badge in forced-colours mode (the status badge already handles that).
- Method: the same 7 sections x 2 widths x 2 themes grid the idea already specifies (28 screenshots); take them from the `do_qa` flow and compare pairs.

### 7. Focus management: drawer and modal
- Modal: focus moves in on open; Tab trapped; Esc closes; focus returns to the invoker, or a sensible target if it no longer exists; for long content focus a static `tabindex="-1"` heading. Source: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- Drawer (quick view): non-modal on desktop (focus stays in the table for rapid browsing, per the earlier research), modal on mobile. Test list: open from keyboard (Enter on a row cell), Esc closes and focus returns to the same cell, a swap to another learner does not steal focus, a live-region announcement names the loaded learner, and the page behind is inert in modal mode.
- Screen reader pass (NVDA/VoiceOver) through quick view, modal and tables: dialog has an accessible name (heading id wired to `aria-labelledby`), table has a caption or label, sortable headers expose `aria-sort`, bulk-select checkboxes have per-row labels ("Select Thandi Nkosi"), badge text is read, and success/error messages are in a polite live region.

## Suggested checklist items for the spec (derived)
1. A terminology grep list and a single verb/state/tone table.
2. One shared confirmation component or template shape; all destructive actions go through it.
3. Two empty-state variants per list, with a test for each.
4. Keyboard script per section (Tab order, Enter/Esc, focus return) and a short deliberate-leftovers list.
5. 390 and 1440, default and dark grid; mockup comparison by eye for the three mocked sections only.

## Sources
- https://design-system.service.gov.uk/components/button/
- https://www.nngroup.com/articles/confirmation-dialog/
- https://atlassian.design/components/lozenge/usage
- https://carbondesignsystem.com/patterns/empty-states-pattern/
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- Project: `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, `.claude/skills/brand-guidelines/visual.md`, `spec_dd/1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md`, mockups folder `Educator LMS Interface Design/`

status: ok
