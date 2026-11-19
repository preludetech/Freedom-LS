# Research: known complaints about file uploads in HTMX panel and dialog forms

Scope: file field on a panel framework form action (inline panel and dialog), Django backend, HTMX.
Decided in `answers.md`: file input comes back empty on 422 with a "choose again" message on the field; current file name as link plus a Remove checkbox for optional fields (ClearableFileInput behaviour); Save disabled and relabelled "Uploading…" while in flight, no progress bar.

Evidence quality: web search was limited (4 searches, no page deep-reads). Items marked (sourced) are backed by a URL below; items marked (general) are well-known practice or my own reasoning and were not verified against a specific source. Treat (general) items as proposals to check, not findings.

## Summary table

| # | Complaint | Already addressed by decided design? | What the spec should add |
|---|-----------|--------------------------------------|--------------------------|
| 1 | Lost file after validation error | Partly. The choice is "ask again", which is the accepted cost; the message covers the "silent" part | Say the message appears only when a file was actually submitted; keep every other field value; focus the file field; do not stash |
| 2 | Unclear which file is stored | Yes (name + link) | Name must be the original basename, not the storage path; show "no file" state explicitly |
| 3 | Accidental removal | Partly | Remove is a checkbox applied on Save only (not instant); a 422 must not silently keep the checkbox ticked invisibly; define clear-plus-new-file behaviour |
| 4 | Double submit | Partly (Save disabled) | Disable must also cover Enter-key submit and the dialog's other buttons; re-enable on any non-success response |
| 5 | No feedback on slow uploads | Partly (label only) | Accept no progress bar, but specify behaviour on timeout/network error and on cancel/close during upload |
| 6 | Unhelpful size/type messages | No (framework leaves it to consumer) | Provide a documented example in the dev page with specific messages; `accept` attribute passthrough |
| 7 | 413 / 5xx from proxy shows raw page or nothing | No | Spec must define the non-422 error path in panels and dialogs |
| 8 | Dialog closes or loses state on error | Unknown; depends on existing modal code | Test that 422 re-render keeps the dialog open |
| 9 | Mobile pickers | No | `accept` and `capture` guidance; test on real device; HEIC note |
| 10 | Long filename truncation | No | CSS truncation with full name in title/text; test with long name |
| 11 | File input swapped away by HTMX (developer) | Decided as "empty on 422" so intentionally accepted | Must still add `hx-encoding="multipart/form-data"` (or `enctype`) on both shapes |

## Detail

### 1. Lost files after validation error
- (sourced) HTMX documents that a file input loses its selection when the form is re-rendered after a validation error. Its documented workarounds are `hx-preserve` on the input, or placing the input outside the swapped form and linking it with the `form` attribute. Source: https://htmx.org/examples/file-upload-input/ and https://four.htmx.org/patterns/forms/file-upload
- (sourced) WCAG 2.2 SC 3.3.7 Redundant Entry is the reason GOV.UK rebuilt its file upload component in March 2025. NSW guidance says to avoid making users re-upload files when correcting errors. Source: https://design-system.service.gov.uk/components/file-upload and https://designsystem.nsw.gov.au/components/file-upload/index.html
- Design consequence: the decided "choose again" design is the weakest option against 3.3.7. It is acceptable because it is explicit, but the spec should record this as a known trade-off and that the `hx-preserve` route (which keeps the browser's selection) was considered and not taken. Caution (general): `hx-preserve` keeps the chosen file but also keeps a stale file if the error was about that file, so it conflicts with the decided "empty with message" behaviour.
- Spec additions:
  - The "choose again" message appears only when the user had submitted a file. Wording is specific, for example "Your file was not saved. Choose it again."
  - The message is shown even when the file itself was valid but another field failed (the common case users find baffling).
  - All other fields keep their values; the form re-renders in place with the same target.
  - Error summary or focus moves to the first error. For panels, at minimum the field error is associated with the input (`aria-describedby`).

### 2. Unclear which file is currently stored
- (general) Bare browser "No file chosen" next to an existing stored file is a classic confusion: users think nothing is stored, or that the chosen file replaced it already.
- Decided design shows name as link. Spec additions:
  - Show the original user-facing filename (strip upload directory and any random suffix Django adds), not the storage path. Django's default `ClearableFileInput` prints the full `url` text, which is often ugly.
  - Label the picker as a replacement ("Change file") when a file exists.
  - Define the empty state (no stored file: no link, no Remove checkbox).

### 3. Accidental removal
- (general) Instant-delete links cause data loss; a checkbox applied on Save is safer.
- Decided design uses a checkbox, which is right. Spec additions:
  - Remove applies only on a successful Save, never immediately.
  - Django `ClearableFileInput` gotcha (general): if both a new file and Clear are submitted, Django treats it as a validation error for required fields and as "clear wins/new file wins" in a way that surprises people. The spec should state the expected outcome and test it.
  - After a 422, the Remove checkbox state should be re-rendered as submitted, so the user can see what will happen.
  - Remove is shown only when the field is optional (already decided).

### 4. Double submit
- (general) Slow uploads with no feedback lead to repeated clicks and duplicate records, especially for `CreateInstanceAction`.
- Disabling Save covers the button. Spec additions:
  - Use HTMX's `hx-disabled-elt` or `htmx-request` class, not a hand-rolled script, and make sure Save is re-enabled after any outcome including errors (see #7).
  - Pressing Enter in a text field can still submit; in-flight requests should be dropped or `hx-sync="this:drop"` used (general, verify against htmx 2 docs).
  - Cover the dialog's Cancel and close controls: define what closing during upload does (abort the request).
  - The label swap to "Uploading…" should not occur for forms with no file field (decided: they behave as today) and should only occur when a file is actually selected.

### 5. No feedback on large or slow uploads
- (general) The usual complaint is "did it work?" on mobile connections. A progress bar is out of scope, which is a reasonable decision.
- Spec additions: a text status with `aria-live` so screen readers hear "Uploading…"; define what happens on network failure or timeout (htmx fires a network-error event rather than a response, so no swap happens and Save would stay disabled forever unless handled; see #7).

### 6. Unhelpful size and type error messages
- (sourced) GOV.UK asks for specific messages per error state, for example one for "no file selected" and different ones for wrong type and too large. Source: https://design-system.service.gov.uk/components/file-upload
- (sourced) Queensland guidance separates failures into retry-upload and remove-upload actions. Source: https://www.designsystem.qld.gov.au/components/file-upload
- The framework does not own validation (settled), so this falls to consumers, but the spec can make it easy:
  - The dev reference page example should include a form with a size and a type check using specific messages that state the limit and the allowed types.
  - Pass the form field's `accept` attribute through the widget so the picker filters (this is a hint only, server validation still required).
  - Document that Django's default message "The submitted file is empty." and the `FILE_UPLOAD_MAX_MEMORY_SIZE` behaviour are not user-friendly.

### 7. 413 or 5xx from a proxy, and how HTMX surfaces it
- (sourced) A 413 is generated by the proxy or web server (nginx `client_max_body_size` defaults to 1m), usually before Django sees the request, so Django's form validation never runs and the body is the proxy's HTML error page. Source: https://fivenines.io/blog/request-entity-too-large/ and https://http.dev/413
- (sourced) HTMX does not swap 4xx and 5xx responses by default. In htmx 2 it fires `htmx:responseError`; network failures and timeouts fire `htmx:sendError` and `htmx:timeout`. In htmx 4 the names change to `htmx:response:error` and `htmx:error`. The behaviour can be changed via `htmx:beforeSwap` or `htmx.config.responseHandling`. Sources: https://four.htmx.org/reference/events/htmx-response-error and https://htmx.org/quirks/ (event names for htmx 2 are from general knowledge; confirm against the htmx 2 docs the project pins).
- Consequence in the panel framework: if 422 is already configured to swap, a 413 will silently do nothing. The user clicks Save, the button shows "Uploading…", then it returns to normal with no message. This is the worst complaint in the list because it looks like a hung or ignored click.
- Spec additions:
  - Define a generic non-422 error path: on `htmx:responseError`, `sendError` and `timeout`, re-enable Save and show an inline message in the form (or dialog) such as "The file could not be uploaded. It may be too large, or the connection failed. Try again."
  - Distinguish 413 specifically with a size message where possible.
  - Never swap a proxy HTML error page into the dialog or panel.
  - Ask deploy docs to set proxy body size at or above the Django upload limit (`DATA_UPLOAD_MAX_MEMORY_SIZE` does not govern files; `FILE_UPLOAD_MAX_MEMORY_SIZE` only governs memory versus temp file). A consumer-form size check is useless if the proxy limit is lower.
  - Test: a simulated 413 and a 500 in both inline and dialog shapes.
  - Check whether the framework already has a global error handler for panel requests, to avoid a second competing one.

### 8. Uploads in modals closing on error
- (general) Complaint pattern: dialog closes or resets on error so the user loses context. Existing `panel_framework/modal/form.html` behaviour on 422 should be checked (not examined in this research).
- Spec additions: test that a 422 keeps the dialog open with errors shown and focus preserved; dialog closes only on success. Pair with #7 so a non-422 error also keeps it open.

### 9. Mobile file pickers
- (general, unverified) On phones the picker offers camera, photo library and files. Complaints include HEIC images from iPhones being rejected by a type check, huge camera photos hitting size limits, and `accept="image/*"` hiding the Files option on some Android versions.
- Spec additions: dev page example should show `accept` usage; docs note that type checks should accept what the picker offers; do not set `capture` by default. Out of scope is resizing, so state the large-photo risk in the docs.

### 10. Filename truncation
- (general) Long names overflow narrow panels or the dialog and push Save off-screen, or are cut so the extension is invisible.
- Spec additions: wrap or truncate with CSS, keep the full name in the `title` attribute and link text, and add a test or dev-page example with a very long filename and a filename with unusual characters (escaped properly).

### 11. Developer complaints
- (sourced) Files are not sent unless the form is multipart; HTMX defaults to urlencoded. Fix with `hx-encoding="multipart/form-data"` on the form. Source: https://four.htmx.org/reference/attributes/hx-encoding/ and https://flaviocopes.com/courses/htmx/upload-a-file/
- (general) The other common Django mistake is forgetting `request.FILES` when building the form; the idea file already notes `get_form` uses `request.POST` only.
- Spec additions: pass `request.FILES` only when the form has a file field (preserves "forms without a file field behave as today"); set multipart encoding automatically from `form.is_multipart()` in both templates rather than per consumer; a framework test for each shape; keep the file-input swap behaviour explicit (the decision to empty it on 422 is consistent with swapping the whole form).

## Suggested acceptance items for the spec (derived)
1. A 422 re-render shows the "choose again" message only when a file was submitted, and keeps all other values.
2. Stored file shows its original name as a link; empty state is explicit; Remove is applied only on Save.
3. Save is disabled and labelled "Uploading…" only when a file is selected; it is always re-enabled after any response or network error.
4. Non-422 failures (413, 5xx, network, timeout) show an inline message in the panel or dialog and do not swap a raw error page.
5. Dialog stays open on 422 and on non-422 errors.
6. Multipart encoding is derived from `form.is_multipart()` for both inline and dialog shapes.
7. Dev page example includes specific size and type error messages, `accept`, a long filename, and the proxy body-size note.

## References
- https://htmx.org/examples/file-upload-input/
- https://four.htmx.org/patterns/forms/file-upload
- https://four.htmx.org/reference/attributes/hx-encoding/
- https://four.htmx.org/reference/events/htmx-response-error
- https://htmx.org/quirks/
- https://flaviocopes.com/courses/htmx/upload-a-file/
- https://design-system.service.gov.uk/components/file-upload
- https://designsystem.nsw.gov.au/components/file-upload/index.html
- https://www.designsystem.qld.gov.au/components/file-upload
- https://fivenines.io/blog/request-entity-too-large/
- https://http.dev/413

Not covered: Baymard, NN/g, StackOverflow and Django ticket tracker were not reached in this pass; no direct GOV.UK blog post on re-selecting files was found.

status: ok
