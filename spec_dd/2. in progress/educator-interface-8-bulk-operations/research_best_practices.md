# Research: best practices for CSV import and bulk actions

Scope: multi-step learner CSV import (upload, preview, confirm, result) and multi-select bulk actions, with large runs in a `django-tasks` background task. Stack: Django 6, PostgreSQL, HTMX. Recommendations are marked **Adopt**. Sources are in References. Only the CSV-injection point was checked against a live search. The rest is established practice plus the Django docs.

## 1. Recommendations at a glance

1. Parse with `csv` from the standard library after decoding with `utf-8-sig`. Fall back to a clear error, not a guess. Cap file size (about 1 MB) and row count (about 2,000, a setting). Reject unknown headers and offer no manual mapping.
2. Keep the uploaded file as a **staging row in the database** (a model with the file, the organisation, the uploader, a status and an expiry). Do not keep it in the session. Store only the parsed rows or the raw file, never the preview verdicts as truth.
3. **Re-validate every row at commit time** with the same function the preview used. The preview is advisory.
4. Commit **row by row**, each row in its own `transaction.atomic()` savepoint block. Valid rows commit and error rows are reported. This matches the idea's default.
5. Idempotency comes from the domain rule (match by email, "already a member"), plus a status guard on the staging row so a double-click or a retry cannot run twice.
6. Do not use `bulk_create` for the import path. The side effects (`ensure_learner`, setup email, membership) must run per row through spec 7's add-learner path.
7. Neutralise formula characters in the downloadable error CSV. Escape on **output** only, never on stored data.
8. Background: threshold as a setting (default 200). Poll from the result page with HTMX and also show the result page on reload. Skip email for the first version.
9. Bulk actions: every object is permission-checked server-side through the same function as the single action. Run per object and report "N done, M skipped with reasons".
10. Selection: ids by default. For "select all matching filter", resubmit the **filter parameters** and resolve the ids server-side at confirm time, then **snapshot the ids into the job** so the run is bounded and reportable.

## 2. CSV parsing safety

- **Encoding and BOM.** Excel's "CSV UTF-8" export prepends a BOM. Without handling it the first header reads `﻿email` and "email is required" fails confusingly. Decode with `utf-8-sig`. On `UnicodeDecodeError`, show "Save the file as CSV UTF-8". Do not auto-detect with chardet. Silent mojibake in names is worse than a clear error. **Adopt.**
- **Delimiters.** European Excel locales write semicolons. Use `csv.Sniffer` restricted to `,;\t` on the first header line only, or simply try the header line with each of those. If `email` is not found as a header after that, reject. Keep it small: do not support arbitrary delimiters.
- **Parse mode.** Use `csv.DictReader` over an `io.StringIO` of the decoded text, with `strict=True` so malformed quoting raises `csv.Error`, which you catch by type and turn into a message. Set `csv.field_size_limit` modestly. Excel files uploaded with a `.csv` name that are really `.xlsx` (a ZIP, starts with `PK`) should get a specific message.
- **Limits.** Enforce size twice. Check `UploadedFile.size` before reading, and set a Django `DATA_UPLOAD_MAX_MEMORY_SIZE` or per-form check. Cap rows and reject the whole file over the cap with the count in the message ("2,431 rows; the maximum is 2,000"). Do not silently truncate. Also cap the number of columns and field length (for example 254 for email, 150 for names) in row validation.
- **Header normalisation.** `strip()`, `casefold()`, and map spaces and hyphens to underscores. Accept `e-mail`, `Email Address`? Keep to an explicit short alias dict (`email`, `e-mail`, `email address`) rather than fuzzy matching. Duplicate headers after normalisation are a file error.
- **Strict headers versus mapping.** For five columns, **Adopt strict headers with a downloadable template and a message that lists the unknown headers and the expected ones.** Mapping UI is a second screen, extra state and extra tests, and the template removes most of the need. Ignore a `cohort` column on the cohort-implied entry point, but say so in the preview ("cohort column ignored"). Unknown extra columns: reject, because a typo such as `firstname` silently dropping names is the common failure.
- **Email normalisation.** `strip()`, validate with Django's `EmailValidator`, and lowercase the **whole address** for matching (the project's user lookup should say what it does; use the same normaliser as spec 7's add-learner path, not a new one). Use `__iexact` lookups or a normalised stored value. Strip zero-width characters and non-breaking spaces, which spreadsheets introduce.
- **Duplicates within the file.** Detect on the normalised email. First occurrence is processed, later ones get the label "duplicate of row N" (an error label, so it lands in the error file). Without this, two rows for the same new email race in the same commit. With the per-row path the second would just come out "already a member", but the preview would have lied by labelling both "new account".
- **Blank lines and trailing empty rows.** Skip rows where every cell is empty (Excel pads them) and do not count them.
- **Cohort column.** Match name within the organisation, case-insensitive and trimmed. Ambiguous or missing cohort is a row error, not a created cohort (the idea says import does not create cohorts).

## 3. CSV and formula injection in the error file

The error file is downloaded by an educator and opened in Excel, and it echoes attacker-controlled cells (names and emails come from a file someone else may have authored). A cell beginning with `=`, `+`, `-`, `@`, tab or carriage return is read as a formula, and wrapping the field in CSV quotes does not stop that because the reader strips the quotes. **Adopt:** write the error CSV through one helper that prefixes a single quote to any string cell whose first character is one of those (the OWASP approach; there is no universal fix, so keep this to the output boundary and apply it to header cells too). Apply to the reason column if it quotes user input. Because emails legitimately may start with `+`, that is one reason to escape only on export, never on the stored or parsed value. Use `csv.writer` with `QUOTE_ALL` plus a UTF-8 BOM on download so Excel renders accents. Send `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.

Escaping the preview HTML is covered by Django autoescape; do not mark row values `|safe`.

## 4. Keeping data between preview and confirm

| Option | Verdict |
|---|---|
| Session | Reject. Cookie-backed sessions overflow, DB sessions bloat, the data is tied to one browser session, and it breaks "survives reload, Back works" when the session rotates. Also unavailable to a background worker without extra plumbing. |
| Stored file only (via the file-storage skill) | Fine for the bytes, but you also need a place for the status, owner and expiry. |
| **DB staging row** (an `ImportJob`-style model, site-aware, with file, uploader, organisation, optional cohort, status, counts, expiry) | **Adopt.** It gives the page a URL (`imports/<id>/preview`), makes the background task pass only an id, stores the result summary and error rows for download, and supports expiry and cleanup. |

Details to adopt:
- Store the original file (private storage, not public media) and **re-parse at preview and at commit**, instead of storing a parsed blob as truth. Parsing 2,000 rows is cheap.
- Status lifecycle: `uploaded` → `previewed` → `running` → `done` or `failed`, with `expired` for an unconfirmed upload. Enforce transitions with a conditional update (`filter(pk=…, status="previewed").update(status="running")` and check the row count). That is the lock against double submit and against two educators confirming the same job.
- Expiry: 24 hours for unconfirmed uploads; delete the file on expiry. Personal data (names and emails) sits in that file, so also delete the stored file after the result has been built, keeping only counts and the error rows for a retention period. A periodic task or a management command does cleanup. Do not add logging (project rule).
- Scope the row to the organisation and the uploader's permission; every URL checks both (`fls-dev:multi-tenant`). A guessable integer id is acceptable only if the lookup is scoped, otherwise use a UUID.

## 5. Re-validation at commit time

State changes between preview and confirm: another educator adds the same person, someone deactivates a learner, a cohort is renamed or deleted, the uploader loses their role. **Adopt:**
- Commit re-runs the same `classify_row()` that the preview used, per row, immediately before acting. The label at commit can differ from the preview; the result page reports what actually happened. Say so in the preview ("counts may change if people are added before you confirm").
- Re-check the uploader's permission for the target organisation and cohort at commit (and again inside the background task, because it runs later and without a request).
- Single code path: preview is `classify_row()` with no writes; commit is `classify_row()` then `apply_row()`. This prevents the preview and the commit disagreeing in rules.

## 6. Idempotency

The domain rule already gives idempotency: match by email, never overwrite, "already a member" on rerun (matches the idea). Add two guards: (a) the status transition above, so a retried or double-clicked confirm does not start a second run; (b) database uniqueness on the membership and organisation-link rows, with `get_or_create` or catching `IntegrityError` specifically, to survive two concurrent runs. Do not rely on a client token.

## 7. Partial commit versus atomic

Established practice for user imports (Moodle, Docebo, most SaaS) is to commit the valid rows and report the rest, because one bad address in 500 should not block the intake and the educator can fix and re-upload only the error rows (which idempotency makes safe). Whole-batch atomic suits financial data where partial state is wrong; it is wrong here because a setup email is an external side effect that cannot roll back with the transaction. **Adopt the idea's default: partial commit.** Make each row its own `transaction.atomic()`, so a failure on row 37 rolls back only that row's writes. Send the setup email with `transaction.on_commit(...)` so it is only sent if that row's writes committed. Unexpected exceptions on a row (not validation errors) are recorded as an error row with a generic reason and do not abort the run; catch specific types (`ValidationError`, `IntegrityError`), and let programming errors fail the job loudly so they surface.

## 8. Django techniques

- **`transaction.atomic()` per row, not one outer transaction.** One outer transaction over hundreds of rows plus email sends holds locks and rolls back everything on one error. Per-row blocks inside no outer atomic are plain transactions; if called inside a test's wrapped transaction they become savepoints, which is fine. (Django docs: transactions, savepoints.)
- **`select_for_update()`.** Needed only where a read-then-write race matters. For "find user by email, else create", prefer `get_or_create` backed by a unique constraint (which retries via `IntegrityError` internally) over locking. Use `select_for_update()` on the staging row when claiming it, or use the conditional `update()` shown above, which needs no lock and is simpler. Never hold the lock across email sending.
- **`bulk_create`.** Fast (one query per batch) but does not call `save()`, does not send `pre_save`/`post_save` signals, and on PostgreSQL returns pks but cannot run model-level side effects. With the setup email, `ensure_learner`, and the multi-tenant site assignment all required per row, **do not use it for the import or for bulk actions**. 2,000 rows at a handful of queries each is seconds, which is acceptable inside a background task. Use `bulk_create(ignore_conflicts=True)` only for pure link rows (for example cohort membership) when no signals or audit exist, and only if spec 7's path allows it. Prefer to reuse spec 7's function unchanged.
- **Query shape.** Preload once: a dict of existing users by normalised email for the batch (one `filter(email__in=…)` with `select_related`/`prefetch_related` for memberships), and a dict of cohorts by lower-cased name. Use these for classification in the preview. At commit, re-check per row with a fresh query (see section 5) rather than the preloaded dict, or re-preload in chunks of about 100.
- **Emails.** Setup emails send through the existing mail backend inside `on_commit`; in the background task they are sent one by one. Do not send for rows that ended up "already a member".
- **Site awareness.** Every query goes through the site-aware managers; the background task must set or derive the site from the staging row, since there is no request.

## 9. Background execution, progress and thresholds

- **django-tasks.** Enqueue with only the staging-row id. The task loads the row, checks the status guard, processes rows, and writes progress and the final summary onto the row. Keep the task idempotent so a worker retry resumes safely: rows already processed become "already a member" on retry, and the result should be recomputed from the row records, not only incremented counters. Check how `support-concrete-project-deployment-3-background-tasks` runs workers in production before relying on retries.
- **Threshold.** Synchronous below about 100 to 200 rows is the common choice (requests must stay well inside typical proxy timeouts of 30 to 60 seconds; each new account involves an email). Default **200** in a setting, with the same setting reused for bulk actions on selected objects. Keep one code path: the sync path calls the same processing function as the task, just inline.
- **Progress delivery.** **Adopt polling** (HTMX `hx-trigger="every 2s"` on a progress fragment that swaps itself out for the final result when `status` is `done`, returning 286 or removing the trigger to stop polling). The page has its own URL, so reload and Back work, which is what the idea wants. Poll interval 2 to 3 seconds with a counter ("143 of 600"). Email as the delivery is extra scope (templates, a rule about whom to email, failure cases) and is not needed when the educator is watching a page; defer, and leave the result page reachable from the job URL. Show a failed state with a plain message if the task dies, and a stale-job indicator (no progress for several minutes).
- **Do not block the page on Python-side sleep or streaming.** Polling endpoints must be cheap: a single indexed row read, scoped to the organisation.

## 10. Bulk-action permission checks

- Offering the action only to permitted roles is UI. **The server must authorise each object**, for the following reason: a crafted POST can contain pks from another organisation or ones outside the educator's cohorts (an IDOR). **Adopt:** resolve the selected pks through the organisation-scoped, role-filtered queryset (the same one that renders the table, for example the educators' visible learners), and report any submitted pk that did not resolve as "skipped: not found or not allowed". Then per object call the same permission function as the single action (spec 5 matrix), because a role may be allowed for some cohorts only.
- Count honestly in the confirmation modal: "Remove 12 learners from Cohort A (3 are not members and will be skipped)". Compute the preview counts through the same per-object checks, but treat them as advisory like the import preview.
- Reuse the single-action service functions from specs 6 and 7 per object; do not reimplement rules in bulk code. Loop, each in its own `transaction.atomic()`, collect `(object, outcome, reason)`.
- Self-protection: skip or warn when the acting educator is in the selection for deactivate; this is a common bulk-action footgun. Whether to block it is a spec decision, but flag it.
- Return HTTP 422 for validation errors on the modal (project convention). Require POST and CSRF (already global).
- Cap the selection size server-side (for example 1,000 ids, a setting) to bound request payload and runtime.

## 11. Select-all-matching-filter semantics

Two designs: send the ids, or send the filter. Gmail and GitHub style: select the visible page, then offer "Select all N matching" which sets a flag.
- **Adopt:** the request carries either `ids=[…]` or `select_all=1` plus the **current filter query string** (search, cohort, status, and so on). The server re-resolves the filter through the same filtered queryset the table uses, scoped by organisation and permission. This avoids posting thousands of ids and avoids a stale client list.
- Race: rows can change between the page render and the confirm. Mitigate by showing the count in the confirmation modal, computed at that moment, and **submit that count as an expected count**. If the count at execution differs by more than zero, re-show the modal ("The list changed: now 41, was 40") instead of acting. That is cheap and avoids surprises on destructive actions.
- **Snapshot at execution.** When the action starts (sync or background), resolve the queryset once to a list of pks and store that on the job row (or in the task args if small), then process that list. This prevents a moving target (for example "deactivate all active" shrinking as you go, or paging drift) and makes the result report match exactly what was selected. A filter-only job that re-queries on each batch is the classic bug.
- The filter parameters must go through a form or whitelist, never straight into the ORM, so that crafted keys cannot filter on arbitrary fields.
- Because it relies on spec 2 shipping "select all matching filter", treat it as conditional. The ids-only path is the baseline.

## 12. Result and error-file download

- Result page: counts by label, the list of error rows (first 50 inline), a download link. Build the error CSV on request from stored error rows (original columns plus a `reason` column) and not as a stored file, so there is no second copy of personal data to clean up. Name it `import-errors-<date>.csv`.
- The error file keeps the original header names so the educator can fix and re-upload it directly. Do not add other columns before the reason column, and reason last.
- Download requires the same scoped lookup as any other page, and the data expires with the job.

## 13. Things that look appealing and should be avoided here

- Updating existing people from the file (already out of scope; also the main complaint in the comparable systems).
- Creating cohorts from unknown names in the `cohort` column.
- Session storage of rows, client-side-only parsing, or a single huge transaction.
- `bulk_create` for accounts.
- Email notification of results in v1.
- Fuzzy header matching or encoding auto-detection.

## References

- OWASP, CSV Injection: https://owasp.org/www-community/attacks/CSV_Injection
- Summary of trigger characters and "quoting is not enough": https://aident.ai/blog/csv-formula-injection-ai-exports
- Koha CSV injection bug report (DDE risk): https://bugs.koha-community.org/bugzilla3/show_bug.cgi?id=33339
- Python `csv` module (dialects, `strict`, Sniffer): https://docs.python.org/3/library/csv.html
- Python `utf-8-sig` codec: https://docs.python.org/3/library/codecs.html#module-encodings.utf_8_sig
- Django database transactions, `atomic`, `on_commit`: https://docs.djangoproject.com/en/stable/topics/db/transactions/
- Django `select_for_update`, `bulk_create` caveats, `get_or_create`: https://docs.djangoproject.com/en/stable/ref/models/querysets/
- Django file upload settings (`DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`): https://docs.djangoproject.com/en/stable/ref/settings/
- Django tasks framework (`django.tasks`) and the django-tasks backport: https://docs.djangoproject.com/en/stable/topics/tasks/ and https://github.com/RealOrangeOne/django-tasks
- HTMX polling pattern (`hx-trigger="every 2s"`, stopping with HTTP 286): https://htmx.org/docs/#polling
- Local: comparable-systems research (Moodle upload modes and preview, Docebo threshold) in `../educator-interface-full-polish/comparable-systems-learner-management.md`, sections 3 and 6.

status: ok
