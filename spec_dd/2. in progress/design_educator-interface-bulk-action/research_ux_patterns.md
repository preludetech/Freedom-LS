# Research: UX patterns for a data-table bulk-action bar

Topic: `ux_patterns`. Sources: the design screenshots 02b, 02c, 02d (visual reference only, per `design.md`), NN/g, Carbon (fetched and read), plus well-known design-system guidance from Material, Polaris, Atlassian, Gmail (cited from background knowledge, URLs not re-fetched this session; treat as lower confidence).

## 1. What the design shows (visual reference)

**02b Bulk selection.** The selection bar sits in the same slot as the search/filter row, directly above the table card, and replaces it (the filter row is gone). The bar is a single row in a bordered, rounded container with an accent outline. Left to right:
1. A tri-state (indeterminate) checkbox plus the bold text "4 selected".
2. A text link "Select all 31" (31 = the total in the current filtered result; the table header shows 284 learners overall in the sidebar, so 31 is the filtered set).
3. A thin vertical divider.
4. Text-only actions, each with a small leading icon and no outline or fill: "Message", "Move to cohort", "Resend invite", "Export".
5. A "More" button with an ellipsis icon (it has a light filled background in the open state) opening a dropdown menu: "Reset assessment attempts", "Change target completion", a divider, then "Deactivate" in red, with a helper line "Removes access. Progress is kept." and a tinted red background.
6. Far right: "Clear" with an X icon.

The header checkbox of the table is also indeterminate. Selected rows have a checked checkbox and a left accent edge. There is no separate "de-select all" link in the bar; the indeterminate header checkbox and "Clear" cover it. The idea asks for both de-select all and Clear, so the spec must decide whether they are the same control or two (see open questions).

**02c Bulk confirm.** Table and bar stay visible but dimmed behind a scrim. A centred modal contains: a round icon badge (red-tinted, same icon as the action), the title "Deactivate 4 learners?" (action verb plus count plus noun), a short body ("They'll lose access to their courses immediately. Progress, assessment results and certificates are kept, and you can reactivate them at any time."), a bordered scrollable-looking list of the affected learners (avatar initials + name), an option checkbox "Notify learners by email" (checked by default), then a footer separated by a rule with two buttons right-aligned: "Cancel" (outlined, secondary) then "Deactivate 4 learners" (solid red, primary). The primary label repeats the verb and the count.

**02d Bulk result.** The modal is closed, the selection is cleared, the search/filter row (search, Cohort filter, Add filter, "Sorted by Last active") has returned in place of the bar, and the affected rows show the new state ("Deactivated" badges, rows dimmed). A dark toast at bottom-right: check icon, "4 learners deactivated", an "Undo" action link, and a close X.

## 2. Pattern research

### Bar placement
Options:
- **Replace the toolbar in place (contextual action bar).** Used by Carbon (batch action bar appears at the top of the table once an item is selected, covering the toolbar; cancel on the far right), Material (contextual app bar replaces the app bar), Gmail. Pro: no layout shift of the table, uses a slot users already look at, search/filter are irrelevant mid-selection. Con: the user cannot change filters without clearing selection (usually acceptable, and arguably desirable because changing the filter would change what "all" means).
- **Insert above the table, pushing it down.** Causes layout jump; avoid.
- **Overlay/floating bar over the table.** Can hide rows or headers; used by some SaaS tools; needs z-index/overflow care.
- **Sticky bottom bar (floating action bar).** Good for long tables where the top toolbar scrolls out of view (Notion-style, mobile). Con: far from the header checkbox, can cover the last rows and pagination.

Recommendation consistent with the idea and design: replace the filter/toolbar slot with the bar. Make it sticky at the top of the viewport on scroll if the table is long (optional). Carbon: bar height should match a table row height. Keep the same container width/shape as the filter row so nothing jumps.

Sources: https://carbondesignsystem.com/components/data-table/usage/ , https://m3.material.io/components/app-bars/overview , https://polaris.shopify.com/components/tables/index-table

### Count and select-all / deselect-all
- Count text states the number plus the state: "4 selected" (design), Gmail "4 conversations selected", Polaris "4 selected". Use the noun only when it helps ("4 learners selected").
- Header checkbox is tri-state: unchecked (none), indeterminate (some), checked (all on the page). Carbon documents these three states. Clicking the indeterminate checkbox conventionally clears the selection (Polaris, Material) or selects all (Gmail selects all on page); pick one and be consistent. Design uses the indeterminate checkbox in the bar as the "deselect" affordance.
- Page-versus-all-results: when selection covers the whole visible page and more results exist, Gmail shows "All 50 conversations on this page are selected. Select all 1,234 conversations". The design simplifies this to a persistent "Select all 31" link whose number is the full filtered total. State the scope in the wording ("Select all 31") so the educator knows it is the filtered set, not everything.
- After select-all-across-pages, change the link to the reverse: "All 31 selected. Clear selection" (Gmail pattern), or hide the link when count equals total.
- Wording: "Select all N" (design), "Clear" or "Clear selection" / "Deselect all". "Clear" with an X on the far right is a dismissal control (Carbon "Cancel"). Keep the destructive-looking X away from the action buttons, which the right-alignment achieves.

### How many actions are promoted vs overflow
- Carbon: up to five actions in the toolbar, extras in an overflow. Material and Polaris: show the 2-4 most frequent actions; the rest go to "More".
- Decide by frequency (promote what educators do most), by safety (put destructive actions in the overflow, separated and visually marked, as the design does with "Deactivate"), and by space (at narrow widths fewer fit, so the promoted set must degrade into More).
- Design: four promoted (Message, Move to cohort, Resend invite, Export) plus More with three (two ordinary, one destructive after a divider with a helper line). The destructive item is intentionally not one click away.
- Text-only buttons with a small icon is the common "contextual toolbar" style; keep icons optional so the labels carry meaning (also needed for accessibility).
- Order: most frequent first, Export/neutral ones later, destructive last (and in overflow).

### Actions not applicable to all selected rows
Common approaches, in order of how frequently they are used:
1. **Disable with an explanation** (tooltip or title: "Resend invite is only available for invited learners"). Keeps the bar stable. Material/Polaris recommend disabling over hiding so users learn the action exists. Disabled controls need an explanation because they are otherwise opaque (NN/g and Adrian Roselli both caution about unexplained disabled buttons).
2. **Hide** inapplicable actions. Avoids clutter but makes the bar jump and hides capability.
3. **Allow, apply to the applicable subset, and say so** in the confirm modal ("3 of 4 learners will be messaged; 1 skipped because ..."), and in the result toast. Good when "mixed" selections are normal.
Carbon also notes that single-row actions (row overflow menus) should be disabled while batch mode is active; the design keeps the row "..." menus visible, so the spec should state which behaviour it wants.

Sources: https://carbondesignsystem.com/components/data-table/usage/ , https://polaris.shopify.com/patterns/bulk-actions (background knowledge), https://www.nngroup.com/articles/

### Confirmation modal content
From NN/g (fetched), https://www.nngroup.com/articles/confirmation-dialog/ :
- Reserve confirmations for serious or hard-to-undo actions. Routine actions should not be interrupted, because users learn to click through.
- Be specific: name the item and outcome, not "Are you sure?".
- Label buttons with outcomes, not Yes/No.
- Keep the main message short; progressive disclosure for detail.
- Avoid a default "Yes"; prefer undo over a dialog where possible.

Applied to bulk:
- **Title:** verb + count + noun, as a question for destructive/irreversible actions ("Deactivate 4 learners?"). Singular/plural must be handled ("Deactivate 1 learner?").
- **Body:** one or two sentences stating the consequence and the recoverability. Design body: what they lose, what is kept, how to reverse.
- **Affected list:** showing the names (design) lets users verify the selection; cap the height and scroll for large selections, or show the first few plus "and N more".
- **Primary button:** same verb with the count ("Deactivate 4 learners"), destructive colour for destructive actions; secondary "Cancel" to the left of primary (design) or per the project's convention. Do not focus the destructive button by default; focus Cancel or the dialog (NN/g: avoid default yes).
- **Escape, scrim click, X** dismiss without action (Atlassian and Material dialog guidance).
- **Non-destructive actions** (Export, Message) usually need no confirmation, only their form if they need input (see below). Per NN/g, confirm only when serious.
- Optional switches belonging to the action (design: "Notify learners by email", on by default) live in the body above the footer.

Sources: https://www.nngroup.com/articles/confirmation-dialog/ , https://atlassian.design/components/modal-dialog/usage , https://m3.material.io/components/dialogs/guidelines , https://polaris.shopify.com/components/overlays/modal

### Forms inside modals
- Use a modal when the action needs input before running (Move to cohort: pick the cohort; Message: subject/body; Change target completion: a date). The modal title names the action and count ("Move 4 learners to a cohort").
- Same footer layout: Cancel + primary verb with count; primary disabled until the form is valid (or validate on submit; the project's HTMX convention is a 422 response that re-renders the form with errors, inside the modal).
- Keep forms short; if long, a page or side panel (the design has a separate message panel for sending a message, which is out of scope for this feature).
- Focus: first field on open; return focus to the triggering control (or to a sensible place, since the bar will vanish) on close; trap focus inside; Escape closes.
- Validation errors stay inside the modal, the modal stays open, selection is retained.

Sources: https://atlassian.design/components/modal-dialog/usage , https://www.nngroup.com/articles/modal-nonmodal-dialog/

### Result feedback
- The design: modal closes, selection clears, bar disappears and the filter row returns, rows update in place, toast at bottom-right "4 learners deactivated" with Undo and a dismiss X.
- Common practice: toast/snackbar for success (auto-dismiss after roughly 5-8 s, longer or persistent when it contains an action like Undo; Material guidance on snackbars: https://m3.material.io/components/snackbar/guidelines). Toast must be announced (`role="status"`, `aria-live="polite"`) and be reachable by keyboard when it has an action.
- Clear the selection on success, because the action has been applied and keeping stale checkboxes invites accidental repeat actions. Keep the selection on failure or validation error so the user can retry.
- Partial failure: the toast (or an inline alert above the table) should state the split ("3 deactivated, 1 failed") and say why; selection can narrow to the failed ones.
- Undo (design) is NN/g's preferred protection but requires a reversible action and a reversal path; whether it is in scope is for the spec to decide (the design.md says design-only controls not asked for by the spec are left out; the idea.md does not mention Undo).
- Update the affected rows (status badge) without a full page reload (HTMX swap), and keep scroll position.

### Mobile / narrow widths
- Carbon/Material: the contextual bar remains, but labels collapse. Pattern: show count + Clear + at most one or two actions (icon-only with accessible labels) + More; all the rest inside More. Alternatively the bar becomes a sticky bottom action bar, which is within thumb reach.
- Row checkboxes need a 44x44 touch target (WCAG 2.5.5 target size / Apple HIG) even when visually small.
- Tables on narrow screens often become horizontally scrollable or card lists; the bar should not scroll horizontally with the table.
- Modal on mobile becomes full-width/bottom sheet or full screen; the footer buttons stack or stay full-width with the primary on top.
- The design is desktop only (1440); anything narrower is a decision for the spec, not something the design settles.

### Transitions
- Bar appears/disappears with a short (about 100-200 ms) fade or slide, matching the filter row height so the table does not jump. Swap rather than animate if the heights match. Respect `prefers-reduced-motion`.
- Modal: scrim fade plus a small scale/fade-in (about 150-250 ms); no animation on close beyond a quick fade.
- Toast: slide/fade in from the corner, fade out.
- Selected rows: instant highlight (accent edge and tint), no animation needed.
- Material motion guidance: https://m3.material.io/styles/motion/overview

## 3. Accessibility notes
- Header checkbox: `aria-checked="mixed"` when partial. Each row checkbox labelled with the row's learner name.
- Bar: `role="toolbar"` with a label; the count is a live region (`aria-live="polite"`) so "4 selected" is announced on change.
- Disabled actions use `aria-disabled` plus an explanation if the user should be able to focus them.
- Destructive menu item distinguished by more than colour (position, divider, helper text, as in the design).
- Modal: `role="dialog"` (or `alertdialog` for destructive confirmation), `aria-labelledby` the title, focus trap, restore focus.

## 4. Decisions the spec needs to make (surfaced by the research)
1. Are "de-select all" and "Clear" one control or two? The design shows the indeterminate checkbox plus "Clear" only.
2. "Select all N": the whole filtered set across pages, or the current page? Wording after select-all.
3. Which actions are promoted, which go into More, and the order (the design's set is illustrative, the spec's real action set decides).
4. Inapplicable actions: disable with explanation, hide, or apply-to-subset?
5. Which actions need a confirmation (destructive/irreversible only, per NN/g) and which need a form.
6. Whether Undo is in scope (the idea does not list it).
7. Row-level "..." menus while selecting: keep or disable.
8. Narrow-width behaviour and the sticky-on-scroll behaviour.

## References
- NN/g, Confirmation dialogs can prevent errors: https://www.nngroup.com/articles/confirmation-dialog/ (fetched)
- Carbon, Data table usage (batch actions): https://carbondesignsystem.com/components/data-table/usage/ (fetched)
- Material 3 app bars: https://m3.material.io/components/app-bars/overview
- Material 3 dialogs: https://m3.material.io/components/dialogs/guidelines
- Material 3 snackbar: https://m3.material.io/components/snackbar/guidelines
- Material 3 motion: https://m3.material.io/styles/motion/overview
- Polaris index table: https://polaris.shopify.com/components/tables/index-table
- Polaris modal: https://polaris.shopify.com/components/overlays/modal
- Atlassian modal dialog: https://atlassian.design/components/modal-dialog/usage
- NN/g modal vs nonmodal dialogs: https://www.nngroup.com/articles/modal-nonmodal-dialog/

status: ok · reason: design screenshots read; NN/g and Carbon fetched; Material, Polaris and Atlassian URLs cited from background knowledge and not re-fetched
