# Research: Quick-view side panel UX patterns

Reference for the educator-interface quick-view panel: an educator clicks a cell in a student-progress table and a non-modal right-hand panel opens with details for that one student/topic intersection. The rest of the page must remain interactive.

This document surveys how mature web products implement the same pattern, then synthesises concrete recommendations for FLS.

## Linear (issue side-peek)

- **Width**: not officially documented; observable behaviour is roughly 40-50% of viewport on wide screens, with the issue list compressing rather than overlaying. The detail content centres and grows proportionally as the window grows ([Linear redesign post](https://linear.app/now/how-we-redesigned-the-linear-ui)).
- **Trigger**: keyboard-only — `Space` toggles peek; hold `Space` for a temporary preview, release to close ([Linear Docs: Peek](https://linear.app/docs/peek)). Cell/row click opens the issue *full-page*, not in peek.
- **Dismiss**: `Space` again, `Esc`, or navigate away.
- **Swap-vs-stack**: in-place swap. While peek is open, `J`/`K` or arrow keys move the selection in the underlying list and the panel content updates immediately. No stacking, no animated transition between items.
- **Modal/non-modal**: non-modal. Underlying list stays interactive (in fact, keyboard navigation drives the swap). No backdrop, no scroll-lock.
- **Mobile**: peek is essentially desktop-only; on small viewports Linear pushes you to the full-page issue view.
- **URL**: peek state is *not* reflected in the URL. Opening the issue in full view does change the URL.
- **Header**: minimal — issue identifier (`ENG-123`), status pill, breadcrumb to project, and an "open full issue" affordance. No explicit X.
- **Loading**: skeleton placeholders for description and metadata; the existing list does not block.

## Notion (database row side-peek)

- **Width**: side-peek splits the screen ~50/50 by default; user-resizable via drag handle. "Center peek" is a centred modal at ~720px; "open full page" replaces the view entirely ([Notion releases: database side peek](https://www.notion.com/releases/2022-07-20), [makeuseof guide](https://www.makeuseof.com/change-notion-side-peek-setting/)).
- **Trigger**: click the row's open-icon, or `Cmd/Ctrl+click`. Default open-mode is configurable per view ("Open pages as: side peek / center peek / full page").
- **Dismiss**: X button top-right of the panel, `Esc`, or click outside the panel onto the underlying database.
- **Swap-vs-stack**: in-place swap. Clicking another row while side-peek is open replaces the panel contents; no stacking. Center-peek likewise replaces. Sub-page navigation inside the peek does *not* stack — it pushes within the peek with a back arrow.
- **Modal/non-modal**: side-peek is non-modal — the database table behind it is fully interactive (you can click another row to swap). Center-peek is modal-ish (dimmed backdrop). This confirms non-modal peek is a real mainstream pattern.
- **Mobile**: side-peek collapses to a full-screen takeover; back-arrow in the header returns to the table. Browser back also dismisses.
- **URL**: yes — both side-peek and center-peek update the URL with the page ID, so the peek is shareable / refresh-survivable. Trade-off: deep-linking works, but introduces history entries that can clutter the back-button stack.
- **Header**: breadcrumb + page title, share/comment/options icons on the right, back arrow if drilled in, X to close.
- **Loading**: shows the page title from the row immediately, body content streams in with a content skeleton.

## GitHub (PR review side panel & file tree)

- **Width**: the new docked panels for Files-changed (overview, comments, merge status, alerts) sit in a resizable column. The file tree hides automatically below ~1000-1200px width depending on whether the diff is split or unified ([GitHub Changelog: Files Changed v2](https://github.blog/changelog/2025-06-26-improved-pull-request-files-changed-experience-now-in-public-preview/), [community discussion](https://github.com/orgs/community/discussions/12341)).
- **Trigger**: click panel toggle in toolbar; tree-item click navigates within the diff area (not a peek per se). Conversation/threads open inline in the diff, not in a side panel.
- **Dismiss**: panel toggle button; persists across navigations within the PR.
- **Swap-vs-stack**: GitHub favours in-place updates (the docked panels filter/scroll their existing content rather than swapping). No stacking model.
- **Modal/non-modal**: strictly non-modal; the diff stays scrollable and clickable while the panel is open.
- **Mobile**: docked panels are hidden; tree collapses; you get a single-column stack.
- **URL**: file selection in the tree updates the URL hash (`#diff-...`); panel-open state itself is not persisted to URL but is remembered per-user as a preference.
- **Header**: panel-specific tab strip (Overview / Conversation / Checks); no close X — the toggle button in the main toolbar is the dismissal affordance.
- **Loading**: tabs render skeleton rows; no full-page block.

Useful as a counterexample: GitHub's pattern is closer to a *persistent dock* than a *peek*. Worth borrowing the resizable-column idea but not the persistence.

## Asana (task detail panel)

- **Width**: opens as a right-side panel that compresses the task list to its left rather than overlaying. Approx 40-55% of viewport on desktop; user complaints in the forum centre on the panel hiding the project/due-date columns at narrow widths ([Asana forum](https://forum.asana.com/t/see-project-and-due-date-columns-when-clicking-on-a-specific-task-to-see-details-in-the-right-side-panel-in-my-tasks/103657)).
- **Trigger**: click anywhere on the task row.
- **Dismiss**: X (top-right of panel), `Esc`, or arrow/collapse button on the panel edge that toggles it without losing context.
- **Swap-vs-stack**: in-place swap. Clicking another row replaces the panel content. Sub-tasks open *inside* the same panel via a back-button breadcrumb (no stacking).
- **Modal/non-modal**: non-modal — the task list to the left remains fully interactive (you can click other tasks, drag-and-drop, etc.).
- **Mobile**: full-screen takeover; native back gesture returns to the list.
- **URL**: yes — Asana puts task ID in the URL when the panel opens (deep-linkable). Trade-off as per Notion.
- **Header**: project breadcrumb, complete-task checkbox, share/copy-link icons, overflow menu, X.
- **Loading**: fields render with skeleton lines; the comments thread shows a spinner at the bottom while it streams.

## ClickUp (task slide-out)

- **Width**: right sidebar, fixed-ish width covering ~30-40% of viewport. Users have repeatedly requested a quick collapse-and-restore arrow — the current implementation makes referencing right-side columns awkward ([ClickUp feedback](https://feedback.clickup.com/feature-requests/p/allow-viewing-task-as-a-side-window-while-browsing-other-tasks-not-as-a-pop-up)).
- **Trigger**: click task; "Sidebar view" must be selected from the layout chooser (alternatives: modal, full-page).
- **Dismiss**: X, `Esc`, or switch layouts.
- **Swap-vs-stack**: in-place swap.
- **Modal/non-modal**: non-modal split-screen — explicitly described as "covers part of the UI as if an overlay, but the rest stays interactive" ([ClickUp Help: Task layouts](https://help.clickup.com/hc/en-us/articles/29665520762647-Task-layouts)).
- **Mobile**: full-screen modal.
- **URL**: yes, deep-linkable.
- **Header**: task path breadcrumb, status chip, assignees, action icons, X.
- **Loading**: skeleton.

## Airtable (expanded record)

- **Width**: default *centered* peek (modal-ish, ~960px), not a right drawer. Newer "side sheet" in Interface Designer is a right-side drawer at ~480-560px ([Airtable Community: side sheet changes](https://community.airtable.com/interface-designer-12/changes-to-sidesheet-behavior-38669)).
- **Trigger**: click row + `Space`, or click the expand-arrow that appears on hover ([Airtable grid view docs](https://support.airtable.com/docs/airtable-grid-view)).
- **Dismiss**: `Esc`, X, click outside.
- **Swap-vs-stack**: in-place swap; arrow keys cycle records while expanded.
- **Modal/non-modal**: the centred default *is* modal (dimmed backdrop). The Interface Designer side-sheet is non-modal. Mixed signals from this product, useful as a "don't dim if you want continued interaction" reference.
- **Mobile**: full-screen.
- **URL**: yes, record ID in URL.
- **Header**: record-name title, expand-to-fullpage button, prev/next arrows, X.
- **Loading**: fields render synchronously from cached row data; attachments lazy-load.

## Stripe Dashboard (resource detail drawer)

- **Width**: right drawer roughly 480-640px on payment/customer details. For Stripe Apps, the SDK formalises two viewports: `ContextView` (non-blocking drawer) and `FocusView` (modal with backdrop) ([Stripe Apps viewports](https://stripe.com/docs/stripe-apps/reference/viewports), [design docs](https://docs.stripe.com/stripe-apps/design)).
- **Trigger**: click row in a list (payments, customers, subscriptions).
- **Dismiss**: X, `Esc`, click outside.
- **Swap-vs-stack**: in-place swap; some flows push a secondary drawer (e.g. refund inside payment), creating a shallow stack of max 2.
- **Modal/non-modal**: explicitly *non-modal* for `ContextView`; explicitly modal for `FocusView` — Stripe's docs are unusually clear about the distinction. This is the strongest evidence that "non-modal peek" is a deliberate, documented mainstream pattern.
- **Mobile**: full-screen takeover.
- **URL**: yes, deep-linkable resource ID.
- **Header**: resource title + ID, copy-ID button, action buttons (Refund, etc.), overflow, X.
- **Loading**: skeleton blocks for each section; non-blocking.

## Gmail (reading pane)

- **Width**: vertical-split puts the preview on the right; user-resizable divider; default ~50/50 ([Gmail preview pane help](https://support.google.com/mail/answer/9499937?hl=en-GB)).
- **Trigger**: click email row; a single click selects, second click or hover behaviour can be configured.
- **Dismiss**: no explicit close — selecting the inbox icon clears, or selecting a different message swaps.
- **Swap-vs-stack**: pure in-place swap. Never stacks.
- **Modal/non-modal**: non-modal; it's a persistent split, not a peek. The list is always interactive.
- **Mobile**: not available on mobile web/apps — full-page mail view only.
- **URL**: the message thread updates the URL.
- **Header**: sender, subject, action icons (archive/delete/etc.), no X.
- **Loading**: usually instant from cache; large attachments lazy-load.

Closer to a "persistent reading pane" than a peek. Useful for the swap-in-place model and the resize-handle affordance.

## Synthesis & recommendations for FLS

### Confirmation: non-modal peek is mainstream

Linear, Notion (side-peek), Asana, ClickUp, Stripe (`ContextView`), and Gmail all ship a non-modal right-hand panel that leaves the underlying page fully interactive. Stripe's docs are the cleanest articulation: a non-blocking drawer for *context*, a modal `FocusView` only for blocking workflows. FLS's "click cell to peek progress detail" is squarely a context use case.

How they achieve non-modal:
- No backdrop / no `aria-modal="true"`.
- No scroll-lock on the body.
- No focus trap (focus moves into the panel on open, but `Tab` can leave it).
- Pointer events on the underlying table stay enabled — clicking another cell swaps content.

### Recommended panel width

- Desktop default: **480px fixed** width (sits between Stripe ~480-640 and Asana ~40-55%; narrow enough to keep the progress table readable, wide enough for charts and topic detail).
- Allow content to dictate height; panel scrolls internally.
- Optional v2: drag-to-resize handle (Notion / Gmail / GitHub) capped at 720px.
- Below `1024px` viewport width, switch to overlay mode (panel sits on top with a subtle backdrop *but no dim*) so the table doesn't get crushed.

### Trigger and dismiss

- Trigger: click anywhere on a cell.
- Dismiss, in priority order:
  - X button in panel header (always present, top-right).
  - `Esc` key.
  - Click outside the panel (anywhere on the page that isn't another cell).
  - Clicking another cell *swaps* rather than dismisses (see below).

### Swap-vs-stack

Universal across references: **in-place swap, never stack.** Clicking a different cell while the panel is open replaces the panel contents.
- Visual treatment: brief content fade/skeleton (~150ms) — enough to signal change without animating the panel itself moving.
- Keep the panel's open/closed state stable; only the inner content swaps.
- If the user clicks the same cell twice, dismiss (toggle behaviour).

### Mobile (full-screen takeover)

- Breakpoint: switch to full-screen at viewport width `< 768px` (matches Tailwind `md`, aligns with Notion/Asana/Stripe behaviour).
- Use the `<dialog>` element or equivalent to take over the viewport.
- Browser back button must dismiss (push a history entry on open *only* on mobile, pop it on close). This is the one place where touching history is worth it — users on phones expect the back gesture to work.
- Header on mobile: back arrow (left) + title + X (right) — Asana/Notion style.

### URL state

Decision: **do not** put open-state in the URL (per spec — ephemeral peek).

What we lose vs. what Notion/Asana/Stripe/ClickUp do:
- No deep-linking ("send me the URL of this student-topic peek"). For an educator workflow this is a low-value capability — they'd usually share the table view, not a single cell.
- No refresh-survival. Acceptable for an ephemeral peek.
- No back-button dismiss on desktop. Acceptable; `Esc` and X cover it.

What we gain:
- No history-stack pollution; cleaner navigation.
- No need to handle deep-link entry (initial-render-with-panel-open) state.
- Simpler implementation: pure HTMX swap into a target div.

Caveat: on mobile, push *one* history entry on open so the back-gesture dismisses (see above). This is local state, not a shareable deep link.

### Header pattern

- Left: short title — `Student name` -> `Topic name` (truncated with tooltip if long).
- Right: secondary-action icons (e.g. "open student profile", "open topic") followed by `X` close.
- No back arrow on desktop; back arrow appears only on mobile full-screen.
- Sticky header so it stays visible while panel content scrolls.

### Loading state (HTMX async fetch)

- Open the panel *immediately* with the cell's already-known data (student name, topic name, current score) populated synchronously — no waiting for round trip.
- Use `hx-trigger` on panel open to fetch the rich detail (history, attempts, time-on-task).
- Render skeleton blocks (Linear/Stripe pattern) for each section, not a single spinner.
- Keep the table behind it interactive throughout — never block for the fetch.

### Accessibility

- `role="complementary"` (not `role="dialog"`) and **no** `aria-modal` — confirmed correct for non-modal drawers ([WAI-ARIA discussion](https://github.com/primefaces/primevue/issues/7943)).
- `aria-labelledby` pointing at the panel header.
- Focus moves to the panel header on open; `Esc` returns focus to the originating cell.
- Do *not* trap focus — `Tab` should exit the panel back into the table.
- Close button needs an accessible name (`aria-label="Close panel"`).

### Quick decision summary

| Decision | Choice |
|---|---|
| Width (desktop) | 480px fixed |
| Width (mobile) | full-screen at `<768px` |
| Trigger | cell click |
| Dismiss | X, `Esc`, click-outside |
| Swap behaviour | in-place swap on cell-click; toggle on same-cell |
| Backdrop / dim | none |
| Scroll-lock | none |
| Focus trap | none |
| URL state | no (mobile pushes one local history entry only) |
| Header | title left, actions+X right; mobile adds back arrow |
| Loading | seed sync data, skeletons for async sections |
| ARIA role | `complementary`, no `aria-modal` |

## References

- [Linear — Peek docs](https://linear.app/docs/peek)
- [Linear — How we redesigned the UI (Part II)](https://linear.app/now/how-we-redesigned-the-linear-ui)
- [Linear — Issue view layout changelog](https://linear.app/changelog/2021-06-03-issue-view-layout)
- [Notion — Database side peek release notes](https://www.notion.com/releases/2022-07-20)
- [Notion — Layouts help](https://www.notion.com/help/layouts)
- [How to change Notion's side peek setting (MakeUseOf)](https://www.makeuseof.com/change-notion-side-peek-setting/)
- [GitHub — Improved Files Changed page (changelog)](https://github.blog/changelog/2025-06-26-improved-pull-request-files-changed-experience-now-in-public-preview/)
- [GitHub — File tree feedback discussion](https://github.com/orgs/community/discussions/12341)
- [GitHub — Side-by-side code and comments changelog](https://github.blog/changelog/2026-03-19-view-code-and-comments-side-by-side-in-pull-request-files-changed-page/)
- [Asana forum — Right-panel detail UX feedback](https://forum.asana.com/t/see-project-and-due-date-columns-when-clicking-on-a-specific-task-to-see-details-in-the-right-side-panel-in-my-tasks/103657)
- [ClickUp — Task layouts help](https://help.clickup.com/hc/en-us/articles/29665520762647-Task-layouts)
- [ClickUp — Sidebar task feature request](https://feedback.clickup.com/feature-requests/p/allow-viewing-task-as-a-side-window-while-browsing-other-tasks-not-as-a-pop-up)
- [Airtable — Grid view (expand record)](https://support.airtable.com/docs/airtable-grid-view)
- [Airtable — Side sheet behaviour discussion](https://community.airtable.com/interface-designer-12/changes-to-sidesheet-behavior-38669)
- [Stripe Apps — Viewports reference (ContextView vs FocusView)](https://stripe.com/docs/stripe-apps/reference/viewports)
- [Stripe Apps — Design your app](https://docs.stripe.com/stripe-apps/design)
- [Gmail — Preview your emails (reading pane help)](https://support.google.com/mail/answer/9499937?hl=en-GB)
- [Building a side drawer with the dialog element](https://pixari.dev/building-a-side-drawer-with-web-standards-using-the-dialog-element/)
- [PrimeVue issue: role="complementary" vs aria-modal](https://github.com/primefaces/primevue/issues/7943)
- [Nielsen Norman — Breakpoints in responsive design](https://www.nngroup.com/articles/breakpoints-in-responsive-design/)
