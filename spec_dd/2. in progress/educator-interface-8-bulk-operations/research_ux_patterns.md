# Research: UX patterns for bulk import and bulk actions

Topic `ux_patterns`. Question: what are the common UX patterns for this kind of work?

Provenance: "Fetched" means I read the page this session. "Background" means well-known behaviour of that system that I did not re-verify here. Treat background items as leads, not citations.

## Findings first

1. **Import as a page with a stepper** is the norm. Atlassian says use 3+ steps, keep labels to 1-2 words, make visited steps clickable and subdue the unvisited. The idea's Upload / Preview / Result fits. The mockup labels the steps Upload / Map fields / Review, so the spec must rename the steps or say why it diverges.
2. **Preview-then-commit with one label per row and a summary of counts** is the strongest pattern. GOV.UK's "Check answers" says to state that nothing is done until the user confirms, to name the confirm button after the action, and to offer a way back that keeps the earlier input. Applied here: the button reads "Add 24 learners", not "Continue". Back or "Fix the file" must not force a re-upload of a file that is still valid.
3. **Strict headers plus a template** is the lower-cost choice for a four-column file (`email`, `first_name`, `last_name`, `cohort`). Mapping only pays off when files come from other systems, as the mockup's `full_name`, `work_email`, `licence_no` and `region` columns suggest. The mockup's mapping UI adds a step, a state to persist, and a mobile layout (M11 stacks one card per column). Middle path: match headers case-insensitively, ignore unknown columns with a visible "Ignored: region, licence_no" note, and hard-fail only on a missing `email`. This avoids a mapping screen and still never silently drops data.
4. **Bulk action bar**: a bar replaces or overlays the table toolbar once one row is selected. It shows "N selected", the actions, and a way to clear. The header checkbox is page-scoped with an indeterminate state. A separate, explicit step offers "Select all N matching this filter". Do not make the header checkbox silently mean "everything".
5. **Confirmation names the verb, the count and the exceptions**: "Add 12 learners to Accra January intake. 3 are already members and will be skipped." Mixed-eligibility selections are handled by computing eligibility server-side and showing the split before confirming, not by failing late.
6. **Background jobs** need three things: immediate acknowledgement, a status page that survives leaving, and a completion channel. Polling the status page with HTMX is the cheap in-app channel. Email is the "I left" channel.
7. **Accessibility is mostly cheap**: a `role="status"` live region for the selection count, labelled checkboxes, native `<dialog>` focus handling, and an error summary that takes focus.

## 1. Multi-step import wizard

### Stepper
- Atlassian progress tracker (fetched): 3+ steps (fewer should use a plain Next button), at most 6, 1-2 word labels, visited steps clickable, unvisited subdued. Source 1.
- Mockup desktop: numbered circles joined by lines, with a green check on done steps. Mobile (M11): three segmented bars plus the text "Step 2 of 3" and a step title. The page needs the text form as well as the visual one (see accessibility): `aria-current="step"` on the current step, and "Step 2 of 3" in text.
- The mockup draws the import as a modal dialog (desktop) and a full-height bottom sheet (mobile). The idea settles on a page. Keep the mockup's visual language (stepper, file chip, warning callout) and drop the dialog chrome. On mobile, the sheet's back arrow becomes the page's back link.

### Upload step
- GOV.UK file upload (fetched, source 2): the specific error strings are a pattern worth copying. Wrong type: "The selected file must be a CSV". Empty: "The selected file is empty". Too big: "The selected file must be smaller than 2MB". Wrong template: "The selected file must use the template". They also say to ask for an upload only when it is critical, and that drag and drop is an enhancement over a visible "Choose file" button. The button is the baseline and the dropzone is optional.
- Template download sits next to the input (link, not buried). Offer two example rows, as the idea says. Say which column is required, e.g. "`email` is required. `cohort` is matched by name."
- Show the file chip after upload (mockup: name, "28 rows · 6 columns · 42 KB", "Replace file"). Do this on the preview step so the educator sees what is being previewed.
- Hard failures (not a CSV, no `email` header, empty, over the row cap, bad encoding) stop at the upload step with an error summary. Per-row problems never do. Check for a UTF-8 BOM and Excel's semicolon delimiter, since those are the usual real-world CSV breakers. This is my judgement, not a design-system rule.
- Cap the file size and row count on upload and say the cap on the page. The cap and the background threshold are different numbers.

### Preview step
- One label per row, a summary of counts first, then the table. The idea's labels are: new account, existing account joined to this organisation, already a member, reactivated, error with reason. Each count is a filter chip/tab: "All 28 · New 20 · Existing 4 · Already a member 2 · Reactivated 0 · Errors 2".
- Do not signal status by colour alone. Use an icon or text label in each row, with colour as reinforcement (WCAG 1.4.1).
- Filter-to-errors: make the "Errors" count a link or toggle that filters the table, and keep the filter in the query string so reload and Back preserve it (this matches the page-not-modal decision). Default to showing errors first, or show a short errors-only list above the full table, when errors exist.
- Row numbers should be the CSV's own line numbers (header = line 1), so an educator can find the line in Excel.
- Mockup already carries a warning callout with the exact kind of sentence needed: "2 rows have email addresses already on the platform. They'll be enrolled into the cohort rather than created again." That reassures the educator that nothing is overwritten. Keep it, and add "Existing details are not changed."
- Paginate or cap the preview table (first 50 per label, "and 120 more") so a 5,000-row file does not render a huge page. The counts still cover every row.
- Choice at the end: two clearly different actions, not a hidden default.
  - Primary: "Add 24 valid rows" (state the count and the exclusion: "2 rows with errors will be skipped").
  - Secondary: "Fix the file and upload again" (link back to step 1; offer "Download the 2 error rows" here too).
  - If every row is an error, hide or disable the primary action and say why.
  - If zero errors, the proceed button reads "Add 28 learners" with no skip wording.
- Moodle's approach, as the idea's resources describe: upload modes and a preview. See the comparable-systems doc rather than re-deriving.

### Result step
- Show counts by label in the same order and wording as the preview, so the educator can reconcile. Include a headline sentence: "Added 24 learners. 2 rows were skipped."
- Error report: CSV of the failed rows, original columns first, with a `reason` column appended, so the fixed file can be re-uploaded directly. Idempotency (already a member on re-run) means re-uploading the whole fixed file is also safe, which can be said in the page: "Re-uploading the whole file is safe. Rows already added show as 'already a member'."
- Links: back to the cohort or learners list, and "Import another file". GOV.UK confirmation pages state what happens next. Here that is "New learners were sent a setup email."
- Make the result URL stable and re-visitable (needed anyway for background jobs). Do not render it only from the POST response.

### Keeping the file between steps
- The preview must show what the commit will do, and the commit must run on the same data. Common implementations: store the parsed rows or the file server-side (a keyed upload record) and re-validate at commit, because the world can change between preview and confirm (a learner joined the cohort meanwhile). Re-check eligibility at commit and report differences in the result. This follows from "nothing is written until confirm" and "idempotent" in the idea.

## 2. Bulk actions on tables

### Selection bar
- Carbon data table (fetched, source 3): a batch action bar appears at the top of the table once a row is selected. Row-level icon buttons and overflow menus are disabled while it is active. The header checkbox has three states (checked, unchecked, indeterminate) and row checkboxes have two. Cancel sits at the far right of the bar, and deselecting everything also exits. Carbon's page gives no guidance on selection-count text or batch accessibility.
- Polaris (via search, source 4): the header checkbox covers only the current page. Once a full page is selected and more results exist, a separate control selects the full result set. Track whether the selection is explicit IDs or query-wide. For query-wide selection, send the filter plus excluded IDs to the server instead of loading every ID. Shopify's own docs label the count "N selected on this page". Community posts show the typical bug: a "select all" that only selects loaded rows.
- Gmail-style banner (background, widely copied): after selecting a page, a strip says "All 25 on this page are selected. Select all 312 matching 'cohort: Accra'." Then "All 312 selected. Clear selection."
- Recommended for FLS, following the idea's "if spec 2 shipped it":
  - Bar text: "3 selected" with a visible Clear button.
  - Header checkbox = this page, indeterminate when partial.
  - If spec 2 has a filter query, offer "Select all N matching" as an explicit link in the bar. Send the filter plus excluded IDs, and let the server re-resolve (and re-check permission on) every object.
  - Changing the filter or the page while a selection exists: say what happens. Safest options are to clear on filter change, or keep and show "3 selected (2 on other pages)". Pick one and test it.
  - With HTMX swaps of the table, keep checked state across swaps (the selection set lives in the DOM or a hidden form, not in transient row state). This is the commonest bug in HTMX bulk UIs.

### Action menu
- Show the actions that apply to the current table's objects. The idea lists seven learner actions. A bar with seven buttons overflows, so show the 2-3 most common and put the rest in a "More actions" menu. Use "Add to cohort" and "Remove from cohort" next to each other as a pair so the remove is as findable as the add (the idea: every add has its remove).
- Disabled actions: say why. A disabled button with a tooltip is not keyboard- or touch-accessible. Use `aria-disabled="true"` (keeps it focusable) with the reason in a visible hint or `aria-describedby`: "Deactivate needs the 'manage learners' permission." The idea says to offer actions only to permitted roles, so hide actions the role can never do and disable only those that this selection cannot do.
- Carbon's rule that row-level actions are disabled during batch mode avoids two competing action paths. That is optional for FLS but worth deciding.

### Confirmation dialog
- Atlassian (fetched, source 5): use a modal for a short-term decision. Warning treatment signals potential data loss. Banners are poor for a single-action confirmation.
- Content pattern: title = verb + count ("Remove 12 learners from Accra January intake?"). Body = the effect on people ("They keep their accounts and their progress. They lose access to the cohort's courses.") and the exceptions ("3 are not in this cohort and will be skipped."). Confirm button repeats the verb and count ("Remove 12 learners"). Cancel is a real button. This is the idea's "what will happen to how many" and "same wording as the single actions".
- Destructive actions: for deactivate and unregister, use destructive button styling and put initial focus on the least destructive control (ARIA APG, source 6). Typed confirmation ("type DEACTIVATE") is the heavy tool. It is usually reserved for irreversible deletes. Everything here is reversible (reactivate, re-register), so I would not use it unless the count is very large. If the spec wants a threshold, a count is the natural trigger. Say in the dialog that it can be undone and how: "You can reactivate them from this list."
- Target picker (cohort or course) sits inside the same dialog above the confirmation sentence, and the sentence updates as the picker changes. Do not show an empty "Add to ?" sentence. Disable confirm until a target is chosen.
- Prefer a result message to an undo toast, because bulk side effects include emails (resend setup email, new accounts) that cannot be undone.

### Mixed eligibility
Examples: selection includes learners already in the cohort (add), not in it (remove), already deactivated (deactivate), already active (reactivate), or with no pending setup (resend setup email).
- Pre-compute the split server-side when the dialog opens: "9 will be added. 3 are already members and will be skipped." Show skipped people with a reason in an expandable list, capped. Salesforce and most CRMs report skipped and failed counts after the fact (background). Showing them before the commit is better, and it matches the import preview's labels.
- If nobody is eligible, the confirm is disabled and the dialog says why. Do not open an empty dialog.
- Permissions are checked per object (idea). Objects the user cannot act on are a separate bucket from "ineligible": "2 are outside your organisation's cohorts you can manage and will be skipped".
- The result uses the same buckets: "Added 9. Skipped 3 (already members)." A bulk run reports in the same vocabulary as the import result.

### Result feedback after a bulk run
- Use a status message with counts, kept visible (not an auto-dismissing toast, which also fails for screen-reader and slow-reader users). Keep selection state defined: clear it on success, keep it on failure so the educator can retry.
- A table refresh via HTMX needs the status message in a live region that already exists (see accessibility).

## 3. Background job UX

- Threshold: Docebo-style background threshold is in the idea's resources. The UX rule is that the educator should know before confirming which path they are on: "This will run in the background. We'll show progress here" when above the threshold.
- Acknowledge immediately: redirect to the stable job/result URL, not back to the table with a toast.
- Progress: "Added 140 of 600" (a determinate count) beats a spinner. Use `<progress>` or `role="progressbar"` with a text equivalent. If the task framework only knows queued/running/done/failed, show those four states honestly and skip the fake percentage.
- Polling: HTMX `hx-trigger="every 2s"` on the status fragment, and stop polling by returning the fragment without the trigger once the job is done (HTMX's documented way to end polling). Back off for long jobs. A failed poll should not look like a failed job.
- Announce completion: update a `role="status"` region ("Import finished. 598 added, 2 skipped.") rather than moving focus.
- Leaving the page: say it is safe: "You can leave this page. We'll email you when it finishes." Salesforce emails the user who started the import on completion (Trailhead, source 7) and keeps a Bulk Data Load Jobs status page admins can revisit. The pair (status page plus email) is the common answer. For FLS, the poll-versus-email choice in the idea can be both: poll while the page is open, email if configured. Make the email link to the result page.
- Failure: a job that crashes midway leaves a partial result. The idea's default is "valid rows commit", so the result must say how far it got ("Stopped after 340 of 600") and the safe next step ("Upload the same file again; rows already added will show as 'already a member'"). Idempotency is the UX safety net here.
- Staleness: a result link for a job someone else started should be permission-checked and scoped to the organisation (`fls-dev:multi-tenant`).

## 4. Mobile

- The mockup M11 uses a full-height sheet with a back arrow, a close X, segmented progress bars, "Step 2 of 3", and one card per column. Cards instead of a wide table is the right call for the preview too: one card per row with the label badge on top, the email, and the reason underneath.
- Selection on mobile: long-press or a "Select" mode button is the usual way in (Material, background, contextual action bar pattern). A persistent checkbox column on a narrow card list is also fine and simpler to build with HTMX. The bar should be sticky at the bottom (thumb reach) and respect the safe-area inset. "N selected" and the primary actions fit, the rest in "More".
- Touch targets: at least 24x24 CSS px under WCAG 2.2 AA (2.5.8), and 44x44 is the common recommendation. Checkboxes in a table row need a bigger hit area than the visible box (label wraps the whole cell).
- The file input on mobile opens the OS picker. Drag and drop is irrelevant, so the "Choose file" button must be the primary affordance (GOV.UK, source 2). Mobile educators rarely have the CSV on the phone, so the template download plus "email it to yourself" is a realistic path. Don't over-invest, but don't break it.
- Confirm dialogs become bottom sheets. Keep the same text and focus rules.
- Result and error-report CSV download works on mobile browsers, but saving it is clumsy. Keep the on-page list of the first few errors so the page is useful without the file.

## 5. Accessibility

- **Checkboxes**: every row checkbox needs a unique accessible name ("Select Yaw Boateng"), not an unlabeled box. The header checkbox is named "Select all learners on this page". Use native `<input type="checkbox">`. Set the indeterminate state through the `indeterminate` property (`aria-checked="mixed"` is for custom roles). Carbon documents the three-state header (source 3).
- **Selection count as a live region**: put the "3 selected" text in `role="status"` (implicit `aria-live="polite"`). WCAG 4.1.3 (source 8) requires status messages to be programmatically determinable without taking focus, and warns against overusing assertive alerts. Update on settle, not on each keystroke, and make the region present in the DOM before it changes (an element inserted already containing text is not reliably announced). The same applies to "Added 9. Skipped 3." after a bulk run and to the job progress.
- **Bar appearing**: do not move focus to the bar when it appears, because the user is mid-selection. Keep it in DOM order immediately before the table so it is reachable. If the bar is a toolbar, `role="toolbar"` with an accessible name is acceptable, but a plain group of buttons is enough.
- **Modal focus** (ARIA APG dialog pattern, source 6): move focus into the dialog on open. For dense content, focus a `tabindex="-1"` title. For irreversible actions, focus the least destructive button. Tab and Shift+Tab stay inside. Escape closes. A visible close or cancel button is in the tab order. On close, focus returns to the opener. If the opener (the bar) is gone because the selection cleared, return focus to the table heading or the status message, not to `body`. A native `<dialog>` opened with `showModal()` gives containment and Escape for free, and the shared modal should be built that way if it is not already.
- **Errors**: GOV.UK error summary (fetched, source 9): always show a summary at the top of `main` for a validation error, even a single one, with the heading "There is a problem", move focus to it, link each message to its field, and match the inline text. Use this for upload failures. For per-row import errors, the table plus the error-count filter is the equivalent, and the page should announce "2 rows have errors" in the live region.
- **Status not by colour alone**: each row label has text.
- **Stepper**: `<ol>` with `aria-current="step"` on the active item, step name included in the visible text.
- **Table semantics**: a preview with 28+ rows is a real `<table>` with `<th scope>` headers. Do not build it from divs as the mockup's inline grids do.
- **Reduced motion**: if progress animates, respect `prefers-reduced-motion`.

## 6. Voice (brand-guidelines `voice.md`)

- Error messages: "Name the specific problem, suggest a specific fix, leave blame out." Examples in the file's style:
  - "Row 14: this email address isn't valid. Check for a missing @ or a stray space."
  - "Row 9: no cohort called 'Accra Jan' in your organisation. Check the spelling against your cohort list."
  - "The file has no email column. Add a column headed email, or download the template."
- Routine actions end on a full stop. State results with a number: "Added 24 learners." not "Success! Your import has been completed."
- Use "learners" (never "students") and "cohort". Avoid SaaS phrasing ("seamlessly", "unlock"). The voice is technical and direct, so showing the expected header row in a monospace snippet fits ("`email,first_name,last_name,cohort`").
- Note: the mockup copy says "First Class fields" (a different product name). Don't copy that string.

## 7. Open questions this research bears on (for the spec to decide)

1. Strict headers vs mapping: recommendation above is strict-with-ignore-notice. Revisit only if the comparable-systems research shows educators import foreign-system exports.
2. Mockup step names (Upload / Map fields / Review) differ from the idea (upload / preview / result). Result as a third step after a confirm is a different thing from the mockup's Review. The stepper probably needs Upload / Preview / Result, and the mockup should be updated or noted as superseded.
3. Whether "select all matching" ships depends on spec 2. If not, show a clear "Selection covers this page only" line so no one assumes otherwise.
4. Selection behaviour across filter and page changes (clear vs keep).
5. Where the typed-confirmation line sits, if at all (suggest never, reversible actions only).
6. Poll plus email as combined delivery.
7. Preview table size cap and the upload row cap.

## References

1. Atlassian, Progress tracker usage: https://atlassian.design/components/progress-tracker/usage (fetched)
2. GOV.UK Design System, File upload: https://design-system.service.gov.uk/components/file-upload/ (fetched)
3. Carbon Design System, Data table usage (batch actions): https://carbondesignsystem.com/components/data-table/usage/ (fetched)
4. Shopify Polaris, select-all migration guide and community threads: https://shopify.dev/docs/apps/build/app-home/migrate-from-polaris-react/select-all-actions and https://community.shopify.com/t/polaris-index-table-how-to-implement-select-all-when-pagination-is-used/134051 (search summary; not opened in full)
5. Atlassian, Designing messages: https://atlassian.design/foundations/content/designing-messages/ (fetched; the page covers confirmation only indirectly)
6. W3C ARIA Authoring Practices, Dialog (Modal): https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ (fetched)
7. Salesforce Trailhead, Use the Data Import Wizard: https://trailhead.salesforce.com/projects/import-and-export-with-data-management-tools/steps/use-the-data-import-wizard (search summary: completion email and Bulk Data Load Jobs page; mapping preview not confirmed)
8. W3C WCAG 2.2, Understanding SC 4.1.3 Status Messages: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html (fetched)
9. GOV.UK Design System, Error summary: https://design-system.service.gov.uk/components/error-summary/ (fetched)
10. GOV.UK Design System, Check answers pattern: https://design-system.service.gov.uk/patterns/check-answers/ (fetched)
11. Material Design 2, Data tables (selection and contextual action bar): https://m2.material.io/components/data-tables (fetch returned no content; the contextual-bar remark is background knowledge)
12. Mockups read: `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/Educator Cohorts and Admin.dc.html` (screen 08, dialog, step 2 of 3) and `Educator Mobile Cohorts and Admin.dc.html` (screen M11).
13. Brand voice: `.claude/skills/brand-guidelines/voice.md`.

Not covered: Salesforce Lightning's own design guidance (only the Data Import Wizard behaviour above), and Atlassian's bulk-edit patterns. The Lightning design-system pages were not fetched.

status: ok
reason: complete; Material and Lightning items are background or search-summary level, flagged inline
