# Research: Configurable Per-Course Application Forms

Research output for the "Applying for Courses" spec. Goal: decide how to model per-course application form schemas in FLS so site admins can configure which questions (text, options, file uploads, etc.) each course requires, support multi-step flows, and store applicant responses (including PII / documents).

Source idea: `spec_dd/1. next/applying-for-courses/0. idea.md`

Existing relevant code:
- `freedom_ls/content_engine/models.py` — `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`, `QuestionType`, `FormStrategy`, `File`, `file_upload_handler`
- `freedom_ls/student_progress/models.py` — `FormProgress`, `QuestionAnswer`

---

## 1. Reuse existing `Form` system vs separate `ApplicationForm` model

### What the existing `Form` system gives us

- `Form` (sits inside `content_engine`): a `TitledContent` + `MarkdownContent`, with a `strategy` field (`CATEGORY_VALUE_SUM` or `QUIZ`) and quiz settings. Loaded from disk via `file_path` on `BaseContent`.
- `FormPage` / `FormContent` / `FormQuestion` / `QuestionOption`: pages, intro text, questions, and option lists. Supports `multiple_choice`, `checkboxes`, `short_text`, `long_text`. Each question has an `order` and `required` flag.
- `FormProgress` / `QuestionAnswer` (in `student_progress`): one row per (user, form) attempt, plus one row per (attempt, question) with either `selected_options` (M2M to `QuestionOption`) or `text_answer`.
- All models inherit from `SiteAwareModel`, so site-scoping is already handled.

### What an application form needs that this does not have

| Need | Existing `Form` | Application requirement |
|---|---|---|
| Authoring surface | Filesystem (markdown / structured content), version-controlled | Admin UI built by site admins, no engineer / git push required |
| File upload questions | Not supported as a `QuestionType` | Required (ID docs etc.) |
| Scoring | Required (`strategy` is non-null) | Not required — applications are reviewed, not scored |
| Approval workflow | None | Must support `pending` / `approved` / `rejected` states with reviewer notes, audit trail |
| PII handling | Quiz answers — low sensitivity | High sensitivity (IDs, addresses, documents). Different retention / encryption / access-control needs |
| Multi-attempt vs one-active-application | Many `FormProgress` rows per (user, form) is fine for re-takes | Usually one in-progress + history of past applications per (user, course) |
| Partial / draft state | Implicit (a `FormProgress` with `completed_time__isnull=True` is a draft) | Same model is fine, but we want explicit "submitted" semantics distinct from "complete" |
| Course linkage | Forms are referenced from courses as content items | Application form is a precondition for *registering*, not a content item *inside* the course |

### Option A — extend `Form`

Add `FILE_UPLOAD` to `QuestionType`, allow `Form.strategy` to be nullable (or add an `APPLICATION` strategy that means "no scoring"), and introduce a separate `CourseApplication` model that wraps a `FormProgress` with approval state and ties it to a `Course`.

Pros:
- One question/answer rendering pipeline. New question types (file upload, date, etc.) benefit both systems.
- HTMX page-by-page navigation logic in `FormProgress.get_current_page_number` / `existing_answers_dict` / `save_answers` is reused as-is.
- `QuestionOption` already supports the option lists application forms need.
- Less duplicate code.

Cons:
- `content_engine` is currently *content-loaded-from-disk*. Forms have a `file_path` and are authored as files. If admins create application forms in the admin UI, those `Form` rows have no on-disk source — we either make `file_path` nullable / synthetic, or accept a hybrid model where some `Form`s are file-backed and some are admin-created. That muddies an otherwise clean invariant.
- `FormProgress` lives in `student_progress` and ties forms to course progress (`update_course_progress_on_completion` fires on save). Application submissions must NOT count toward course progress. We would need to either gate the progress hook on form type, or skip `FormProgress` and create a parallel response model — at which point the "reuse" is partial.
- PII handling: mixing low-sensitivity quiz answers and high-sensitivity application answers in the same `QuestionAnswer` table makes per-table retention policies, encryption-at-rest scoping (see `spec_dd/0. drafts/encryption-at-rest`), and audit logging harder.
- `Form` already carries quiz-specific fields (`quiz_show_incorrect`, `quiz_pass_percentage`, `strategy`). Forcing those to be null for application use clutters the model and the admin.
- Coupling: `content_engine` becomes responsible for an admin-management feature it was not designed for.

### Option B — separate `ApplicationForm` model

A new app (`course_applications` or similar) with its own models:
`ApplicationForm`, `ApplicationFormPage`, `ApplicationQuestion`, `ApplicationQuestionOption`, `CourseApplication` (the submission), `ApplicationAnswer`, `ApplicationFile`.

Pros:
- Clean separation of concerns: content (authored, file-backed) vs application (admin-built, DB-only).
- PII can be isolated in dedicated tables — easier to apply field-level encryption, separate backups, retention policies, and stricter admin permissions.
- No quiz / scoring fields polluting the schema.
- `ApplicationForm` admin UI is unconstrained by content-engine conventions (no `file_path`, no markdown loader).
- Approval workflow models (state machine, reviewer, decision audit) live with the application, not with course content.
- File-upload question type lives only where it is needed; we are not under pressure to retrofit it into the quiz/learning flow before it is requested.

Cons:
- Code duplication — two question/option/answer hierarchies, two render pipelines, two HTMX answer-saving paths.
- Two admin surfaces for admins to learn ("how do I add a question?" depends on context).
- Risk of divergence: improvements to one form system do not flow to the other.

### Option C — shared abstraction (rejected)

Extract a common `QuestionnaireSchema` package both apps depend on. Sounds clean, but:
- Premature: we have only two consumers. Per project conventions ("Don't build functionality that is not explicitly requested", "Don't create abstract base classes unless asked"), this is over-engineered today.
- Would force a refactor of `content_engine` that is out of scope for this spec.

### Recommendation for FLS

**Use Option B — a separate `ApplicationForm` model in a new `course_applications` app.**

Decisive reasons:

1. **Authoring model mismatch.** The existing `Form` is designed around file-backed content (`BaseContent.file_path`, the markdown loader, version control). Application forms are explicitly intended to be admin-built by non-engineers. Bolting that onto `content_engine` weakens its invariant that content is loaded from disk.
2. **PII isolation.** Application data (IDs, addresses, uploaded ID documents) has materially different retention, encryption, and access-control requirements than quiz answers. Putting it in a separate table makes it cheap to ship strict admin permissions and field-level protections later (see `spec_dd/0. drafts/encryption-at-rest`, `spec_dd/0. drafts/privacy-compliance`).
3. **Behavioural divergence.** `FormProgress` triggers `update_course_progress_on_completion`. Applications must not affect course progress. Adding conditionals to a shared model is fragile.
4. **No scoring semantics.** `Form.strategy` is required and meaningful; applications have no scoring concept. Making it optional muddies the model's contract.
5. **Approval workflow has its own home.** The state machine (`pending` / `under_review` / `approved` / `rejected`), reviewer notes, decision history, and the eventual hand-off to cohort enrolment are application concerns — they want to live next to the application data, not in `content_engine`.

Mitigations for the duplication cost:

- Reuse the *render conventions* (cotton components for short_text / long_text / radio / checkbox inputs) from the existing form templates. Copy the templates initially; extract shared partials only if and when a clear reuse pattern emerges.
- Keep field naming consistent (`question_<id>` POST keys, page `order`, `required`) so anyone familiar with one system can read the other.
- Reuse `File` from `content_engine` (or the same `file_upload_handler` pattern) for storing uploaded application documents — but with a separate `ApplicationFile` row pointing at the upload, so we can scope permissions and retention independently.

---

## 2. Schema-driven form patterns in Django

### 2a. JSON-schema in a `JSONField`

Store the whole schema (questions, types, options) as JSON on the `ApplicationForm` row. Render with a generic renderer that walks the JSON.

Pros: extremely flexible; no migrations when adding a new form; easy to copy/clone forms.
Cons: no FK integrity for answers (an answer references a question by string ID inside JSON); admin UI needs a custom JSON widget; querying / reporting across answers is awkward; schema migrations (renaming a question) are hand-rolled.
Verdict: tempting for prototypes, painful for PII data we will need to query, redact, and audit.

### 2b. EAV (Entity-Attribute-Value)

Generic `Attribute`, `Value` tables. Frequently regretted. Loses type safety, poor query performance, hard to validate.
Verdict: avoid.

### 2c. Dedicated `Question` / `Option` / `Answer` tables (relational schema)

What FLS already does for `Form`. Each question is a row, options are rows, answers reference question/option rows by FK.

Pros: full referential integrity, clean admin, good queries, easy to add per-question fields (help text, validation rules) later.
Cons: schema migrations when the *model* changes (not when the *form definition* changes — adding a new question is just a row).
Verdict: the right default for this use case. Matches the existing FLS pattern, and mirrors how the admin actually edits "a list of questions, each with options."

### 2d. Off-the-shelf packages

- **django-forms-builder** — https://github.com/stephenmcd/django-forms-builder. Admin-built forms, response storage, basic field types including `FILE`. Email notifications. Single-page forms (no native multi-step). Project is mature but lightly maintained. Uses its own admin — would clash with Unfold / `SiteAwareModelAdmin` conventions and is not multi-tenant aware. Could be a reference for question types and field validators, but adopting wholesale would fight FLS's site-aware patterns.
- **django-formtools** (official Django) — https://django-formtools.readthedocs.io/ — provides `FormWizard` / `SessionWizardView` / `CookieWizardView` for *static* multi-step forms defined in code. Useful as a UX pattern reference, not as a schema engine. Wizard state is in session/cookie, not in the DB, so it doesn't help with "save draft and come back next week."
- **django-survey-and-report** — https://github.com/Pierre-Sassoulas/django-survey. Admin-built surveys with multiple question types (text, radio, select, date), CSV/PDF export. Designed for surveys, no file-upload type, no approval workflow, not site-aware.
- **django-formidable** — https://github.com/peopledoc/django-formidable. Schema-driven forms with a JSON-based definition, REST API. Heavier dependency, ships its own React frontend, project activity is low.
- **django-dynamic-forms** — https://django-dynamic-forms.readthedocs.io/. Admin-built forms with action plugins on submit. Limited maintenance, no file uploads.
- **wagtail Form pages** — https://docs.wagtail.org/en/stable/reference/contrib/forms/index.html. Rich, but assumes Wagtail. Not applicable.

None of these line up with FLS's conventions (Unfold admin, `SiteAwareModel`, HTMX-first, no React) closely enough to adopt as-is. They are useful as references for question-type catalogues and validator design, not as dependencies.

**Conclusion for 2:** build a relational `ApplicationForm` / `ApplicationQuestion` schema in the same shape as the existing `Form` family. Do not introduce a third-party form-builder package.

---

## 3. File-upload UX in forms

### Server-side validation

- **Size**: enforce in two places — `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` for hard ceiling (https://docs.djangoproject.com/en/stable/ref/settings/#file-upload-max-memory-size), and a per-question `max_size_bytes` validator for the application-specific limit (e.g. ID docs 5 MB).
- **Type**: a per-question allowlist of MIME types AND file extensions. Validate by reading the file's magic bytes (e.g. `python-magic` — https://github.com/ahupp/python-magic — wraps libmagic) rather than trusting the browser-supplied `Content-Type`. For PDFs and images this is straightforward; reject anything outside the allowlist.
- **Filename**: never use the original filename in the storage path. The existing `file_upload_handler` already does this — uses the model `pk` plus extension. Reuse that pattern.
- **Storage location**: store under a path that is *not* publicly served. Either:
  - keep behind a Django view that checks permission per request (preferred for PII), OR
  - use a private S3 bucket with signed URLs.
  Public `MEDIA_URL` serving is unacceptable for ID documents.
- **Virus scanning**: the OWASP File Upload Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) recommends scanning anything user-uploaded. Practical options:
  - ClamAV via `clamd` socket, run in a Celery / background task after upload. Quarantine until clean.
  - Cloud equivalents (e.g. S3 + Lambda + a scanner).
  - For v1, an explicit "scan pending → clean / infected" status field on `ApplicationFile` lets us ship the model now and wire the scanner later.
- **Image stripping**: if we accept images, strip EXIF (location, device data) on upload — Pillow can do this in a few lines.

### Progressive upload with HTMX

- HTMX supports `hx-encoding="multipart/form-data"` (https://htmx.org/attributes/hx-encoding/) — POST a single field's worth of file data without submitting the whole form.
- Pattern: each file question is its own mini-form with `hx-post` to an `upload_application_file` endpoint that returns a partial showing "Uploaded: ID.pdf · Replace · Remove". The `ApplicationAnswer` row gets the file FK on success.
- Show progress with `htmx:xhr:progress` event (https://htmx.org/events/#htmx:xhr:progress) — a small Alpine component listening on this event can render a progress bar.
- Validate server-side and return HTTP 422 with a re-rendered field partial for errors (matches the FLS HTMX validation convention).

### Replacing a previously uploaded file

- The "Replace" link on the field partial swaps the partial back to a file-input form.
- On successful replacement: the new `ApplicationFile` row is created, the old row is *kept* (soft-deleted or marked `superseded=True`) so the audit trail of what the applicant submitted at each point survives. Hard-delete only when the application's retention period elapses.
- The `ApplicationAnswer.current_file` FK points at the latest active file. A reverse relation gives the history.

### CSRF and auth

- All upload endpoints require login and the global HTMX CSRF header (already set in `<body hx-headers>`).
- An applicant may only upload to / replace / view files attached to their own in-progress application. Reviewers (admin / educator role) get separate read-only access.

---

## 4. Multi-step / multi-page form data model

### Goal

User can navigate forward and backward across application steps without losing data, save a draft, leave, and come back days later to resume — all while we keep clear "submitted vs draft" semantics.

### Pattern: persistent draft, page-keyed saves

Mirror the existing `FormProgress` shape, with explicit application states:

```
CourseApplication
  user (FK), course (FK), application_form (FK)
  state: draft | submitted | under_review | approved | rejected | withdrawn
  created_at, updated_at, submitted_at, decided_at
  decision_by (FK user, nullable), decision_notes (text)

ApplicationAnswer
  application (FK CourseApplication), question (FK ApplicationQuestion)
  text_answer, selected_options (M2M), current_file (FK ApplicationFile, nullable)
  last_updated_at
  unique_together: (application, question)
```

State rules:
- `draft` is the only mutable state for the applicant. Each page submit upserts the relevant `ApplicationAnswer` rows (same pattern as `FormProgress.save_answers`).
- Transition `draft -> submitted` runs full validation across *all* pages, not just the current one. If validation fails on an earlier page, redirect there with errors.
- After `submitted`, applicant gets a read-only view; staff can transition to `under_review`, `approved`, or `rejected`.
- `withdrawn` lets the applicant abandon a submitted application without leaving it pending.

### Page navigation

- URL: `/courses/<slug>/apply/<page_number>/` (or step name).
- GET: render the page with current draft answers preloaded (reuse the `existing_answers_dict` pattern from `FormProgress`).
- POST: save this page's answers, then redirect to the next page (or to a review page on the last step).
- "Back" is just a link to the previous page URL — answers are persisted on every save, so navigation never loses data.
- Unique `(user, course)` constraint scoped to "active" applications only (use a partial unique index where `state IN ('draft','submitted','under_review')`) so a rejected applicant can re-apply later. Postgres supports partial unique indexes natively (https://www.postgresql.org/docs/current/indexes-partial.html).

### Validation strategy

- Per-page: only validate fields that belong to the current page on POST. Allows free navigation even when later pages are blank.
- On submit: run a full `is_complete()` check across all pages. The same method powers a "Review and submit" page that lists missing answers as links.
- Required-field validation lives on `ApplicationQuestion.required`, mirroring `FormQuestion.required`.

### Avoiding session-based wizards

`SessionWizardView` keeps state in session/cookie, which fails the "leave and come back next week" requirement (sessions expire and don't survive logout). DB-backed draft is the right pattern here. This matches how `FormProgress` already works for quizzes.

### Comparable patterns in the wild

- Django REST Framework's serializer-per-step is a code-side analogue, not a schema-driven one.
- The Django docs for form-tools wizards (https://django-formtools.readthedocs.io/en/latest/wizard.html) explicitly suggest moving to a model-backed workflow when persistence beyond a session is required.
- Government digital service forms (e.g. GOV.UK's "task list" pattern — https://design-system.service.gov.uk/patterns/task-list-pages/) are a useful UX reference: each step is independently completable, with a status indicator ("not started" / "in progress" / "complete") on a hub page. Worth adopting for the application landing view.

---

## Summary of recommendations

1. **Build `course_applications` as a new app** with its own models. Do not extend `content_engine.Form`. Reuse `File` / `file_upload_handler` patterns and the page/question/answer shape, but in dedicated tables.
2. **Schema model**: relational (`ApplicationForm` -> `ApplicationFormPage` -> `ApplicationQuestion` -> `ApplicationQuestionOption`), mirroring the existing form models. Avoid JSON-blob schemas and EAV.
3. **No third-party form-builder package** — none align with FLS's site-aware / Unfold / HTMX conventions closely enough to be worth the dependency.
4. **File uploads**: per-question type/size allowlist; magic-byte type detection; private storage behind permission-checked views; defer virus scanning to a background task with a `scan_status` field; keep history of replaced files for audit.
5. **Multi-step**: DB-backed draft via `CourseApplication` rows in `draft` state; per-page save with answers preloaded on GET; full validation only on final submit; partial unique index keyed on active states so rejected applicants can re-apply.
6. **Approval workflow**: explicit state field with reviewer + decision metadata; on approval, *do not* auto-enrol — surface a clear admin action ("Add to cohort & register for course") that uses the existing course-registration flow, matching the wording in `0. idea.md`.
