# Research: reference implementations for bulk CSV user import UI

Scope: fetched with web tools on 2026-11-03. Items marked (not verified) came from search snippets or were not retrievable (Canvas SIS page 404, MS 365 page 404, Polaris DropZone redirected to a landing page, Flatfile docs root empty, GitHub Primer/Atlassian not fetched).

## Per-product findings

### Moodle "Upload users" (closest to an LMS educator/admin flow)
- Flow: upload file + pick encoding -> **preview** page with settings -> "Upload users" -> **results table** (per-user row, changes/exceptions, non-added rows highlighted, summary counts of uploaded/updated/weak-password/errors) -> "Continue".
- Format communicated: docs page lists required columns (username, firstname, lastname, email), optional columns; advice to test with one record first. Not an in-UI template.
- Errors: row-level in the results table ("User not added - error"); no file-level pre-validation step beyond encoding.
- Partial import: yes, valid rows import, error rows are skipped and flagged.
- Confirm step: preview page is where upload-type (skip existing / update), password, and rename/delete options are chosen. These are heavy options; FLS likely wants far fewer.
- https://docs.moodle.org/en/Upload_users

### Google Workspace "Bulk update users"
- Flow: download blank CSV template from the dialog -> fill -> attach + Upload -> processing is **asynchronous**, progress in Tasks list, **email report** on completion.
- Format: template download, fixed columns (cannot add columns), explicit limits (35 MB, 150,000 rows), UTF-8 with BOM note.
- Errors: two tiers. Upload-time (file-level: empty file, wrong/missing headers, empty required cell, column count, too large) -> fix and re-upload. Post-processing log file (row-level: licences, invalid org unit, existing users).
- Partial import: yes, per-row; the log reports failures.
- Confirm step: none; no review screen. Create vs update decided by whether email exists.
- https://knowledge.workspace.google.com/admin/users/add-or-update-multiple-users-from-a-csv-file

### Shopify product CSV import
- Flow: download sample CSV, upload, one checkbox ("Overwrite products with matching handles"), import.
- Format: sample file; docs enumerate required columns and encoding (UTF-8, LF).
- Errors: file-level failures with a message naming which related columns need values; some rows (partly filled packed products) are just not imported.
- Partial import: yes, per product. Overwrite semantics are documented (blank cell overwrites; missing column leaves untouched).
- https://help.shopify.com/en/manual/products/import-export/using-csv

### HubSpot import
- Flow: choose object/method (create, update, both) -> upload or paste -> **map columns** -> configure (name, consent) -> Finish import -> review page with **status timeline and estimated completion**.
- Errors: caught at mapping step, "[x] errors" link opens a side panel with **Edit errored values** (replace value or "Don't import this value") before import starts.
- Pattern worth noting: inline fixing of bad values on the review step, side panel for error detail.
- https://knowledge.hubspot.com/import-and-export/import-objects

### Mailchimp audience import
- Flow is a stepper: upload (drop area or file picker) -> audience/options (update existing, tags) -> **match columns** -> status -> **Review and confirm** (click any step header to go back, "Complete Import").
- Result: email notification on completion; results page covers added/updated counts and syntax errors; **Undo import** exists.
- Duplicates are skipped silently by design; blank fields overwrite in update mode (a documented gotcha).
- https://mailchimp.com/help/import-contacts-mailchimp/

### Flatfile / OneSchema / Dromo / CSVBox (import widgets)
- Common widget flow: upload -> map columns -> **review/fix in an editable table** -> submit.
- Review table has filters: all / valid / invalid, and filter by specific error (Flatfile). Summary counts of valid vs invalid.
- Partial import is a configurable choice: OneSchema "accept clean rows only" modal at end of Review & Finalize; clean rows exported as `records`, rejected as `error_records`. Flatfile final screen offers "Discard x rows with issues. Submit the rest." or blocks submission when any invalid (setting). Dromo has options for unresolved errors and exporting errors.
- References: https://docs.oneschema.co/changelog/accept-clean-rows-only , https://docs.oneschema.co/changelog/accept-partial-imports , https://support.flatfile.com/articles/7763163677-importing-data-with-flatfile-overview , https://support.flatfile.com/en/articles/7873833-can-i-completely-disable-submission-if-there-are-any-invalid-records , https://developer.dromo.io/guides/exporting-errors (search snippets, UI labels not verified)

### GOV.UK Design System (file upload, error summary)
- File upload: visible label above input; error message above the input with hidden "Error:" prefix, linked by `aria-describedby`. Prescribes **specific messages per case**: no file chosen, wrong type (list accepted types), too large (state max size), empty file, upload failed (try again), wrong/modified template ("must use the template").
- Enhanced component (Frontend 5.9.0, Mar 2025; colours/states updated Feb 2026): JS turns the input into a button plus a **larger, always-visible drop zone** that reacts visually; `name`, `accept`, `multiple` stay on the input. Original component had no visible drop target.
- Error summary: at top of `main`, below breadcrumbs/back link, above h1; heading "There is a problem"; one link per error that targets the field (file upload links to the input); text identical to inline message; focus moved to it; `role="alert"`; page `<title>` prefixed "Error:".
- https://design-system.service.gov.uk/components/file-upload/ , https://design-system.service.gov.uk/components/error-summary/

### Not retrieved
- Canvas LMS SIS import (guide URL 404; known only from general knowledge: format-pick + file upload, then async batch with processing progress and a warnings/errors list; not verified).
- Microsoft 365 bulk add users (URL 404; not verified).
- Polaris DropZone, GitHub Primer, Atlassian drop zone: not verified.

## Synthesis for the FLS design

1. **Two-tier error model is universal**: file-level errors (wrong type, empty, size, missing/unknown headers, missing required columns) block the file and show on the upload screen with GOV.UK-style specific messages plus error summary; row-level errors show on the review step. (Google, GOV.UK)
2. **Format guide plus downloadable template on the upload screen**, listing required vs optional columns, encoding and size limit (Google, Shopify, Moodle docs). GOV.UK wants a specific "use the template" error.
3. **Review step before commit** with summary counts (valid / error / existing), filterable table or error-row list, row number + reason per error (Flatfile, OneSchema, Moodle preview). Moodle, Mailchimp, HubSpot, OneSchema all have an explicit confirm action; Google and Shopify do not.
4. **Partial import is the norm** (every product skips bad rows). Best practice is to make it explicit in the accept step: "Import N valid rows, skip M with errors" (OneSchema, Flatfile), and to offer the error rows for download.
5. **Progress**: large imports go async with status timeline / task list / email (HubSpot, Google, Mailchimp). For small educator imports, an inline HTMX-polled progress bar is sufficient; email is optional.
6. **Completion summary**: counts of added / updated / skipped / failed, per-row list of failures, link to next action (Moodle results table, Mailchimp results and undo). Undo is a differentiator but out of scope unless requested.
7. **Drop zone**: large, always visible, with a button fallback and keyboard/screen-reader access (GOV.UK enhanced component).
8. **Avoid** Moodle-style option overload on the preview page and mapping steps (HubSpot/Mailchimp/Flatfile) when the template has fixed columns.

status: ok
