# Reference implementations: CSV learner import with preview, and bulk actions on tables

Extends sections 3 and 6 of `spec_dd/1. next/educator-interface-full-polish/comparable-systems-learner-management.md`
(which already covers: Moodle bulk "add to cohort" with no bulk remove, MDL-61007; Open edX batch box as the only
enrol UI; Docebo's 250-user background threshold). Not repeated here.

Confidence tags: [doc] fetched this session; [mem] from prior knowledge, not re-verified this session; [gap] not found.

## Findings first (what FLS should do)

1. **Persist the upload server-side between preview and confirm; carry only a token in the confirm form.** Both
   Moodle and django-import-export do this. Never round-trip the parsed rows through hidden fields or the session
   cookie. For FLS: store the raw file via the file-storage skill (or a small `ImportBatch` row), keyed by an
   unguessable id, scoped to site and uploading user, with an expiry. This also gives the "survives reload, Back
   works" the idea asks for: preview is `GET /import/<batch id>/preview`, not a POST response.
2. **Re-validate at commit; do not trust the preview.** Between preview and confirm, state can change (someone
   else adds the learner). django-import-export re-runs the whole import in the confirm step; the preview is only a
   dry run. FLS commit should re-classify each row through spec 7's add-learner path and report the final label, so
   a row that was "new account" in the preview and "already a member" at commit is reported honestly.
3. **One classification function, used for both preview and commit.** django-import-export's `dry_run` flag
   (same code path, no persistence, or rolled back in a transaction) is the model. Avoids a preview that disagrees
   with the commit. In FLS: `classify_row(row) -> RowOutcome` pure/read-only, and `apply_row(outcome)` that calls
   spec 7's path.
4. **Row labels: the closed set in the idea is right and richer than the libraries.** django-import-export has
   new / update / skip / delete / invalid / error. Moodle has created / updated / skipped(exists) / error. Neither
   distinguishes "existing account joined to this org" from "already a member"; FLS needs both because accounts are
   site-wide-by-email but membership is per organisation. Keep the label an enum on the row result, plus a separate
   free-text reason for errors only.
5. **Separate file-level errors from row-level errors.** Google Workspace rejects immediately on empty file, missing
   required column, or file too large (nothing is stored), and puts per-row failures in a log. Do the same: header
   problems (missing `email`, unknown headers if strict) block the upload step with one message; row problems never
   block other rows. This answers the "strict headers vs mapping" open question in favour of strict headers: none of
   the LMS systems below needs a mapping UI for a four-column file, and Google's answer to "which columns" is a
   downloadable template. Offer the template, reject unknown headers naming the unknown and the expected ones.
6. **Error rows downloadable as the original columns plus a reason column.** django-import-export builds exactly
   this (`failed_dataset`: the row values plus an "Error" column) [doc]. Google offers a downloadable log from the
   task list [doc]. Copy: the file the educator fixes and re-uploads should be the error file itself. Because FLS
   import is idempotent, re-uploading the *whole original file* is also safe, so the error download is a
   convenience, not a requirement.
7. **Never overwrite existing people.** Moodle's default upload type is "Add new only, skip existing users"; update
   modes are opt-in and give four "existing user details" sub-options [doc]. Google's default is the opposite
   (match on email, update the rest; blanks do not erase) [doc]. The idea's out-of-scope line (no updates) is the
   Moodle default taken as the only mode. Do not add a mode selector.
8. **Do not email new users from a background task as an afterthought; make it part of the per-row apply.** Google
   creates accounts with no welcome email [doc]; Moodle defers password generation and emails to cron [doc].
   Both give delayed or missing credentials. FLS's spec 7 path already sends the setup email per new account; keep
   it inside the same per-row unit so a retried task cannot send twice (see idempotency).
9. **Sync/async: no reference implementation documents a clean row threshold except Docebo (250 mass actions, from
   the earlier doc).** Google is always async (Tasks list plus email report, up to 150,000 rows, 35 MB) [doc].
   Canvas SIS is always async with a progress object [mem]. Django admin and django-import-export are synchronous by
   default; async is a third-party add-on [doc: not covered on the pages fetched]. So the two honest options are
   always-async or threshold-sync; a threshold has precedent only in Docebo. Recommendation unchanged from the
   idea (setting, low hundreds), but build the result page as one page that works in both modes (see item 10) so
   there is a single code path to test.
10. **One result page, status-driven.** Canvas models an import as an object with `workflow_state`, progress and
    warning/error lists that clients poll [mem]. Google exposes a task with a status [doc]. Copy: an `ImportBatch`
    row with `status` (uploaded, previewed, queued, running, done, failed), counts per label and the per-row results.
    The result page is a GET of that row; sync commits just arrive at `done` before the redirect. HTMX polling of a
    partial every few seconds while `queued/running`, stop on `done`. Email is optional extra, not the primary
    delivery (Google emails but also keeps the Tasks list).
11. **Partial commit is the norm; atomic-all is the exception.** django-import-export defaults to one transaction
    for the whole file, so one bad row aborts everything (`IMPORT_EXPORT_USE_TRANSACTIONS` defaults True) [doc].
    Moodle, Google and Canvas all apply valid rows and report the rest [doc/mem]. The idea's default (valid rows
    commit) matches the LMSs. Per-row `transaction.atomic()` so a failing row rolls back only itself.
12. **Guard rails against destructive imports are a real feature elsewhere (Canvas `change_threshold`), but FLS's
    import cannot delete or deactivate, so skip it.** Worth knowing: Canvas "full batch" mode deletes whatever is
    missing from the file, and its `change_threshold` aborts if too many deletions would occur [doc]. This is the
    failure mode behind "bulk without safe remove" complaints. FLS avoids it by design: import only adds.
13. **Bulk table actions: post the selected ids to a confirmation view, not a JS-only modal that acts directly.**
    Django admin's pattern: the changelist posts `action` plus the selected ids (`_selected_action`) and
    `select_across`; the action either renders a confirmation page or redirects to a custom view with the
    selection [doc]. The docs recommend the redirect-to-a-view style because format/field choices belong in a
    view, not a short function [doc]. In FLS the shared modal is that view: modal GET renders "N learners, what will
    happen", POST executes. Re-resolve the ids server-side on both requests, scoped to the site/organisation.
14. **Per-object permission checks, not queryset-level ones.** Django admin's `permissions=[...]` gates whether
    the action is *offered*, once, per request, not per object [doc]. That is the gap the idea names ("each object
    is checked server-side, not only the first"). Copy the gating for visibility; add a per-object check in the
    loop and report skipped-for-permission as its own count.
15. **Admin `delete_selected` bypasses `Model.delete()` via `QuerySet.delete()` [doc].** The same trap applies
    to `queryset.update()`: bulk actions that need `ensure_learner`, signals, setup emails or (later) audit entries
    must iterate and call the single-object service from specs 6 and 7. Do not use `queryset.update(...)` for
    deactivate/reactivate.
16. **Results after a bulk action are themselves actionable in Moodle** (select new / updated / all users from the
    results screen for messages, download, add to cohort) [doc]. Nice, but out of scope; note only as a possible
    follow-up (link the result page to the cohort).

## Per-implementation notes

### Moodle: `admin/tool/uploaduser` [doc: docs.moodle.org/Upload_users; source details [mem]]
- **Steps:** 1 upload file and choose encoding, delimiter, upload type; 2 preview (first rows of the file, with
  the per-row outcome computed) plus settings and default profile values; 3 results ("Upload users results"). Settings
  are on the same pages as the file.
- **Persistence:** the uploaded CSV is parsed by `csv_import_reader` into a temp store keyed by an import id (`iid`)
  that is passed as a hidden field to step 2 and 3; not the session, not the DB proper [mem].
- **Upload types** [doc]: add new only skip existing (default); add all appending a number to usernames; add new
  and update existing; update existing only. With update modes, "existing user details": no changes / override
  with file / override with file and defaults / fill in missing from file and defaults.
- **Matching:** on username; email matching only when `allowaccountssameemail` is off; duplicate emails blocked by
  default [doc].
- **Classification:** created, updated, skipped (already exists), error ("User not added - error") [doc]. Results
  screen counts: uploaded or updated users, weak passwords, errors [doc].
- **Errors:** shown inline per row in the results table; no downloadable error file [doc: none described].
  Typical causes: illegal username characters, invalid email, field longer than the DB column, trailing/non-breaking
  spaces, Excel mangling leading `-`/`+` [doc]. FLS lesson: trim and normalise whitespace and case in emails before
  matching; validate length against the model fields in the classify step so the failure is a reason, not a 500.
- **Async:** synchronous in one request; password generation and welcome emails deferred to cron [doc].
- **Idempotency:** re-running with "add new only" skips existing; this is the behaviour FLS wants.
- **Copy:** three-step flow, add-only default, skip-existing semantics, per-row outcome in the preview.
  **Avoid:** the matrix of upload type x existing-details x password options; it is the part users find confusing.
  FLS has one mode.

### Canvas: SIS import [doc: developerdocs.instructure.com sis csv; processing details [mem]]
- **Steps:** upload zip/CSV in Account admin (or API); the import is queued and processed by a background job;
  progress visible; completes with warnings and errors lists. Not a preview-first UI: there is no preview step,
  the batch mode and thresholds are the safety net instead [doc/mem].
- **Persistence:** the import is an object (SisBatch) with the attachment stored, `workflow_state`, `progress`,
  counts, `processing_warnings` and `processing_errors`; error attachment available [mem].
- **Row classification:** warnings (row skipped or partially applied) vs errors (import failed) [mem].
- **Idempotency:** the SIS id is the key; re-importing the same data is a no-op. Diffing mode compares to the last
  successful import with the same identifier and applies only differences; omitted objects are deleted by default
  [doc]. Passwords can be set only once; "sticky" fields keep UI edits unless Override is chosen [doc].
- **Safety:** `change_threshold` (1..100) aborts a batch that would delete more than N% [doc].
- **Copy:** import as a persisted object with a status; warning vs error distinction (a row that is already a
  member is a *skip*, not an *error*; keep it out of the error download). **Avoid:** batch deletion semantics;
  sticky-field machinery (FLS never overwrites at all).

### Docebo [doc: only partly found; threshold from the earlier research doc]
- Help-centre pages (360020084054 and similar) returned 403 to the fetcher; a search found a help article saying
  user import both creates and updates, with one row per user and one column per field, and that the
  Docebo-assigned user id cannot be combined with Username/User ID in the same file (importing error) [doc via search].
- Background threshold of 250 users for mass actions: taken from the earlier document; not re-verified here.
- [gap] Preview, error report, and whether blank cells overwrite: not found. Do not cite Docebo for those.
- API batch limits (not the admin UI): enrollment batch 300 rows per call, tracks batch 100 [community.docebo.com].
  Shows that even API designers cap batch size and make clients chunk.
- **Copy:** the threshold idea (sync below, background above) applied to *all* mass actions, not only import.

### Google Workspace: Bulk update users [doc]
- **Steps:** Directory > Users > Bulk update users; download blank CSV template (or the current user list as a
  CSV to edit); attach and upload; processing is a task shown in the Tasks list; email report on completion.
- **Persistence:** server-side task; no preview.
- **Validation split:** immediate errors on upload (empty file, missing required column, over 35 MB) vs a downloadable
  processing log (USER ALREADY EXISTS, INSUFFICIENT LICENSES, OU INVALID, PERMISSION DENIED) [doc].
- **Limits:** 35 MB, 150,000 records, 200 new licences per file [doc].
- **Matching:** by email; matched rows update other columns; blank optional cells do not erase data; `****` in the
  password column keeps the current one [doc].
- **Async:** always; new users may take up to 24 hours to appear [doc]. No welcome email on bulk-created accounts [doc].
- **Copy:** template download (the idea already has this), two-tier error handling, task status plus emailed report,
  "blank never erases". **Avoid:** no preview; credentials not sent; opaque processing delay with no row-level
  progress.

### Open edX: batch enrollment [doc: docs.openedx.org]
- **Steps:** one text box on the instructor dashboard Membership page (paste emails or usernames, comma or newline
  separated; CSV content is pasted, not uploaded), choose Enroll or Unenroll, tick Auto Enroll and Notify by
  email, submit. No preview.
- **Unregistered emails:** held as pre-enrollment, applied when that email registers and activates. The
  "learners who can enroll" report in Data Download lists the pending ones. Auto Enroll has no effect on Unenroll
  [doc].
- **Result:** a summary banner listing per-address outcomes [mem].
- **Async:** the docs steer large enrolments to the CSV-based or API routes; the box suits small batches [doc].
- **Copy:** one form handles both enrol and unenrol (every add has its remove). **Avoid:** pre-enrolment for
  unknown emails; FLS creates the account and sends a setup email instead, so no pending-enrolment state exists.

### django-import-export [doc: readthedocs admin_integration, import_workflow, installation; results.py source]
- **Steps (admin):** (1) choose file and format, submit; the file is written to temporary storage; (2) preview
  page shows the dry-run diff and any errors, with a Confirm form; (3) Confirm re-reads the stored file and imports
  for real, then deletes the temp file. `IMPORT_EXPORT_SKIP_ADMIN_CONFIRM` collapses it to one step.
- **Persistence:** `IMPORT_EXPORT_TMP_STORAGE_CLASS`: host temp files (default, dev only), Django cache, or Django
  storage (`MediaStorage`, e.g. S3 via the `STORAGES["import_export"]` entry). The confirm form carries the
  stored file's name (and original name and format) as hidden fields [mem]. Temp files are removed on success but
  may linger if users never confirm or an error occurs; docs suggest a cache expiry or cron cleanup [doc].
  Extra form fields must be declared on both `ImportForm` and `ConfirmImportForm` and passed with
  `get_confirm_form_initial()` or they are lost between requests [doc]. FLS lesson: anything the educator chose in step
  1 (the cohort on the cohort-tab entry point) must be in the stored batch, not only in the first request.
- **Row result types** (`RowResult.import_type`): `new`, `update`, `delete`, `skip`, `error`, `invalid` [doc,
  results.py]. Valid set is new/update/delete/skip. `error` = an exception during the row, traceback stored;
  `invalid` = validation failure (`ValidationError`), stored in `Result.invalid_rows` with values aligned to the
  diff headers. `Result.totals` is a counter per type. `Result.has_errors()` / `has_validation_errors()`.
  `Result.base_errors` for non-row failures.
- **Error reporting:** preview shows per-row errors or validation errors in tables; `failed_dataset` is the
  failed rows plus an "Error" column, which the admin can offer as a download [doc].
- **Transactions:** whole import in one transaction by default (`IMPORT_EXPORT_USE_TRANSACTIONS`, default True),
  and the dry run is the same code with persistence suppressed/rolled back [doc]. `raise_errors=False` by default so
  one bad row is recorded, not raised [doc].
- **Idempotency:** `skip_unchanged` / `skip_row()` compares the stored and imported instance to mark identical rows
  as skip [doc: `skip_row` seen, the option name not on the page]. Equivalent to FLS "already a member".
- **Async:** none built in; separate Celery/background packages exist [gap: not verified on the pages fetched].
- **Copy:** temp-storage-between-steps, same code for dry-run and commit, distinct invalid-vs-error, totals
  per type, failed-rows-plus-Error-column. **Avoid:** whole-file atomic default; leaving orphaned temp files without
  a documented cleanup; carrying the file name in a hidden field that the client can edit (validate that it belongs
  to the user and site; better an opaque id looked up server-side).
- **Do not depend on the library.** FLS rules (match by email, `ensure_learner`, never overwrite, site scoping,
  setup email) do not fit a model-resource mapping, and it is not a project dependency. Borrow the flow only.

### Django admin actions [doc: docs.djangoproject.com admin/actions]
- Action signature `(modeladmin, request, queryset)`; the changelist POST carries `action`, the selected ids
  (`_selected_action`), and `select_across` (all matching, not only the page) [mem for field names].
- Confirmation: render an intermediate template on first POST, re-POST with a `post` marker and the selection in
  hidden inputs; or redirect to a custom view with `ct` and `ids` in the query string, which the docs recommend
  for anything non-trivial [doc]. Query-string ids hit URL length limits for big selections [mem], which is the
  argument for FLS storing the selection (or the filter) server-side for large runs and passing a token.
- `permissions=[...]` decides if an action is shown, per request [doc]. `get_actions()` can drop actions per request.
- `QuerySet.update()` / `.delete()` skip per-object logic; iterate for anything with side effects [doc].
- `select_across` semantics: the client sends only the flag, and the server re-applies the *filter*, so the set
  may differ from what the user saw. FLS: show the count at confirm time and re-count at execute time; if they
  differ, show the new count rather than silently acting on more.
- **Copy:** actions as a registry of (name, label, permission, confirm view); the "offer only if allowed" hook.
  **Avoid:** queryset-wide permission check; update() shortcuts; ids in the query string for large sets.

## Idempotency patterns observed

| System | Key | Re-run result |
|---|---|---|
| Moodle (add new only) | username (or email) | existing skipped |
| Canvas SIS | `user_id` / SIS ids | no-op; diffing applies only changes |
| Google | email | updates matching, never deletes on blank |
| django-import-export | model identity fields | skip if unchanged (`skip_unchanged`) |
| FLS (idea) | normalised email within the site | "already a member" for every row |

For a background retry, make the per-row apply a pure function of (site, organisation, cohort, email): re-running
a half-finished task then yields "already a member" for the finished rows. Store each row's final label on the batch
row as it is applied; the task resumes from rows with no label. Send the setup email only on the transition that
created the account.

## Decisions this research supports for the open questions

- **Column mapping vs strict headers:** strict headers (case-insensitive, trimmed), reject unknown headers with
  the list of expected ones, template download. Evidence: Google and Canvas are strict-template; Moodle uses fixed
  field names; a mapping UI appears only for wide, free-form files (not the case here).
- **Threshold and delivery:** setting, default low hundreds; poll the status-driven result page; email optional.
  Precedent: Docebo (threshold), Google (task list plus email), Canvas (polled object).
- **Partial commit:** valid rows commit; per-row atomicity. django-import-export's atomic-whole-file is the outlier.
- **Preview storage:** server-side batch row plus stored file, token in the URL, expiry cleanup job (a gap
  django-import-export leaves open).
- **Bulk table actions:** confirm view per action receiving ids or a filter token, per-object permission check
  inside the loop, call the single-object services (no `update()`), pair every add with its remove (Moodle gap).

## Gaps

- Docebo help pages blocked (403): preview and error-report behaviour unknown; the 250 threshold is not re-verified.
- Canvas warnings/errors/progress details come from memory, not fetched docs.
- Moodle `iid` temp-store mechanism from memory; confirm in `admin/tool/uploaduser/index.php` and
  `lib/csvlib.class.php` if the spec relies on it.
- django-import-export hidden-field names and any async add-on not verified.

## References

- Moodle, Upload users: https://docs.moodle.org/en/Upload_users
- Canvas SIS CSV format: https://developerdocs.instructure.com/services/canvas/sis/file.sis_csv
- Google Workspace, add or update multiple users from a CSV: https://knowledge.workspace.google.com/admin/users/add-or-update-multiple-users-from-a-csv-file
- Open edX, manage course enrollments: https://docs.openedx.org/en/ulmo/educators/how-tos/student_management/manage_course_enrollments.html
- Open edX, enrollment (older docs): https://open-edx-building-and-running-a-course.readthedocs.io/en/latest/manage_live_course/course_enrollment.html
- django-import-export, admin integration: https://django-import-export.readthedocs.io/en/latest/admin_integration.html
- django-import-export, import workflow: https://django-import-export.readthedocs.io/en/latest/import_workflow.html
- django-import-export, installation/settings: https://django-import-export.readthedocs.io/en/latest/installation.html
- django-import-export, results.py: https://raw.githubusercontent.com/django-import-export/django-import-export/main/import_export/results.py
- Django admin actions: https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/
- Docebo API payload limits (community): https://community.docebo.com/integrations-apis-45/api-payload-limits-13510
- Docebo help (blocked to fetcher): https://help.docebo.com/hc/en-us/articles/360020128839

status: ok
