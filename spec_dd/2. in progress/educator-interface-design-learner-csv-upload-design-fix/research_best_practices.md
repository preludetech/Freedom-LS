# Research: best practices for restyling a learner CSV bulk-import flow

Scope: styling and markup of an existing working flow (Django + HTMX + Tailwind + Alpine). Sources are mostly design-system docs and vendor blogs, so treat them as guidance, not specification. Items marked (general) come from established WCAG/HTML practice and were not individually web-verified in this pass.

## 1. File upload UI
- Keep the native `<input type="file">` as the real control and style it, or the label for it, as the drop zone. Do not replace it with a div. The drop zone enhances the native input. (https://blog.filestack.com/html-file-upload-accessibility/, https://ezud.com/accessible-file-upload-design/)
- Drag-and-drop must never be the only path. WCAG 2.2 SC 2.5.7 (Dragging Movements) requires a non-drag alternative. A visible "Choose file" button/label that opens the file picker satisfies this. (https://ezud.com/accessible-file-upload-design/, https://carbondesignsystem.com/components/file-uploader/accessibility/)
- Give the input a programmatic label (`<label for>`), or screen readers announce only "file upload". Tie the format help text to it with `aria-describedby`. (https://blog.filestack.com/html-file-upload-accessibility/)
- If you build a custom focusable zone (`tabindex="0" role="button"`), it needs Enter/Space to open the picker. Prefer visually hiding the input (not `display:none`) and showing a focus ring on the zone via `focus-within`. (https://carbondesignsystem.com/components/file-uploader/accessibility/)
- Show drag-over state with more than colour (border style change plus text such as "Drop to upload"). Show the chosen filename and size after selection, with a way to remove or replace it. (general)
- Apply `accept=".csv"` as a hint only. Validation stays server-side, which the current flow already does.

## 2. Communicating CSV format requirements
- Put requirements before the action: required columns, an example of the first rows, encoding, max size and row count. Use a small table or code block with a sample, not a prose paragraph. (https://blog.csvbox.io/csv-errors-nontechnical/, https://dromo.io/blog/building-a-seamless-csv-importer)
- Offer a downloadable template as a prominent secondary button next to the drop zone. Use a text label with an icon, not an icon alone. (general)
- Plain-language wording for non-technical educators. Distinguish required from optional columns with text ("Required"), not colour alone.

## 3. Error presentation
- Separate file-level from row-level errors. File-level problems (empty, missing headers, wrong format, too large) block the whole import. Show them on the upload screen, in an alert near the drop zone, with the fix ("Add a header row containing: ..."), and keep the drop zone ready for re-upload. (https://blog.csvbox.io/row-level-errors-csv/, https://mfyz.com/designing-scalable-csv-importers-what-a-good-importer-should-do/)
- Row-level errors: give row number (matching the user's spreadsheet row numbers), the column and a specific message with the suggested fix. Aggregate or group similar errors with counts when there are many. (https://blog.csvbox.io/row-level-errors-csv/, https://mfyz.com/designing-scalable-csv-importers-what-a-good-importer-should-do/)
- Summary counts at the top (valid / errors / skipped) as a scannable stat strip. This also gives the user triage before they look at detail. (https://mfyz.com/designing-scalable-csv-importers-what-a-good-importer-should-do/)
- Offer "fix and re-upload" prominently. A downloadable error report is a common extra, but only add it if the spec asks for one (project rule: do not build unrequested functionality). (https://blog.csvbox.io/skip-invalid-rows/)
- Show errors beside the row (inline in the table row or an adjacent error column) rather than only in a separate list, so the row and its problem are linked. Mark rows with an icon plus text label ("Error"), not just a red tint.

## 4. Preview and confirm step
- Show a parsed preview before committing: what will be created, with the count. This is the established file -> validate -> preview -> submit flow. (https://dromo.io/blog/building-a-seamless-csv-importer, https://blog.csvbox.io/file-upload-patterns/)
- The confirm button states the consequence ("Create 42 learners"). Place it after the preview. Disable or hide it when there is nothing valid to import, and say why.
- Give a secondary "Cancel / upload a different file" action next to the accept button.
- Cap the preview height or paginate for large files, so the accept button stays reachable (sticky action bar on mobile is an option).

## 5. Progress for sync vs async imports
- Synchronous: a button busy state is enough. Use `htmx-indicator` / `hx-disabled-elt` to disable the button and show a spinner with text ("Importing..."). This prevents double-submit. (general; htmx docs)
- Async/long-running: use a determinate progress bar (`role="progressbar"` with `aria-valuenow`) if counts are known, otherwise an indeterminate spinner with a status text. Poll via `hx-trigger="every 2s"` and stop polling on completion. (general)
- Whatever the style, the "importing" state should say what is happening and that the user should not close the page (if that is true). Announce state changes through a live region. (https://blog.filestack.com/accessible-react-file-upload/)

## 6. Result summaries
- Lead with the outcome in a heading ("42 learners imported"), then a count breakdown (created / skipped / failed). Use text and icon together.
- Next actions: link to the learner list or cohort, and "Import another file". Preserve any failed-row detail so the user can act. (https://blog.csvbox.io/reduce-support-tickets-import-ux/)

## 7. Accessibility with HTMX
- htmx does not manage accessibility. After a swap, move focus deliberately. (https://tessl.io/registry/alonso-skills/htmx/files/references/gotchas.md)
- Swap target: give the new step's heading or error summary `tabindex="-1"` and focus it in an `htmx:afterSwap` listener (or `autofocus`/Alpine `x-init`). Use `role="alert"` on file-level error summaries so they are announced. (https://flaviocopes.com/courses/htmx/focus-after-a-swap/)
- Keep a persistent wrapper with `aria-live="polite"` for status messages (importing, complete). The live region must exist in the DOM before its content changes. (https://tessl.io/registry/alonso-skills/htmx/files/references/gotchas.md)
- If the swap removes the focused element (for example the submit button), focus is lost. Move it to the new heading. See htmx issue https://github.com/bigskysoftware/htmx/issues/1431.
- Elements keeping the same stable `id` across a swap preserve focus. Use stable ids for the file input if it is re-rendered with an error.
- Colour is never the sole indicator (WCAG 1.4.1). Pair with icon and text. Contrast is at least 4.5:1 for text and 3:1 for UI components and focus rings (WCAG 1.4.3, 1.4.11, general).
- Use real `<table>` markup with `<th scope="col">` and a `<caption>` or `aria-label` for the preview and error tables. Link per-field error messages to their cells with `aria-describedby` where practical. (general)
- Respect `prefers-reduced-motion` for spinners and drop animations (general).

## 8. Responsive tables at 375px
- Preferred: wrap the table in `overflow-x-auto` with a visible horizontal-scroll cue, a sticky first column (row number or name), and a focusable wrapper (`tabindex="0"`, `role="region"`, `aria-label`) so keyboard users can scroll it. (general; WCAG 1.4.10 Reflow allows 2-D scrolling for data tables)
- Alternative for few columns: collapse each row into a stacked card below the `sm` breakpoint (Tailwind `hidden sm:table` plus `sm:hidden` cards), including the row error inside the card. Keep semantic equivalence.
- Do not hide columns without a way to see them. Error messages must stay visible on mobile.
- Stat strip: use a grid that wraps (`grid-cols-2 sm:grid-cols-4`). Primary action buttons go full width on mobile, with touch targets at least 44px (WCAG 2.5.8 sets a 24px minimum, general).

## Actionable checklist for the spec
1. Native input stays; restyled label is the drop zone; visible "Choose file" button.
2. Format description is a table plus sample, with a template download button.
3. File-level errors: `role="alert"` summary plus fix instructions, with the drop zone kept visible.
4. Review: stat strip, error rows with row/column/message, preview table, "Create N learners" accept button plus cancel.
5. Importing: disabled button plus spinner and text, with a polite live region.
6. Complete: outcome heading, count breakdown, next-action links.
7. Each HTMX step swap focuses the new heading or alert.
8. Tables: scrollable focusable wrapper or card layout at 375px.
9. Check status never relies on colour alone.

## Sources
- https://blog.filestack.com/html-file-upload-accessibility/
- https://ezud.com/accessible-file-upload-design/
- https://carbondesignsystem.com/components/file-uploader/accessibility/
- https://blog.filestack.com/accessible-react-file-upload/
- https://blog.csvbox.io/row-level-errors-csv/
- https://blog.csvbox.io/skip-invalid-rows/
- https://blog.csvbox.io/csv-errors-nontechnical/
- https://blog.csvbox.io/file-upload-patterns/
- https://blog.csvbox.io/reduce-support-tickets-import-ux/
- https://dromo.io/blog/building-a-seamless-csv-importer
- https://mfyz.com/designing-scalable-csv-importers-what-a-good-importer-should-do/
- https://tessl.io/registry/alonso-skills/htmx/files/references/gotchas.md
- https://flaviocopes.com/courses/htmx/focus-after-a-swap/
- https://github.com/bigskysoftware/htmx/issues/1431

status: ok
