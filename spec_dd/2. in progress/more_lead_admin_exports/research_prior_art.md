# Research: prior art for admin exports of Users and Applications

Topic: what has already been tried, here or elsewhere, and what happened.
Idea: export Users and Applications (including anonymous ones) through the admin interface; an application export carries the full application form.

Limit: this worker had no shell, so `git log --oneline --all | grep ...` was NOT run. The spec_dd tree and the code stand in for history. The orchestrator can run the git grep if it wants commit-level history.

## 1. Here: no earlier "lead admin exports" spec exists

No directory under `spec_dd/` is named for lead or admin exports, and `roadmap.md` has no export item (its only "export" hit is an unrelated test-fixture re-export, plus "Calendar export" under out-of-scope). The `more_lead_admin_exports` name is the only trace of "lead". The earlier work that matters is below.

### 1a. Shipped: the admin CSV export machinery (from `referal_tracking`, 2026-09-10)

- Built and QA'd in `spec_dd/3. done/2026-09-10_18:18_referal_tracking/` (see `upgrade_notes.md` section "Admin CSV exports run on django-import-export", `qa_report.md` section 8 "CSV export - pass").
- It is the only admin export in use. Code:
  - `freedom_ls/site_aware_models/admin.py`: `SiteAwareExportModelAdmin(ExportActionMixin, SiteAwareModelAdmin)`. It gives a bulk "Export selected" action plus a changelist "Export" button that downloads the whole filtered list. Download is immediate (`skip_export_form = True`, `skip_export_form_from_action = True`). The detail-page export button is off (`show_change_form_export = False`) because it posts to the change view and denies users without change permission. Export is gated on view permission (`has_export_permission` returns `has_view_permission`), because the package default is "any staff user".
  - `freedom_ls/site_aware_models/admin_exports.py`: `FormulaSafeCSV` (the only format, fixed in code so a downstream `IMPORT_EXPORT_FORMATS` cannot bypass escaping), `IsoDateTimeWidget` / `IsoDateWidget`, and `SiteAwareModelResource` (drops the `site` column, ISO dates).
  - `freedom_ls/base/csv_safety.py`: `escape_csv_formula` (prefixes `'` on a leading `= + - @ \t \r`) and the UTF-8 BOM.
  - Example resources: `freedom_ls/referral_tracking/resources.py` shows the idiom of swapping an FK pk for a readable value (`ForeignKeyWidget(user_model, "email")`).
  - Dependency: `django-import-export>=4.4.1` in `pyproject.toml`.
- Downstream cost recorded in upgrade notes: `"import_export"` must be in `INSTALLED_APPS` after `unfold.contrib.import_export` or the changelist raises `TemplateDoesNotExist`. The notes say "further FLS exports will use the same base". Already done, so new exports add no new setting.
- QA found: select-across ("All 1000 selected") exported 1000 rows; a filtered changelist exported only the filtered set; a field value `=1+1` came out escaped; with only view permission granted, export worked and there was no Add button.
- Wrinkle in the upgrade notes: there is no separate export permission, and superusers pass everything.

### 1b. Deliberately deferred: exporting applications

- `spec_dd/3. done/2026-10-08_09:35_course-applications-admin/`:
  - `idea.md` line 72: "No export. `SiteAwareExportModelAdmin` exists, but exporting applicant data wasn't asked for."
  - `2. plan.md` lines 66 and 99: "no export base", "No export, no review state, no notes...".
  - `research_application_changelist.md` section 5 and item 6: "Do NOT add ... CSV export."
  - `research_current_admin_state.md` line 48: no export exists for form_engine data; `SiteAwareExportModelAdmin` is there "if ever wanted".
  - `research_admin_answer_display.md` line 24 recommended a read-only computed "Responses" field via one helper that builds page / question / answer structure from a `FormProgress`, with "no custom view unless a print or export need appears later". That need has now appeared.
- Result built (code, `freedom_ls/course_applications/admin.py`): `CourseApplicationAdmin(SiteAwareModelAdmin)` and `AnonymousApplicantAdmin(SiteAwareModelAdmin)`, read-only. Both extend the plain base, not the export base. It uses `answers_context` from `freedom_ls/form_engine/admin.py` to render answers on the change page. That helper is the existing "full application form" reading code and the natural source for a flat export of answers.
- Search fields and `list_select_related = ["user", "anonymous_applicant", "course", "form_progress"]` are already set, so the export queryset has a tested relation set. `list_filter` has submitted/draft, email-verified, course, created-date range, which an Export button on the changelist would honour.

### 1c. Users admin has no export

- `freedom_ls/accounts/admin.py` `UserAdmin(SiteAwareModelAdmin)` (line 101) is a plain site-aware admin with no export. `USER_ERASURE_CASCADE_MODELS` (also in that module) is the existing register of models the user-erasure path cascades to, and `CourseApplication` / `AnonymousApplicant` add themselves to it. A new Users export touches personal data and should be checked against that erasure story.
- Only four classes in the code (`site_aware_models/admin.py`, `admin_exports.py`, `referral_tracking/admin.py` and `resources.py`) use the export base, so Users and Applications would be its first non-tracking uses.

### 1d. Application PII and site scoping (from `simple-application-forms`, 2026-09-10)

- `research_application_pii.md`: application-strategy forms are distinguishable by `strategy=FormStrategy.APPLICATION`; a reporting or export path should exclude/include by that field rather than re-deriving it (lines 124-128). Any export, digest or background hook "must filter `site_id=` explicitly" because a task has no request, and nothing enforces it generically (lines 298-302). An admin changelist export runs in a request, so the site-aware manager applies, but a streamed or queued export would not.
- File uploads (`QuestionAnswerFile`) sit behind `SuperuserOnlyAdmin` and a gated reviewer route; a flat CSV cannot carry file contents, so an export must decide to emit a link or filename or nothing.
- `AnonymousApplicant` model: has email, names, consent fields (`consent_ip_address`, `consented_at`), `claimed_at`, `claim_email_sent_at`, and an optional `user` link once claimed. `CourseApplication` has `user` OR `anonymous_applicant` (one-to-one). A claimed anonymous applicant therefore appears twice in a naive Users + Applications pair of exports; this needs one rule.

### 1e. Related export designs that were built or designed (reuse, do not duplicate)

- `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/research_csv_export.md`: a second, non-admin table-export hook for educator panels. Decisions to build to: declared export columns, same filter pipeline as the on-screen table minus pagination, always stream, `.iterator(chunk_size=...)` with explicit prefetch handling, formula escaping and BOM re-used (it re-implemented the five-line `escape_csv_formula`, later consolidated into `freedom_ls/base/csv_safety.py`).
- `spec_dd/2. in progress/educator-interface-8-bulk-operations/idea.md`: lists "Export beyond what spec 2's hook and spec 10's roster give" as out of scope, and cites an old TODO in `educator_interface/views.py` ("checkboxes and bulk actions", "export as csv"). That TODO (line 244 of `freedom_ls/educator_interface/views.py`, a bare `# TODO`) is still in the code; it concerns the educator UI, not the Django admin, so it is not this idea.
- `spec_dd/3. done/2026-08-21_20:12_basic_reports` and `educator-interface-10-reporting-dashboards` ship report outputs; their `research_known_complaints.md` and `research_reference_implementations.md` contain export-related complaints (not re-read in depth here).
- `spec_dd/3. done/2026-03-13_21:21_security-audit/research_gdpr.md` and `research_popia.md`: mention export in the data-subject-access sense (right of access / portability), a different purpose from an operator lead export, but they set expectations on who may download personal data.

### 1f. TODO comments about exports in code

- Grep of `freedom_ls/**/*.py` for TODO near "export" found none. The only export-adjacent TODO is the bare `# TODO` at `freedom_ls/educator_interface/views.py:244` (educator UI, see 1e). `freedom_ls/reports/signals.py:27` has a TODO about report-file retention (not relevant to CSV downloads, which are not stored).

## 2. Elsewhere: pitfalls teams hit with form-submission exports

(Web search was thin; sources below are what it returned. The project's own earlier research in 1b adds Wagtail, Typeform, django-forms-builder and django-fobi accounts in `spec_dd/3. done/2026-10-08_09:35_course-applications-admin/research_admin_answer_display.md`, lines 28-36.)

1. Renamed or removed form questions break the export's columns.
   - Renaming a field makes earlier answers vanish from the dashboard and export until the old name is restored; the data is not deleted. Source: https://support.paubox.com/kb/why-renaming-a-form-field-makes-prior-submission-data-inaccessible
   - SurveyCTO treats a rename as remove + add, so old answers have no column in the export: https://docs.surveycto.com/02-designing-forms/01-core-concepts/11.missing-data.html
   - ODK Central hides removed fields from export; a maintainer's workaround is to re-add the question: https://forum.getodk.org/t/responses-for-maintained-data-fields-reset-to-blank-na-after-form-definition-update/35998/3
   - JotForm: deleting a field deletes its submission data, and the advice is to download before editing: https://jotform.com/answers/2421404-how-to-edit-a-form-without-losing-any-data-
   - Implication: the "full application form" export must decide how to key columns (question id vs current text vs a snapshot) when a form's questions change between applications. Wagtail, Typeform and django-forms-builder (project research above) show the same complaint.
2. CSV formula injection: leading `= + - @ \t \r` in user-typed answers runs as a formula in Excel / Sheets. Already handled in FLS by `FormulaSafeCSV`; an answer export puts far more visitor-typed text in the file than the tracking exports did, so the risk is bigger.
3. Large exports and memory/timeouts: libraries that build the whole dataset in memory fail on big tables. General Django guidance is `QuerySet.iterator(chunk_size=...)`, which also drops prefetch unless a chunk size is given (Django docs https://docs.djangoproject.com/en/6.0/ref/models/querysets/#iterator, already cited in the educator-interface-2 research). Search did not surface a specific django-import-export issue; the admin export through the package builds a `tablib.Dataset` fully in memory, so the first thing to measure is the row count of the largest tenant. A general reference on iterating in chunks: https://element84.com/software-engineering/strategies-reducing-memory-usage-django-migrations/
4. Wide forms: one column per question means a form with many questions makes a very wide sheet; multi-select / multi-option answers need a joining rule; unanswered questions need a blank, not a missing column (Google Forms / Typeform notes in 1b).
5. Permission gap: the package default export permission is "any staff user" (fixed already in `SiteAwareExportModelAdmin`), but it is view-permission-gated, not a separate "export" permission, so anyone who can view the changelist can download every row.

## 3. Open points this research hands to the spec

- Whether Applications export is flat (one row per application with one column per question) or two files (applications + answers); the earlier admin work recommended one helper that builds page/question/answer structure from a `FormProgress` and reused it for display.
- How to key and order answer columns when applications for the same course span different form versions.
- Whether anonymous applications and claimed anonymous applications appear as one row and how the Users export treats applicants with no user.
- Whether the export needs a permission narrower than view (deferred in both earlier specs; PII research flagged applicant data as sensitive).
- Superuser-only status of file answers (`QuestionAnswerFileAdmin`): an export should not leak file content.

status: ok
