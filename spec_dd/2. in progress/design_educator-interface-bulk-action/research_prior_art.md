# Research: prior art for the bulk-action bar restyle

Question: what has already been tried, here or elsewhere, and what happened?

## Findings first

1. **The bar has been built and QA'd; this is a restyle, not a first build.** Spec 2 built the seam (`BulkAction`, `Selection`, `tableSelection`, the bar). Spec 8 (`educator-interface-8-bulk-operations`) built the real actions, "Select all N matching", the confirmation/result modal and the background run. Spec 12 polished the dialogs and the bar's phone behaviour. No earlier attempt at the design's bar layout was found, and no abandoned attempt.
2. **The behaviour is settled and the idea does not ask to change it.** The design draws three states (02b bar, 02c confirm, 02d result). All three already exist as behaviour. The restyle must keep every contract in "Do not reopen" below.
3. **Several idea bullets overlap what exists, and some differ.** The idea asks the bar to appear "above the table", to hold Clear on the right, and to be text-only buttons. Today the bar is in the table footer row beside the pagination (desktop) and fixed to the bottom below `lg`. See "Where the idea departs from what was built".
4. **Open QA items from spec 12 touch the same surface** and were left unresolved (todo lines 46, 49 and the B10 band). The restyle will probably hit them.

## Here: what was built

### Spec 2 (`3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/`)
- `1. spec.md` "Row selection and bulk actions": `BulkAction` plain class (`label`, `action_name`, `max_rows = 500`, `confirm_template_name`, `has_permission`, `execute`). The whole table sits in one `<form method="post">`; rows post `keys`; each action is a submit button whose `formaction` is the action URL plus the table query string. Selection is never in the URL and clears on any table swap.
- `research_row_selection_bulk_actions.md`:
  - The desktop mockup then (`Educator Learners.dc.html` screen 02) drew no bulk toolbar. Spec 2 designed the bar itself and put it "pinned to the bottom of the table ... beside pagination". A "sticky-top bar as a desktop table grows tall is a later refinement, not spec 2's default" (line 255-257). **The design now asks for exactly that refinement (a bar above the table).**
  - Header checkbox is native, page-scoped, with `indeterminate`, `aria-label="Select all on this page"`, never silently "everything".
  - The count sits in a polite live region (`aria-live="polite"`, not assertive), as a full sentence.
  - Mobile: always-visible card checkboxes; the bar replaces the bottom tab bar. Long-press selection and cross-page persistent selection were rejected.
  - The confirm step is a modal with JS; a real confirmation page with JS off. Known external bug quoted there: several toolbars on a page sharing `select_across` (Django ticket #33083). So one bar per table.
  - The htmx pitfall: keep checked state across table swaps (commonest bug in HTMX bulk UIs). Spec 2 solved it by clearing selection on swap, deliberately.

### Spec 8 (`3. done/2026-11-01_14:50_educator-interface-8-bulk-operations/`, `1. spec.md` R1, R2, R7)
- **Select all matching.** Bar prompt "All 25 on this page are selected." with a button "Select all 312 matching"; then "All 312 matching are selected." with "Clear selection". Unticking in this mode adds to `excluded`. A table swap clears the selection in both modes. The header checkbox stays "this page". The count sits in a `role="status"` region present before it changes (R2.2-R2.4).
- **Where confirmation happens.** Bulk confirmation is a modal over htmx (`#app-modal-body`), a confirmation page with JS off. The first POST renders the confirmation; `refresh=1` re-renders it when a target picker changes; the confirmed POST carries `expected_count` (a mismatch is 422, "The selection changed since you opened this."); a confirmed inline run returns the result summary in the same modal with `refresh_events` in `HX-Trigger`, so the table refreshes behind it and Close only closes.
- **Pickers in the confirmation.** Bulk actions that need a target (cohort, course) render the form above the confirmation sentence inside the modal. This is the "user-facing forms related to actions" the idea mentions.
- **Imperative sentences.** "Add 12 learners to Accra January. 3 are already in the cohort and will be skipped." Result in the past tense, one sentence per skip reason. When nothing would change, Confirm is disabled and the reason is stated.
- **Bar contents.** The bar renders the first two permitted actions (registration order) as buttons and the rest under "More actions". Learners: Add to cohort and Remove from cohort, then More. Cohorts: Register for a course and Unregister (later renamed), then More. Destructive actions use the destructive variant; initial focus lands on Cancel.
- **Background runs.** Above `BULK_BACKGROUND_THRESHOLD` (250) the confirm POST answers 204 with `closeModal` and `bulkRunStarted`. The `tableSelection` component keeps the run in an Alpine store keyed by region (survives table refreshes). While it runs, the bulk buttons and More actions are disabled, the starting button shows a spinner, every row checkbox is disabled, and the bar reads "<Label> is running…". The store polls `status_url` every 2 s into `#app-modal-body`, skipping while a modal is open or the tab is hidden. The requester also gets a `bulk_action.finished` in-app notification.
- **JS off.** Confirmed POST ends with a 303 to the table plus a flash. Decision recorded in the spec 8 todo: kept the redirect + flash from commit 10dc8f328 so Back and refresh cannot re-run the action; the spec, QA plan and Playwright test were updated (QA B1, resolved).
- **Always-rendered live region.** QA 6.2 checked the status region is empty before ticking and then reads "2 selected · showing 1–9 of 9 learners".

### Spec 8 QA (`qa_report.md`, `todo.md`) and user decisions captured
- Wording: every bulk sentence became imperative; access and impact sentences moved to consequence lines. Result lines became past-tense sentences (`'2 were already in the cohort.'`).
- The user asked: "the bar stays fixed until the sidebar docks at lg" (fixed to the bottom below `lg`, table padded so it covers no row). The fixed bar was a QA fix, not original design.
- Course action labels: "Register for a course" / "Unregister from a course", the single-learner action included.
- JS-off picker confirm: `noscript` "Show what changes" button re-posts with `refresh=1` and enables Confirm. Passed; a QA-procedure miss.
- Minor, unresolved at close: JS-off bar text reads " selected · showing …" with no count; at 375px the running-state bar is about 335px tall (about 40% of the viewport); the resend confirmation cannot predict the recent-send skip.

### Spec 12 (`3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/`)
- **Button weight (decision).** In a confirm dialog a reversible action (deactivate, reactivate, register, move, resend) confirms with `primary`; an action that deletes a row (remove from cohort) confirms with `error`. Trigger buttons in row menus and the selection bar use `secondary` for reversible actions and `error` for deleting ones. The framework gained `confirm_variant` and `loading_text` on the bulk action base; `variant` still drives the bar trigger. **The idea's "text-only buttons, no outline" collides with this decision for the bar triggers.** See below.
- **Confirmation shape (decision).** Title is a question naming the object and, for bulk, the count ("Remove 12 learners from Cohort A?"); the body says what stops, what is kept, how to undo; footer `<c-button-group variant="right">` (later `<c-modal-footer>`: Cancel left, actions right); Cancel has `autofocus`; `loading_text` is "-ing…".
- **Renamed bulk actions.** "Unregister" became `DeactivateRegistrationBulkAction` ("Deactivate a course registration"), per the glossary (`is_active` flip).
- **Defects touching the bar:** "Selection bar about 335px tall at 375 while a run is in progress → Bar stays compact; progress detail collapses"; QA B1 "More actions" menu closed itself on the first click (fixed in 57ebf7c88); B10 160px empty band under tables at tablet width when nothing is selected (UNRESOLVED, because room for the fixed bar is reserved even with no selection); a scroll-padding rule clears the sticky header and the bar.
- **Unresolved QA items at that spec's close** (`todo.md`, unchecked): line 46 "phone selection bar uses full-size stacked buttons and a text Previous/Next pager instead of small and icon-only"; line 49 "bulk confirmation bodies repeat the title and omit what changes, what is kept and how to undo". Both are inside this restyle's reach. The skill (`SKILL.md` below) now states the rules, so treat the rules as binding even where the code lags.
- Screen-reader pass included one confirmation dialog and the learners table; the checklist file `screen_reader_checklist.md` covers it. A stale-tab bulk action shows "already changed. Nothing changed…" (3-repeat) and a bulk action whose selection became inaccessible shows "This is no longer available".

### Rules captured in the panel-framework skill (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`)
- Selection bar (lines 124-127): fixed to the bottom below `lg`, every control inside the viewport at 375px; the list reserves its height while fixed.
- Dialogs, sheets (107-122): a dialog ends in `<c-modal-footer>`, Cancel at the left, the primary last. A confirm dialog states what is true now and what changes. `#app-modal` is the modal (dims and blocks); `#quick-view` is never modal. Every sheet and dialog shares one chrome (bottom-sheet on a phone, header with close control).
- Triggers: every framework action trigger outside a dialog footer is the small size and all on a page one size; on a phone a button is 44px tall and as wide as its label (lines 47-48, 146-147, 164). The selection bar is named there as a place small triggers live.
- Dropdown: a filter dropdown is a `<details>`; the bar's More menu uses `<c-dropdown-menu>` with `trigger_class="btn btn-secondary btn-sm"`.
- "A dialog, sheet, table or selection bar stays inside the viewport at every width."
- Invariants file: `freedom_ls/panel_framework/tests/invariants/test_templates.py` (e.g. `test_every_framework_action_trigger_is_small`, `test_no_control_link_is_hand_styled`, `test_every_dialog_ends_in_the_modal_footer_not_a_button_group`). Run after any template change.

### Current implementation (read, not spec)
`freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html`: one flex row = entry count, a `role="status"` span (running text, "N selected · showing a–b of c"), the page prompt and matching prompt, a `fieldset` with the first two buttons (`c-button`, `variant` from the action, `size="small"`, `hx-post` into `#app-modal-body`), a `c-dropdown-menu` "More actions" (noscript fallback to plain submit buttons), and the pagination in the same row.

### Docs
`docs/product/educator-interface.md` "Bulk actions" (line 82-93): "Tick rows ... and an action bar appears. When every row on the page is ticked and the filter matches more, Select all N matching extends the selection ... Changing page, sort or filters clears the selection." Background runs and notification are described. The product doc must be updated if the layout wording changes ("action bar" is vague enough to survive).

## Where the idea departs from what was built

| Idea bullet | Today | Note |
|---|---|---|
| Bar above the table on selection | Footer row beside pagination; fixed bottom below `lg` | Spec 2 deferred a top bar as "a later refinement". The design (02b) says the selection bar replaces the filter bar. The idea says "above the table". |
| Count of items | "N selected · showing a–b of c" | Exists. |
| Select all / de-select all | Header checkbox (page); prompt "Select all N matching" (all matching); "Clear selection" in matching mode | "Select all" already means page vs matching. Two meanings of "select all" is the known Gmail/Polaris ambiguity (below). Do not make the header checkbox mean everything. |
| Clear button on the right | None; clearing is "Clear selection" only in matching mode, otherwise untick | New control. Selection is client-only Alpine state, so no server contract changes. |
| Text-only buttons, no outline | `c-button` `secondary` (outlined) / `error` | Conflicts with spec 12's button-weight decision for bar triggers; the destructive cue (`error`) must survive without the outline, and the invariant tests check triggers are small. |
| More is a dropdown | Already `c-dropdown-menu` "More actions" | Exists; QA B1 fixed. |
| Modal for confirmation and forms | Already `#app-modal` | Exists. Settled; do not move to a sheet. |

## Do not reopen (settled, tested, documented)

- Confirmation is a modal over htmx and a confirmation page with JS off. Result is shown in the same modal. Not a sheet; not an inline bar confirmation. Sheets are for filter/sort and phone chrome.
- The `BulkAction` contract: `classify_all` / `apply` / `BulkOutcome` / `BulkResult`, `expected_count` 422, `refresh=1`, `max_rows`, threshold 250, `__runs/<uuid>` status route, `bulkRunStarted` event, notification on finish.
- "Select all N matching" semantics and the `excluded` list; header checkbox is page-scoped; selection clears on any table swap and is never in the URL.
- Imperative confirmation sentences; skip reasons; Confirm disabled with a reason when nothing would change; Cancel autofocus; JS-off 303 redirect plus flash (decided in spec 8, commit 10dc8f328).
- Which actions exist, their permission gating (single action's capability, not `bulk_manage_learners`), and button weight in the dialog (reversible `primary`, deleting `error`).
- First two permitted actions as buttons, the rest under More actions (spec 8 R7), unless the spec chooses otherwise explicitly; "More" naming is a copy decision (today "More actions").
- Always-present live region before text changes; running state disables controls and shows a spinner; the bar must fit 375px.
- JS-off path must keep working (real form, `noscript` fallbacks).

## Elsewhere: well-known bulk-bar redesign experiences

- **Gmail, select-all-across-pages.** Tick the header checkbox, then a banner offers "Select all conversations that match this search" (or "... in <label>"). Page size varies (50 or 100). The banner is what stops the checkbox silently meaning "everything"; a confirmation then states that the action affects all conversations in the search. Documented failure: a user selecting over 30K matches reported only about 2K affected. FLS lesson, already adopted in spec 8: two explicit steps, and the confirm re-derives and states the real count (`expected_count`). Gmail's mobile app lacks select-all-across-inbox. Sources: https://mailmeteor.com/blog/how-to-select-all-in-gmail , https://support.google.com/mail/thread/73130046 , https://blog.superhuman.com/how-to-mass-delete-emails-gmail
- **Shopify Polaris, bulk actions evolution.** `IndexTable` took `bulkActions` and `promotedBulkActions`. PR #11622 merged select-all back into the bulk-action UI, deprecated `SelectAllActions`, and changed overflow so promoted actions show as many as fit rather than all-or-menu. Issue #11669: select-all appeared on tables with no bulk actions; the author argued they are unrelated (fixed in #11670). The web-component migration says there is no standalone select-all, tells teams to define first whether "all" means the page, all loaded items or every result matching the query (`paginatedSelectAllAction`, "Select all N products"), and recommends a small stable promoted set in a menu. FLS lessons: promote a small fixed set and put the rest in the menu (already the first-two-plus-More rule); keep select-all separate from whether actions exist (the checkbox column already hides when no action passes `has_permission`); and define "all" explicitly (already done). Sources: https://github.com/Shopify/polaris-react/pull/11622 , https://github.com/Shopify/polaris/issues/11669 , https://shopify.dev/docs/apps/build/app-home/migrate-from-polaris-react/select-all-actions , https://shopify.dev/docs/apps/build/app-home/migrate-from-polaris-react/unstable-bulk-actions , https://polaris.shopify.com/components/index-table
- Earlier FLS research (spec 8, `research_ux_patterns.md`) already holds the generic pattern: a bar replaces or overlays the table toolbar once one row is selected, with "N selected", the actions and a way to clear; a separate explicit step for "Select all N matching"; prefer a result message to an undo toast because bulk side effects include emails. Not re-fetched here.

Limits of the external search: I read search summaries, not the full pages. The Gmail and Polaris wording above is as reported by those summaries; current props and Gmail page sizes are not confirmed.

## References (local)

- `spec_dd/3. done/2026-11-01_14:50_educator-interface-8-bulk-operations/1. spec.md`, `qa_report.md`, `todo.md`, `research_prior_art.md`, `research_ux_patterns.md`, `research_known_complaints.md`
- `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/1. spec.md`, `research_row_selection_bulk_actions.md`
- `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/1. spec.md`, `qa_report.md`, `todo.md`
- `spec_dd/3. done/2026-11-08_19:37_educator-interface-design-learner-csv-upload-design-fix/3. frontend_qa.md` (scroll padding clears the sticky header and the bar)
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`
- `docs/product/educator-interface.md`
- `freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html`
- Not read: git history (unavailable); the `design_source/` and `design_screenshots/` files (another unit's job).

status: ok · reason: prior art compiled from specs 2, 8, 12, the panel-framework skill and docs; external notes from search summaries only
