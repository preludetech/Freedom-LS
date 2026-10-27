# Research: UX patterns for exporting records from an admin interface

## Current project state (verified in code)

- `freedom_ls/site_aware_models/admin.py` defines `SiteAwareExportModelAdmin(ExportActionMixin, SiteAwareModelAdmin)` on django-import-export plus Unfold's `ExportForm`.
  - It gives an "Export" button on the changelist AND an admin action on selected rows.
  - `skip_export_form = True` and `skip_export_form_from_action = True`, so both download straight away with no confirm page.
  - Only one format is offered: `FormulaSafeCSV` (`freedom_ls/site_aware_models/admin_exports.py`). It escapes formula-leading cells and prefixes a UTF-8 BOM so Excel opens it.
  - `has_export_permission` is gated on view permission.
  - The detail-page export is off (`show_change_form_export = False`).
- `SiteAwareModelResource` drops the `site` column and renders dates as ISO 8601.
- It is used by four `referral_tracking` admins (`SignupAttributionAdmin`, `FirstTouchCountAdmin`, `ReferralCodeAdmin`, `ReferralCodeHitAdmin`), each with `resource_classes`.
- Headers are model field names. The class docstring says "headers ... name model fields", so they are field keys, not human labels.
- No background or emailed export exists.
- Users and Applications admins do not yet use this base. The simplest fit is to reuse `SiteAwareExportModelAdmin` plus a Resource for each.

## Common patterns and recommendations

1. **Selected rows versus "export all matching filters".**
   - The usual admin pattern offers both.
     - An action on ticked rows covers "these N people".
     - A changelist-level "Export" button covers the whole result set.
   - django-import-export's `ExportActionMixin` adds the row action. `ExportMixin` adds the button.
   - Caveat from the django-import-export docs: with the button, filtering is not automatic. The docs describe overriding `get_export_queryset()` as the way to limit what is exportable, and recommend it for multi-tenant setups. The project's existing pattern already provides both entry points.
   - Caveat: selecting many rows for the action can raise Django's `TooManyFieldsSent` (`DATA_UPLOAD_MAX_NUMBER_FIELDS`). The "select all N across pages" path is the safer route for big sets.
   - Recommendation: keep both, as the existing base does. Verify the button honours the active search and filters, and test that site scoping and view permission still hold.
   - Source: https://django-import-export.readthedocs.io/en/latest/admin_integration.html

2. **Format chooser.**
   - The package default is a confirm page where the user picks resource, fields and format, then downloads.
   - It can be skipped (`skip_export_form`) when only one format is offered.
   - The project deliberately offers CSV only and skips the form.
   - Recommendation: stay with a single CSV and no chooser. XLSX is the usual first addition, but it brings extra formula and injection handling. Add it only if requested.

3. **Column picker versus fixed columns.**
   - The package's confirm page offers a field checklist.
   - For the application form export, the columns depend on the form definition. This is the case for a dynamic set of columns, and a fixed column set cannot work.
   - Recommendation: fixed core columns (identity, status, timestamps) followed by one column per form question in form order, with no picker. That keeps a one-click flow. Revisit a picker only if the widths become unmanageable.

4. **Human-readable headers versus field keys.**
   - Admin exports meant for non-technical staff usually use readable labels (the question text or the model `verbose_name`).
   - The existing exports use field keys, but that suits technical, round-trippable data.
   - For per-question columns, use the question label, made unique if two questions share one (for example by appending the order number). A raw key would be meaningless to staff.
   - Recommendation: use labels for the new exports. Note that this departs from the "headers are not user-typed" assumption in `FormulaSafeCSV`. Question text is authored by staff, but headers should still be escaped if they can ever be visitor-influenced.

5. **Filename conventions.**
   - Common convention: `<entity>-<YYYYMMDD-HHMMSS>.csv`, with the site or tenant added when one account manages many.
   - The package's stock filenames are not documented on the pages I fetched, so this is unverified. Check `get_export_filename` in the installed version.
   - Recommendation: `<site-slug>-<entity>-<timestamp>.csv`. Include a form name for application exports, and use a timezone-explicit timestamp, matching the ISO choice already made.

6. **Large or slow exports.**
   - Typical pattern: a synchronous streamed download up to some thousands of rows. Beyond that, a background job with a notification or emailed link.
   - Third-party packages exist for Celery-based exports (django-import-export-celery, django-import-export-extensions), per https://django-import-export.readthedocs.io/en/latest/celery.html. I did not review their UX.
   - Recommendation: synchronous is enough unless production row counts are large. Before choosing, record the expected maximum row count and how many form questions an application can have. Make sure the queryset uses `select_related` and `prefetch_related`, because the answers cost the most queries. Background export is out of scope unless the spec asks for it.

7. **Rendering answers in a cell.**
   - Multi-select: join the chosen option labels with a delimiter such as `; ` or ` | `, using labels and not ids. Pick a delimiter that cannot occur in an option label.
   - File upload: a URL is the usual cell value (absolute, or a filename). The file itself is never embedded. Decide whether the URL needs authentication. Many admin exports give the file name only, which is safe, or an admin download link.
   - Long text: put the full text in the cell. CSV quoting handles embedded newlines. Do not truncate, because truncation loses data. Truncation belongs in the changelist, not in an export.
   - Empty or unanswered: an empty cell.
   - All string cells go through the formula escaping already in `FormulaSafeCSV`. This matters most here, since the answers are visitor-typed.

8. **Anonymous versus signed-in submissions.**
   - Common pattern: an explicit "Submitted by" column holding the account email, or a blank or "Anonymous" marker. Add a separate column for the contact details the visitor typed in the form.
   - Users should not have to infer anonymity from an empty cell.
   - Recommendation: include a "Signed in" yes/no column, or a user-email column that is blank for anonymous submissions. Include the email entered in the form when present, so anonymous applications remain contactable.
   - Check how the Applications model links to a user, and whether it is nullable. This is a code question for the spec, not answered here.

## Open questions for the spec

- Does the Applications admin exist yet? What is the model for anonymous submissions?
- Is the form definition versioned? If so, exports spanning versions need a union of columns.
- How is a file upload accessed, and what should the cell contain?
- Should the Users export include personal fields? That is a data-protection decision, since export gives wide access.

status: ok
