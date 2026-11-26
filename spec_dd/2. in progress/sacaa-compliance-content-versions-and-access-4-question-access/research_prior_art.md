# Research: prior art

Question: what has already been tried for this, here or elsewhere, and what happened?

Short answer: no question-viewing permission, role or per-view audit entry exists yet for question
banks. The nearest precedents are `conversation.viewed` (oversight), `download_cohort_report`,
the staff-roles work, the admin-removal spec, and `sacaa-compliance-4-attempt-review`. None of their QA runs found a
bug in the gating or audit write itself. Several of their decisions constrain this spec.
(Paths below are under `spec_dd/3. done/` unless stated.)

## 1. In this repo

### `2026-11-01_12:45_user-communication-ux-improve` (`conversation.viewed`)

- Decided (`1. spec.md` ~173-215, `2. plan.md` Slice 10): organisation and site admins get
  `freedom_ls_comms.view_conversation` on `organisation_admin` and `site_admin` (default grant, scoped to the
  learner). One `conversation.viewed` entry per open, written with `record_entry` in
  `panels/learner/messages.py`. Actor = viewer, target = the `Conversation` with label "Conversation
  with <educator>", `subjects=[learner]` (so it shows on the learner's History tab), organisation =
  learner's.
- Written only on the HTMX request that renders the thread; a request without the HX header is a
  404 and writes nothing. A separate paging endpoint (older messages) writes no entry. No dedupe:
  a second open writes a second entry. Participants' `last_read_at` is not touched. The vocabulary
  test (`audit_log/tests/invariants/test_vocabulary.py`) needed the noun `conversation` and verb
  `viewed` added to `NOUNS` and `VERBS`.
- Upgrade note: roles are read live, no migration; "a project that defines its own role config
  should decide whether its admin roles get this permission". This is the opposite default from this
  spec, where no existing role gets the permission.
- QA (`qa_report.md` §9 and §10): all oversight checks passed. One open added exactly one History row, a second open
  added a second row, superusers' opens were logged (banner "as a site admin"), a refused GET
  (403/404/400) left History unchanged, and the cursor paging endpoint wrote nothing. The only bug in that run (1 of 1 fixed)
  was unrelated: an HTMX 204 + `HX-Location` swap in the messaging composer. QA caveat: the audit log is not reset by
  scenario commands, so counts must be taken as deltas.
- Relevance: this is the pattern the idea copies. Its tests already prove "one open = one entry, no
  entry on refusal or paging". For this spec, the new case is a surface that has no instance (the
  course preview) and PDF downloads (a file served, not an HTMX render).

### `2026-10-01_22:00_educator-interface-5-permissions` and `2026-10-24_08:10_educator-interface-10-reporting-dashboards` (`download_cohort_report`)

- Decided: `download_cohort_report` is a custom permission in `Meta.permissions` on `Cohort`,
  checked with `can(user, "freedom_ls_learner_management.download_cohort_report", cohort)`. All four
  roles (site admin, org admin, cohort admin, cohort viewer) hold it, cohort-scoped. Generate and
  download views refuse without it (403/404). A viewer without it sees no Downloads panel but still sees the
  Cohort report body (`10/1. spec.md` ~74, 236, 262; `10/3. frontend_qa.md` 168-170).
- Constant pattern: `DOWNLOAD_COHORT_REPORT = "freedom_ls_learner_management.download_cohort_report"` beside
  the other capability constants (`10/2. plan.md:328`). The permission matrix test (`MATRIX`) gets a row per
  permission.
- Consequence for this idea: today the report body (on screen) is gated by `view_cohort` only. The permission
  only protects generate and download. This spec adds a second axis on the same report, so
  "can see the report" and "can see question detail in it" are independent. The existing
  precedent of a viewer seeing the body without the Downloads panel is the closest model for "rest
  of the report unchanged".
- QA of spec 10 (`qa_report.md`): 62 records, 0 bugs. Relevant observations: the report body is cached
  ("Figures as of ..." with Refresh; a plain reload within five minutes serves the cached version, 8.5a/8.5/8.6), so the
  cache-key concern in the idea is real. Confusion tables then showed aggregate counts only ("No per-learner wrong answers
  anywhere", 8.3). The idea says the panel now carries per-learner wrong answers, so
  that was added later and the QA there no longer matches. Reports for the same cohort accumulate (12 stored PDFs for one cohort),
  and the admin offers a Download link outside the educator permission check (6.6), which is an admin back
  door to the stored PDF that the admin-removal spec did not touch (`GeneratedReport` admin remains).
  Two quizzes in different courses titled "Voltage Quiz 01" showed identical headings with no course label.
- Upgrade note: a user with `view_cohort` but not `download_cohort_report` "can see a cohort but not
  generate or download its report".

### `2026-11-13_08:06_educator-interface-13-staff-roles` and `2026-11-21_09:55_educator-interface-refactor-3-staff`

- Staff-viewer roles were added in the permissions-module style, per cohort and per organisation. Roles on a `Cohort`
  never satisfy an organisation check (the idea's settled point). QA found 8 bugs (2 fixed, 6 unresolved at the time of the report), all about staff-page
  copy and stale state (B1 stale page after deactivating one's own role, B6 wording on role removal, B7 unlabelled
  role buttons), none about permission checks. Lesson: role-assignment UX copy
  and self-removal edge cases are where bugs appeared. Self-assignment edge cases may matter for the new role
  because an org admin may be able to grant it to themselves (check whether the assign permission is scoped
  per role, `educator-interface-5` `assign_*` permissions, upgrade notes line ~49).
- `educator-interface-5-permissions`: roles are read live (no migration); `FREEDOMLS_PERMISSIONS_MODULES`
  lets a site redefine roles; `validate_role_permissions` must be run after role changes. A new role in the
  fls permission module therefore needs to pass that command and the permission-matrix test
  (`2026-11-22_09:22_faster-test-runs-3-permission-matrix-test`).

### `2026-11-25_14:36_remove-unnecessary-admin-panel-functionality` (admin removal)

- Decided: unregister `Form`, `FormPage`, `FormQuestion`, `FormContent` and `QuestionOption` (and content and learner management
  admins) from the Django admin, wholesale. Make `TopicProgressAdmin`, `CourseProgressAdmin`,
  `CourseFormAttemptAdmin`, `FormProgressAdmin`, `QuestionAnswerAdmin` and `QuestionAnswerFileAdmin` view-only through
  `ReadOnlyAdminMixin` (now in `freedom_ls.site_aware_models.admin`, denies add/change/delete to superusers too). Keep the answers
  document on `FormProgressAdmin`.
- Important: `research`/`upgrade_notes` list `FormQuestion` and `QuestionOption` admins as **removed**
  there, yet this idea (written after) says both `FormQuestion` registrations and the `QuestionOption` page still exist. Check
  the live code (`freedom_ls/form_engine/admin.py`, `content_engine`): a rebase restore ("restore the `ReadOnlyAdminMixin` import
  lost in rebase", commit 8d4b528c8) shows that spec's work was reworked after merge, so confirm what is registered today before
  writing "remove" lines in the spec.
- Method that worked: a removal list in the upgrade notes (URL names that stop reversing, modules removed, `admin.E039`/`E040` for
  autocomplete/filter users of removed models), a "capabilities with no replacement yet" list, and a QA test that every removed
  admin URL returns 404 and no sidebar link points at a removed admin (QA test 1 and 2). The same checks fit this spec.
  Links from remaining admin pages to a removed admin must degrade to plain text (that spec did this for the course on the application page,
  test 8, passed). Pickers pointing at a removed admin broke and were replaced (learner email picker); `QuestionAnswer`
  admin lists show question text, which is the thing this spec must hide for quizzes.
- QA: 11 tests, all passed, no bugs. Full suite 20798 passed after rebase. Dev-visible note: `CourseApplication(85, <uuid>)` title
  from model `__str__` (unrelated).
- Residual back doors it left in place and its note on erasure: `UserAdmin` refuses erasing a user with form progress (a
  related guard exists).

### `sacaa-compliance-4-attempt-review` (done 2026-11-24)

- `research_prior_art.md` there (read it) already records that the educator attempt review leaves gating and audit to spec 5 of this
  effort, and that `_form_preview_context` (`educator_interface/panels/course/content_preview.py`) renders forms read-only with
  `show_answer_key=True`. That is the exact seam this spec gates. It also says the review keeps the summary separable from the question detail so a
  "score and pass/fail only" view can exist, and that an audit action code chosen here "should be one spec 5 can reuse".
- Key facts for this spec: the cohort report's quiz panel and `QuizAttempt` data are shared with the PDF
  (`reports/report_data.py`, `gather.py`). A gating change in the shared data builder reaches screen and PDF, and the cache.

## 2. Gaps no earlier spec covered

- No earlier spec gated read access to content (as opposed to actions) by a permission that no default role holds. All earlier
  permissions went to existing roles by default. This spec is the first with a deny-by-default role, so the permission matrix test, the role
  validation command and the `upgrade_notes` wording need an explicit "no existing role changes" statement.
- No earlier audit entry covers a file download or a lazily generated artifact. `conversation.viewed` is HTMX-render only. The PDF case
  (each download of a PDF carrying detail is audited, per answers.md) is new, and has no 404/refusal-writes-nothing precedent
  beyond the comms one.
- `GeneratedReport` admin Download link (above) can serve stored PDFs with question detail, outside both gates. Whether that is in scope
  is not stated in the idea ("answer views for QUIZ forms" only).

## 3. Elsewhere

No public, well-documented incident was found where an LMS admin back door or a report leaked an exam question bank. What exists is adjacent:

- Insider and admin risk, and audit trails, as general guidance: Questionmark on audit trails and admin tampering
  (https://www.questionmark.com/resources/blog/the-reality-of-exam-results-tampering-and-how-to-solve-it/), ManageEngine on privileged-user
  misuse in LMS settings (https://www.manageengine.com/log-management/cyber-security/edtech-education-security.html), and a commentary arguing the question
  bank is a security asset that should be monitored for abnormal access (https://cxotoday.com/expert-opinion/the-new-exam-leak-may-be-an-ai-prompt/).
- Unauthorised access to quiz answers through an API or IDOR rather than an admin: a write-up of a cross-student IDOR in Academy LMS leaking correct quiz
  answers (https://infosecwriteups.com/how-i-found-a-cross-student-idor-in-academy-lms-that-leaked-correct-quiz-answers-c68bfe06f3a0), and CVE-2024-1208
  for the LearnDash plugin exposing quiz questions via its API to unauthenticated users (https://feedly.com/cve/CVE-2024-1208). These support
  the idea's "every path, including APIs and exports, not only the UI" stance, and match the out-of-scope applications API note.
- Exam paper theft (not LMS back doors): police investigation of exam papers stolen in a cyber attack
  (https://feweek.co.uk/police-investigate-stolen-exam-papers-after-cyber-attack/), hacked VCE exams allegedly sold to students
  (https://ia.acs.org.au/article/2026/hacked-vce-exams-allegedly-sold-to-students.html), a USB-drive leak
  (https://searchinform.com/blog/2025/12/17/usb-insider-data-leak-exam-security-risk/). Not verified in depth; they are cited for
  context only and none implicates an in-product report or admin page.
- Canvas data-theft claim by ShinyHunters (unconfirmed); advisory guidance was to review admin audit logs and rotate keys. Not exam-content specific.

Conclusion for elsewhere: the practice of bank confidentiality (restricted role, access logging, monitoring for bulk access) is
common guidance, but I found no incident that settles a design choice here.

## 4. What the spec should take from this

1. Copy the `conversation.viewed` shape (actor, target, subjects, organisation; HX-only; no dedupe; superusers logged), and its test set
   (one entry per open, none on refusal, none on paging, entry visible on the History tab if a subject is a cohort).
2. Follow the `download_cohort_report` pattern for the constant, `Meta.permissions` and matrix row, but with no default holder.
3. Treat the cached report and the stored PDF as separate places where gated data persists; QA of the reporting spec proved the cache serves for five minutes
   and that PDFs accumulate and are also downloadable from the admin.
4. Verify what the admin still registers today before listing removals (the admin-removal spec's notes list `FormQuestion` and `QuestionOption` as already gone).
5. Reuse the admin-removal QA checks (removed URLs 404, no dead links, no broken pickers/filters) and its upgrade-note structure.

status: ok
