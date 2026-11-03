# Research: UX patterns for a multi-step bulk learner CSV import

Evidence quality: web search was thin. No Nielsen Norman page was surfaced, and no official GOV.UK bulk-CSV pattern exists. Items marked (practice) are common convention from design systems and general knowledge, not a cited source. I did not read design.md or the screenshots.

## Sources
- GOV.UK Error summary: https://design-system.service.gov.uk/components/error-summary
- GOV.UK Check answers: https://design-system.service.gov.uk/patterns/check-answers
- DfE bulk teacher-record check, which uses the error summary for file-level errors (wrong template, over 100 rows) and tells users to download a CSV with the errors marked, fix it and re-upload: https://design-histories.education.gov.uk/check-teachers-record/searching-for-multiple-teacher-records
- DfE CSV bulk upload write-up, which saves valid rows and returns error rows as a CSV to fix and re-upload: https://teacher-cpd.design-history.education.gov.uk/ecf-v2/building%20a%20CSV%20bulk%20upload%20feature
- GOV.UK design notes on upload design: https://designnotes.blog.gov.uk/2017/02/14/some-design-tips-for-uploading-things
- DWP file-upload research, which argues for validating files early rather than only at the final check step: https://design-system.dwp.gov.uk/research/file-upload
- MoJ upload files pattern: https://design-patterns.service.justice.gov.uk/patterns/upload-files
- Polaris drop zone (`<s-drop-zone>`: drag and drop or click to browse, plus a rejected-drop handler): https://shopify.dev/docs/apps/build/checkout/migrate-to-web-components/drop-zone.md
- Stepper guidance, all from design systems:
  - GitLab: https://design.gitlab.com/components/stepper
  - Visa wizard: https://design.visa.com/patterns/wizard/usage/
  - Salt wizard: https://main.saltdesignsystem.com/salt/patterns/wizard
  - Ontario step indicator: https://designsystem.ontario.ca/components/detail/step-indicator.html
  - SaaS wizard article: https://www.saasui.design/blog/saas-multi-step-form-wizard-ux-patterns

## Patterns

### Stepper and progress
- Use a stepper for linear flows of about 3 to 6 steps (GitLab, Visa, Salt). Show it at the top with "Step X of Y" plus the step labels.
- Suggested labels: Upload, Review, Import, Done. The "Importing" step is a transient state, so it can be a status within the wizard rather than a user-navigable step.
- Let users go back to completed steps (Visa). The re-upload action on the review screen does this.
- Do not let the indicator mislead (SaaS article). The Import step is quick, so keep the stepper honest by marking "Done" as the final state.
- Accessibility (practice): use an ordered list, `aria-current="step"`, and text labels rather than colour alone.
- Mobile at 375px (practice): collapse to "Step 2 of 4: Review" with a thin bar. Do not show a full horizontal labelled stepper.

### Upload step
- Show the format expectations before the file is chosen: a table of columns with required or optional, an example value and a short note, plus a template download link (practice, supported by the GOV.UK/DfE "use the provided template" approach).
- The drop zone must always be a real file input that works by click or keyboard. Drag and drop is an enhancement (Polaris, MoJ).
- States:
  - idle: dashed border, "Drag a CSV here or choose a file", the accepted type and the size limit.
  - drag-over: the border and background change, and the text reads "Drop to upload".
  - selected file: file name, size and a Remove or Replace action, with the primary "Upload and check" button enabled.
  - uploading: a spinner or progress, with the controls disabled.
  - error: the message sits next to the zone and in an error summary, linked to the field (GOV.UK single-field rule).
- Never rely on colour alone for the error state. Use an icon plus text.

### File-level error state
- File-level errors are problems with the whole file: wrong type, empty, too large, missing columns, over the row limit. Show them in an error summary at the top, linked to the file input, with a specific message and the fix (GOV.UK, DfE).
- Keep the user on the upload step with the format table and template link still visible. Do not make them restart.

### Review step
- Summary cards: Total, Valid, Errors. Use an icon and a label in addition to colour. The error card gets emphasis only when its count is above 0. On mobile, stack them or use a 3-up compact row.
- Two models for rows with errors:
  1. Block everything until the file is fixed.
  2. Import the valid rows and return the errors to fix (DfE partial upload).
  The design must state which one applies. The accept button copy should say exactly what will happen, for example "Import 42 learners", not just "Continue".
- Error table: columns are Row number, Field (column name), Message. Use plain language and say how to fix it. Cap the visible rows and show "Showing first N of M errors" (practice). Offer a downloadable error CSV where there are many (DfE).
- Re-upload action: place it beside or inside the error section ("Fix and re-upload") as a secondary action.
- Preview table: show the first N rows (commonly 10 to 25) with a caption "Showing first N of M learners to be imported". Keep it read-only. On mobile use horizontal scroll with a sticky first column, or a stacked card per row. Prefer the scroll, because it is simpler.
- This resembles GOV.UK Check answers, which is review before submit with the ability to change (https://design-system.service.gov.uk/patterns/check-answers). DWP argues for validating early, so errors surface at review and not after import.

### Action placement
- One primary action per screen, and it is the forward action. Secondary actions are Cancel, Back and Re-upload (practice).
- Desktop: primary on the left in GOV.UK style, or bottom-right in the common SaaS style. Pick one and apply it everywhere. Check which the project's existing educator views use.
- Mobile: stack the buttons at full width, with the primary first.
- If there are 0 valid rows, disable or hide the accept button and make Re-upload the primary action.

### Importing
- Show a non-dismissible progress state: "Importing N learners...", with a spinner, and disable the buttons to prevent a double submit. Use `aria-live="polite"`. For a large import, an indeterminate indicator is acceptable unless real progress is available.

### Complete summary
- Show a success panel with counts: imported, skipped (errors), and any already-existing learners, if that case applies. If there were errors, say so and offer the error CSV.
- Next actions: "View learners" or "View cohort" as primary, and "Import another file" as secondary (practice).
- The result must be visible in text and not only in a toast. Provide a way to return to the result later if it is feasible.

### Empty states
- Review with 0 valid rows: explain that nothing can be imported and offer re-upload.
- Empty file: treat it as a file-level error.
- Preview with no rows: don't render an empty table.

### Mobile at 375px
- Wide tables scroll horizontally inside their container, and the page itself must not scroll sideways.
- Targets should be at least 44px high. The drop zone should be a tappable "Choose file" button, since there is no drag-and-drop on touch.
- Stack the cards and buttons, and keep the stepper compact.

## Recommendations for the spec
1. State whether the import is all-or-nothing or partial, and make the button copy match.
2. Specify every drop zone state and which element carries each error message.
3. Specify the truncation limit N and the caption wording for both tables.
4. Specify the mobile behaviour for the stepper, cards and tables at 375px.
5. Specify the next actions on the complete screen.

status: ok
