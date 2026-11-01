# Research: prior art for bulk operations (spec 8)

Question: what has already been tried, here or elsewhere, and what happened?

## Findings first

1. **Nothing was ever built here.** No earlier bulk import, CSV import, or bulk action exists in the repo. Spec 2 shipped only a seam (`BulkAction`, `Selection`, `resolve_selection`, a test-only stub). Specs 6 and 7 deliberately shipped none. No abandoned attempt was found in `spec_dd/`. The only prior art is design research and settled contracts, listed below.
2. **The contract that binds spec 8 is largely already written.** Spec 2 fixed the bulk-action flow and payload. Spec 7 fixed the per-row outcome labels and the add-learner path. Spec 5 fixed the permission. The idea restates some of it. The spec should cite these rather than redesign them (section "Binding decisions").
3. **Two gaps in the existing contract that spec 8 must close itself:**
   - Spec 2's `max_rows = 500` on `BulkAction` makes the framework return 422 above the cap. It never truncates and has no background route. The idea says "large selections go through the same background path". So spec 8 must change or extend that flow (a `BulkAction` that opts into background above a threshold). It cannot only register actions.
   - Spec 2 shipped `all_matching` as "422, Not supported yet". Spec 8 owns that branch if it wants "select all matching".
4. **External lessons that matter most:** (a) keep the uploaded file or its parsed rows somewhere every web process and the worker can reach (django-import-export's default host-local temp file breaks on multi-container deploys, and orphans files when users abandon the flow); (b) bind the commit to what was previewed, and re-check at commit, since the data can drift between preview and commit; (c) pair every bulk add with a remove; (d) email case and duplicate-email handling is a recurring bug source; (e) Excel encoding (UTF-8 BOM) mangles accented names.

## Here: what earlier specs decided that binds this one

### Roadmap (`spec_dd/1. next/roadmap.md`, "Educator interface rebuild")
- Spec 8 depends on 6 and 7, and runs beside 9. "Both reuse the account-creation path that 7 builds (match an existing user by email, or create one and send the setup email). Neither should write its own."
- Decision 1: deactivate, never delete, in the educator interface. So bulk "remove" actions are membership removal and deactivation only.
- Decision 2: an admin hands out their own level and below, within scope.
- Assumptions: no new dependencies; the denied experience is 404 for out-of-scope, 403 with message for a seen-but-forbidden action, and unusable controls are hidden, not disabled; everything is organisation-scoped and site-aware.
- Spec 11 (audit) depends on 6, 7, 9 and "records every action in specs 6 to 9", and spec 12 depends on 8. A per-object audit breakdown is therefore not available to spec 8, as the idea says.
- Spec 7 left an open unknown that affects bulk: whether a cohort move re-points the old progress record. Spec 7 resolved it (see below).

### Spec 2 (`3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/1. spec.md`, `research_row_selection_bulk_actions.md`)
- `BulkAction`: `label`, `action_name`, `max_rows = 500`, `confirm_template_name`, `has_permission(request)`, `execute(request, queryset)`. URL `<table panel base_url>/__actions/<action_name>`. `DataTablePanel.get_bulk_actions()` and `ListViewConfig.get_bulk_actions(request)` default to `[]`. Checkbox column, header checkbox, card checkboxes and bar render only when at least one registered action passes `has_permission(request)`.
- Form shape: the whole table sits in one `<form method="post">`. Rows post `name="keys"` and hidden `mode=keys`. Each action is a submit with `formaction` = action URL plus `{% querystring request.GET %}`.
- Flow: both POSTs check `has_permission` (403) and resolve the selection through `resolve_selection(panel, request, selection) -> QuerySet`. Keys outside the panel's scope drop silently. Count 0 or above `max_rows` is 422 naming the count and cap. "The framework never truncates, because a truncated request would act on fewer rows than the confirmation promised." First POST renders the confirm page or modal with the resolved count and `confirmed=1`. Second POST calls `execute` and redirects (`HX-Redirect` for htmx, 303 otherwise). 500 sits under `DATA_UPLOAD_MAX_NUMBER_FIELDS` (1000).
- Payload: `mode: "keys"` implemented. `mode: "all_matching"` (table's own prefixed `query_string` plus `excluded`) returns 422 "Not supported yet"; spec 8 adds the UI link and the branch. The query string is validated like a normal table GET.
- Selection clears on any `<key>-*` change and is never in the URL. Mobile cards get an always-visible leading checkbox. Header checkbox is native with `indeterminate` and no `aria-checked`. The JS-off path is a real form with a confirm page, which the research says is "exactly the two-step GET-then-POST-confirm pattern the CSV import already uses (upload, preview, result)".
- Research note: "Never trust posted pks as the action's scope." Per-object permission is required inside the queryset intersection or the loop, not only at the action gate. Matches the idea's "each object is checked server-side, not only the first".
- Research rejected: persisting selection across pages (extra complexity, no mockup support); long-press selection on mobile (not discoverable, not accessible); a serialised filter object for `all_matching` (use the table's own query string, re-derived server-side).
- CSV export (`research_csv_export.md`): stream with an `Echo` pseudo-buffer; formula-injection escaping (leading `=+-@\t\r` gets a `'`); UTF-8 BOM. `site_aware_models/admin_exports.py` has the project's only existing CSV hardening (`escape_csv_formula`, `FormulaSafeCSV`), tied to `django-import-export` and the Django admin, so spec 2 copied the five lines into a new `base/csv_safety.py` rather than import across apps. Spec 8's error-row CSV download should reuse that helper, not write another.

### Spec 5 (`3. done/2026-10-01_22:00_educator-interface-5-permissions/1. spec.md`)
- Matrix row: "CSV import, bulk actions" needs `bulk_manage_learners` (custom permission on `Learner`, organisation-level). Granted to `organisation_admin` and site admin, not to `cohort_admin` or `cohort_viewer`. The idea's "offered only to roles the spec 5 matrix allows for the single action" therefore has two layers: the umbrella `bulk_manage_learners` and the single action's own permission. The spec must say whether a user needs both. Cohort-table bulk actions (register for course) reach into cohort-level and registration permissions too.
- Spec 5's own scope note: it defines the capabilities and wires them only into actions that existed then; spec 8 wires `bulk_manage_learners`.

### Spec 6 (`3. done/2026-10-11_06:57_educator-interface-6-cohort-administration/1. spec.md`)
- "The selection column appears once spec 8 declares the cohort table's first `BulkAction`."
- Decision 3: an inactive cohort is read-only. Spec 7 enforces it in functions too (see below), so a bulk "add to cohort" must handle inactive destination cohorts per row, and a CSV `cohort` column naming an inactive cohort is a row error.
- Spec 6 created `register_cohort_for_course` and `unregister_cohort_from_course`, which fire a webhook only on a real change. The cohort-table bulk actions reuse them.

### Spec 7 (`3. done/2026-10-20_13:37_educator-interface-7-learner-administration/1. spec.md`, `research_lms_educator_ux.md`)
- Decision 11: "Row selection ships as a seam. No bulk actions here (the inherited `get_bulk_actions` returns `[]`)... Checkboxes appear when spec 8 registers its actions."
- `add_learners(organisation, entries: list[LearnerEntry], cohort=None) -> list[AddLearnerResult]`: raises `ValueError` before touching any entry for an inactive or foreign cohort; de-duplicates case-insensitively first; per entry runs `match_or_create_user`, `ensure_learner` (which reactivates), then membership; a new user gets the setup email. `AddLearnerResult.outcome` is `created | joined | reactivated | already_learner | invalid_email | email_in_use_elsewhere`; `cohort_outcome` is `added | already_member`. "Spec 8 reuses these labels row by row."
  - Gap to settle: the idea's preview labels are "new account, existing account joined to this organisation, already a member, reactivated, error". The spec 7 labels map onto them, but "email in use on another site" (`email_in_use_elsewhere`) is a spec 7 case that needs an explicit error reason in the preview. Also `add_learners` is one `transaction.atomic()` per call per its R2 ("Each runs in one `transaction.atomic()`"), which conflicts with the idea's default "valid rows commit, error rows are reported" if called with the whole file. Calling it per chunk or per row, or pre-filtering errors in the preview, resolves that.
- `match_or_create_user`: matches `email__iexact` across all sites because `User.email` is globally unique, never overwrites existing names, raises `EmailInUseOnAnotherSite`, creates users with an unusable password and a verified primary `EmailAddress`. The setup email is sent on `transaction.on_commit`, and `send_account_setup_email` works with no request: "with no request, both fall back to `context["user"].site`, so spec 8 can send from a background task." Resend is rate limited with a per-user `cache.add` guard (`SETUP_EMAIL_RESEND_SECONDS`, default 900), so a bulk "resend setup email" must report refused rows rather than fail the batch.
- The add-learners dialog takes at most 50 lines and says larger lists are spec 8's CSV import. So the dialog and the import coexist; 50 is the existing small-input ceiling.
- Consequence queries in `learner_management/queries.py` are "reused by single and bulk confirmations" (grants, progress impact), which supplies the idea's "same wording as the single actions".
- Cohort moves fire `cohort.member_removed` then `cohort.member_added` with a shared `move_id`; move is refused when repeated. Bulk "move" is not in the idea's list, which is consistent.
- All single actions are idempotent and return whether they changed anything, and webhooks fire only on change, so a re-run of a bulk action fires nothing.
- Spec 7's research (`research_lms_educator_ux.md`): top complaint in smaller LMSs is no bulk import; CSV creating duplicates instead of matching existing users (Moodle warns about it); Tutor LMS added a review step with checkboxes to exclude individual rows and it was "well-received". Idea does not offer per-row exclusion; it offers proceed-with-valid-only. Per-row exclusion is an unused alternative.

### Spec 9 (`3. done/2026-10-22_11:25_educator-interface-9-educator-administration/`)
- Reuses `match_or_create_user` and `send_account_setup_email` directly, not `add_learners` (its research table, row 8). Confirms the shared account-creation seam is `accounts.account_setup`.

### The comparable-systems research (`spec_dd/1. next/educator-interface-full-polish/comparable-systems-learner-management.md`)
- Section 3: CSV import is bulk-only everywhere. Docebo runs mass actions over 250 users as a background job (this repo's research; my web search found Docebo background jobs but not the 250 figure, so treat the number as unconfirmed). Open edX's batch enrolment box makes one learner a batch of one. "Bulk actions come in pairs where they are liked and alone where they are complained about": Moodle bulk add to cohort without remove (MDL-61007), no teacher bulk unenrol; TalentLMS pairs every add with a remove.
- Section 6: Moodle Upload users is the model (explicit mode and a preview); Docebo makes overwriting existing details an explicit opt-in. The FLS-specific additions: per-row outcome labels and a no-overwrite default, errors downloadable.
- Section 5 complaints: no bulk remove, duplicate accounts with no merge, rules that add but never remove. Not bulk-related but relevant: rules in `corporate-job-course-recommendations` run once per import, not per row.

### Spec 5 of the registration-rules effort (`spec_dd/1. next/corporate-job-course-recommendations-5-attribute-csv-import/idea.md`)
- A downstream consumer is already designed on top of spec 8's import flow: it reuses the page, the three steps, the labels, the background threshold, the result page and the error-row CSV. It writes `Learner` HR attributes only and never `User` details. It asks spec 8 to expose these as reusable: a generic import page and flow (upload, preview, confirm, result), per-row label and error model, a threshold/background commit path, the error CSV, and `bulk_manage_learners`-style permission gating. It also leaves open whether attributes are extra columns on the learner import. The spec 8 design should keep the flow generic enough that a second importer plugs in, without building the second importer (CLAUDE.md: do not build what is not requested).

### Background tasks (`3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/`, `upgrade_notes.md`, `2. plan.md`)
- Production runs `django-tasks-db==0.12.0` `DatabaseBackend` with a separate `python manage.py db_worker` process. Base settings, dev and the test suite keep `ImmediateBackend`, so tasks run inline and no queue row persists. It is a "hard operational dependency": with no worker, tasks sit in the database. Producers call `django.tasks` (`from django.tasks import task`), never a concrete backend.
- Existing example: webhook dispatch (`freedom_ls/webhooks/events.py`), with an idempotency guard (`WebhookDelivery` unique constraint) added because tasks can be retried.
- Implications for spec 8: tests run the "background" path inline, so a test that asserts the result page polls cannot see a real queued state without overriding `TASKS`; a task must take only serialisable arguments (ids, a stored batch reference), so the uploaded rows must be persisted somewhere before enqueue; and the task needs a result record the page can poll. `DatabaseBackend` task results exist (Task Results admin) but the QA report notes rows persist only with the durable backend.
- No earlier spec built a user-facing progress or result page for a task. Nothing to reuse for polling.

### Repo-wide search result
- Grep for bulk, CSV import and `import_export` across `spec_dd/` found no earlier user-import spec. `django-import-export` is used only for Django-admin exports (`site_aware_models/admin_exports.py`), per spec 2's research. Spec 2's research also records that the project chose not to depend on it from the panel framework.
- The old TODO in the educator views ("checkboxes and bulk actions", "export as csv") was removed when spec 1 deleted the old interface; spec 2 covers the export half. The "bulk-import dialog" mockup (`Educator Cohorts and Admin.dc.html`, and `design_screenshots/educator-cohorts-and-admin__08-bulk-import-modal.png`, mobile `m11-import-learners.png`) shows manual column mapping, which the idea has not accepted.

## Abandoned or rejected approaches (and why)

| Approach | Where | Why rejected |
|---|---|---|
| Truncating a large selection to the cap | Spec 2 | Would act on fewer rows than the confirmation promised. Spec 2 returns 422 instead. Spec 8 should route over-cap selections to background rather than truncate. |
| Selection that persists across pages | Spec 2 research | Complexity (restore state on every htmx swap) for a case not in the mockups. `all_matching` is the cross-page route. |
| Long-press mobile selection | Spec 2 research | Not discoverable or accessible. |
| Serialised filter object for "select all matching" | Spec 2 research | The table's own query string is re-derived server-side; nothing the client asserts about matches is trusted. |
| Import as a modal | Idea | Page chosen for reload and Back. |
| Overwriting existing users' details from the file | Idea, comparable-systems research | Out of scope; `User` is shared across organisations; spec 7 says names are never overwritten. |
| Name editing for any admin | Spec 7 decision 4 | `site_admin` only; email edits stay in the Django admin. Relevant: no bulk edit of names. |
| Tutor LMS-style per-row exclusion checkboxes in the preview | Spec 7 research | Not adopted in the idea (proceed with valid rows or fix the file). Open alternative. |

## Elsewhere: what went wrong and how it was fixed

Sources were public docs and trackers. Several searches returned nothing on the specific complaint; those gaps are stated.

### django-import-export (the Django reference for upload, preview, confirm)
- It stores the uploaded data in temporary storage after step 1 and reads it back after confirmation. Three storage mechanisms: host temp file (default, "suitable for development only"), Django cache, Django storage. Set with `IMPORT_EXPORT_TMP_STORAGE_CLASS`. "Use of temporary filesystem storage is not recommended for production sites."
- Failure modes documented: if a user does not finish the confirmation step, or the import errors, temporary resources may not be deleted, so the docs suggest a cache expiry or a cron job. On multi-server or container deployments the confirm request can land on a host without the file and fail with `FileNotFoundError` (stated by the search summary of the project's FAQ; the admin-integration page itself did not mention it). Stored data needs thought for sensitive content.
- Large uploads: the FAQ points to Celery with bulk imports for timeouts. `IMPORT_EXPORT_SKIP_ADMIN_CONFIRM` collapses to a single step, losing the preview.
- Bulk-import mode docs warn that a failed bulk batch can leave the import partly applied and that exceptions in bulk mode are not tied to a row, so validate before the bulk call.
- Lesson for FLS: persist the preview in a place the worker and every web process can read (database row or `fls-dev:file-storage` storage, not host temp), expire abandoned previews, and treat the stored payload as personal data (emails and names, `research_popia.md` in the security audit covers personal data handling).

### Design guidance on preview then commit
- Articles on safe bulk imports recommend staging rows at preview time, tying the commit to a batch id rather than re-reading the file, creating a new batch if the file or mapping changes, and checking for drift at commit. Unverified as case studies; they are design write-ups.
- Lesson: the preview is a snapshot. Between preview and confirm another educator may add the same person, or an account may be set up. The commit should re-evaluate each row through `add_learners`' own matching, and report any row whose outcome differs from its preview label. The idempotence rule in the idea ("already a member" on the second run) covers double-click and replay.

### Moodle Upload users
- Preview page carries an explicit mode and a "Prevent email address duplicates" option. Duplicate emails are blocked by default; creating accounts with a matching email is possible but "not recommended". `MDL-49280` added a config switch `allowaccountssameemail`.
- `MDL-53139`: an email differing only in letter case defeated duplicate detection in an "update existing users only" run. Lesson for FLS: `email__iexact`, which spec 7 already does, is correct; normalise at parse time and de-duplicate within the file case-insensitively, which `add_learners` also does.
- Docs advise testing a file of one record before a large upload (versions 3.2 and 3.3), which the preview step replaces.
- `MDL-61007` (bulk add to cohort without bulk remove), and recurring forum threads for bulk unenrol, are the "adds without removes" complaint already in the repo's research.
- I found no Moodle tracker issue describing the uploaduser preview itself timing out or running out of memory. Moodle issues I found on large exports (`MDL-34925`, `MDL-40094`, `MDL-40245`) show the general pattern: CSV memory stayed flat, time grew with row count (about 120 seconds at 14,400 users), and PHP's execution limit was hit by long jobs. Lesson: stream CSV, and do not rely on a request surviving a long job.

### Canvas
- A Canvas Ideas post describes a re-import with an old duplicate SIS ID: the new accounts were not created and an existing account was given an email address. There is no way to check beforehand whether a user already exists with that ID. Suggested workarounds are the SIS export report and "diffing mode". Lesson: matching key must be explicit and visible in the preview; FLS matches by email only, and the preview must say which existing account a row matched.
- Canvas SIS docs require UTF-8 and a header row, with quoted fields containing commas. Canvas community has a guide on creating UTF-8 CSVs from Excel (a known pain point).
- I found no source on how Canvas handles email case.

### Docebo
- Mass actions run as background jobs so the admin need not stay on the page. A Background jobs page lists pending and in-progress jobs and those ended in the past 13 days, with a log file of operations and errors for completed or failed jobs. A community answer says to wait for a large enrolment job to finish before re-enabling notifications, and there is an option "Send immediate notification digest on massive enrollment action". Lesson: bulk runs that send email (the setup email for every new account) are a known concern; FLS's setup email is sent per new user, and the result page should say how many were sent. The 250 threshold itself was not confirmed.

### CSV encoding and Excel
- Excel opens a UTF-8 file correctly only with a BOM; without one it uses the legacy code page, and accented names turn to mojibake. Python's `open()` keeps the BOM as part of the first field unless `encoding="utf-8-sig"`, which silently renames the first header (`﻿email`). Semicolon delimiters are common where the locale uses a decimal comma. One vendor changelog fixed an importer that parsed Latin-1 by honouring the BOM, defaulting to UTF-8 and adding a 10-row preview.
- Lesson for FLS: decode with `utf-8-sig`, strip and lowercase headers (the idea already says case-insensitive), sniff the delimiter or reject it clearly, and ship the template with a BOM (spec 2's export already prepends one). South African schools (the project's likely audience) open files in Excel, so the template should be tested there. FLS names with non-ASCII characters are the case that matters.
- Formula injection applies to the error-row CSV download too (OWASP); reuse spec 2's `base/csv_safety.py`.

## What this means for the open questions in the idea

- **Manual column mapping or strict headers.** Prior art: Moodle and Canvas are strict header formats with a template; django-import-export maps by header name. The mockup draws mapping. The binding cost is that mapping needs the file kept between steps and an extra step the idea's "three steps" does not have. Strict headers with a clear error is cheaper and fits the settled flow. This is evidence, not a decision.
- **Threshold and delivery.** Docebo's design is background job plus a jobs page. FLS has no jobs page; spec 8 would add the first user-facing task result. The idea's poll-or-email choice has no precedent in the repo. Polling needs a result record keyed by batch; email needs the same record plus a template. Both need the stored batch.
- **Partial commit or atomic.** Moodle's preview marks bad rows and imports the rest; django-import-export wraps the whole import in a transaction by default and warns that bulk mode can leave partial state. Spec 7's `add_learners` is atomic per call. Choosing per-row (or per-chunk) calls gives the idea's default (valid rows commit) with no partial-state surprise inside a row.

## References

Web:
- django-import-export, admin integration (temporary storage, `IMPORT_EXPORT_TMP_STORAGE_CLASS`, cleanup): https://django-import-export.readthedocs.io/en/stable/admin_integration.html
- django-import-export, FAQ (large files, Celery): https://github.com/django-import-export/django-import-export/blob/4.0.0-rc.1/docs/faq.rst
- django-import-export, bulk imports (partial failure, validation before bulk): https://django-import-export.readthedocs.io/en/4.0.8/bulk_import.html
- Safe bulk imports, preview then commit (design article): https://appmaster.io/blog/safe-bulk-imports-preview-validate-commit
- Designing scalable CSV importers (design article): https://mfyz.com/designing-scalable-csv-importers-what-a-good-importer-should-do/
- Moodle MDL-49280, duplicate email switch: https://tracker-old.moodle.org/browse/MDL-49280
- Moodle MDL-53139, email case and duplicate detection: https://tracker-old.moodle.org/browse/MDL-53139
- Moodle MDL-34925, bulk export performance: https://tracker-old.moodle.org/browse/MDL-34925
- Moodle MDL-40094, large log download memory: https://tracker-old.moodle.org/browse/MDL-40094
- Moodle MDL-40245, zip download execution limit: https://tracker-old.moodle.org/browse/MDL-40245
- Moodle docs, Upload users (preview settings): https://docs.moodle.org/29/en/Upload_users
- Moodle docs 3.3, uploaduser: https://docs.moodle.org/33/en/admin/tool/uploaduser/index
- Canvas Ideas, SIS import duplicate detection: https://community.canvaslms.com/t5/Canvas-Ideas/SIS-Running-SIS-Import-and-looking-for-duplicates/idi-p/563303
- Canvas, SIS CSV format: https://community.canvaslms.com/docs/DOC-3093
- Canvas, UTF-8 CSV from Excel: https://community.canvaslms.com/docs/DOC-3372
- Docebo, background jobs / mass actions: https://help.docebo.com/hc/en-us/articles/360020127579
- Docebo community, mass enrolment and notifications: https://community.docebo.com/product-q-a-7/issues-with-mass-enrollments-into-a-learning-plan-8249
- Excel UTF-8 BOM guidance: https://support.cayosoft.com/hc/en-us/articles/38401974026253-How-to-import-a-CSV-file-with-accents-characters-to-Microsoft-Excel
- Importer changelog (Latin-1 versus UTF-8, 10-row preview): https://www.acceleratorapp.co/en/changelog/csv-import-fix/
- OWASP, CSV injection: https://owasp.org/www-community/attacks/CSV_Injection

Local files read (all under `spec_dd/`):
- `2. in progress/educator-interface-8-bulk-operations/idea.md`
- `1. next/roadmap.md` (Educator interface rebuild)
- `1. next/educator-interface-full-polish/comparable-systems-learner-management.md`
- `1. next/corporate-job-course-recommendations-5-attribute-csv-import/idea.md`
- `3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/1. spec.md`, `research_row_selection_bulk_actions.md`, `research_csv_export.md`
- `3. done/2026-10-01_22:00_educator-interface-5-permissions/1. spec.md`
- `3. done/2026-10-11_06:57_educator-interface-6-cohort-administration/1. spec.md`
- `3. done/2026-10-20_13:37_educator-interface-7-learner-administration/1. spec.md`, `research_lms_educator_ux.md`
- `3. done/2026-10-22_11:25_educator-interface-9-educator-administration/research_codebase.md`
- `3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/` (`upgrade_notes.md`, `2. plan.md`, `qa_report.md`)

Not searched or not found: git history (cannot run git); a Moodle tracker issue on uploaduser preview memory or timeout; Canvas email-case behaviour; the Docebo 250-user figure; the django-import-export `FileNotFoundError` text on the docs page itself (only via a search summary of the project's documentation).

status: ok
