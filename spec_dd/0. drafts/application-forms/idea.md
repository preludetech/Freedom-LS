# Application Forms for Application-Gated Courses

Builds on top of **`applying-for-courses`** (`spec_dd/2. in progress/applying-for-courses`),
which ships the course-access backend, the `application_gated` access type, and a
bare **Apply** button that creates a standalone `CourseApplication` with **no form**. The
review/approval workflow (state machine, reviewer permissions, review UI) is a separate
follow-up, `application-review-ui` — this spec also leans on it for the FSM (see the dependency
note under "Seams already in place").

This follow-up adds the **application form**: an authored, multi-step questionnaire
(text, choice, checkbox, and file-upload questions) that an applicant fills in before
their application reaches a reviewer. The form is **content** — authored in
yaml/markdown and loaded through the same content pipeline as every other content type.

It only puts a form *in front of* the existing submission; the access backend is untouched, and
the review workflow it feeds is `application-review-ui`'s. Every seam these models need is left in
place by the predecessor specs (see "Seams already in place" below).

---

## What this adds

### 1. Form config models (content-loaded, mirror the `Form` family)

Mirror `Form → FormPage → FormQuestion → QuestionOption`
(`content_engine/models.py:302–451`) in shape and load through the **same content_save
pipeline** (new `content_type`s + Pydantic schema entries), keeping a single authoring
paradigm for all content-shaped data. All inherit `SiteAwareModel`; all carry the
`BaseContent` `file_path` so they are file-backed like other content.

```
ApplicationConfig          # content_type: APPLICATION_CONFIG. governs ≥1 course (per site)
  key              SlugField        (config identity; unique per site)
  title, intro     (markdown)
  # NO course FK — the config→course binding lives on ConfiguredCourse below, so one
  # config can be reused across courses that share an identical application process.
ConfiguredCourse           # join: binds a config to a course it governs
  config           FK ApplicationConfig (related_name="configured_courses")
  course           FK Course
  # unique_together = [site, course]: a course is governed by AT MOST ONE config.
  # (loader rejects a second config file that lists an already-bound course.)
ApplicationStep            # ordered steps within a config
  config           FK ApplicationConfig (related_name="steps")
  title, intro
  order            PositiveSmallInteger
ApplicationQuestion        # mirrors FormQuestion + a file type
  step             FK ApplicationStep (related_name="questions")
  prompt, help_text
  type             ApplicationQuestionType  (see below)
  required         bool
  order            PositiveSmallInteger
  # file-upload config (null unless type == FILE_UPLOAD):
  file_max_bytes   PositiveInteger | None
  file_mime_allowlist  JSON list[str] | None
  file_max_count   PositiveSmallInteger | None
ApplicationQuestionOption  # mirrors QuestionOption (no `correct` — applications aren't scored)
  question         FK ApplicationQuestion (related_name="options")
  text, value, order
```

**`ApplicationQuestionType`** (`TextChoices`) = the existing four plus one new value:
`SHORT_TEXT`, `LONG_TEXT`, `MULTIPLE_CHOICE`, `CHECKBOXES`, `FILE_UPLOAD`. The file type is
the one genuinely new question type (the existing `QuestionType` has no file option).

Content-loading detail:

- Add an `APPLICATION_CONFIG` content type and matching Pydantic schema classes in
  `content_engine/schema.py`, plus a `save_application_config()` analogous to
  `save_course()` (`content_save.py:342`). Because the loader lives in `content_engine`,
  the config models either (a) live in `content_engine`, or (b) the loader is extended to
  register the `course_applications` config models. **Decision:** the config models live in
  `course_applications`, and `content_save` is extended to dispatch the new content type to
  them. This keeps all application code in one app. The structure review must confirm this
  `content_engine → course_applications` *loader-only* edge is acceptable (it mirrors how
  the loader already knows about every content model); if not, fall back to (a). Flag for
  `/plan_structure_review`.
- **Config→course binding.** The `courses:` list resolves each slug to a `Course` on the
  current site and upserts a `ConfiguredCourse` row. The `[site, course]` uniqueness means a
  course governed by config A cannot also be claimed by config B: the loader **fails loud**
  (clear error naming both `file_path`s) rather than silently re-binding. A config with an
  empty/absent `courses:` list loads fine but governs nothing (useful while authoring).
- **Resolution at runtime is course → config**, never the reverse: a single helper
  `get_application_config(*, course) -> ApplicationConfig | None` (the only lookup any view,
  CTA, or the access backend uses) reads the `ConfiguredCourse` row for that course. No call
  site walks `config.configured_courses`. This is the seam that lets the cardinality change
  later (e.g. per-cohort configs) without touching callers.
- Example content file:

  ```yaml
  ---
  content_type: APPLICATION_CONFIG
  key: bootcamp-application            # config identity (unique per site)
  courses:                             # one or more course slugs that share this process
    - data-science-bootcamp
    - web-dev-bootcamp
  title: Apply to the Data Science Bootcamp
  steps:
    - title: About you
      questions:
        - {type: short_text, prompt: Full name, required: true}
        - {type: long_text,  prompt: Why this course?, required: true}
    - title: Documents
      questions:
        - type: file_upload
          prompt: Proof of ID
          required: true
          file_mime_allowlist: [application/pdf, image/png, image/jpeg]
          file_max_bytes: 5242880
          file_max_count: 1
  ---
  ```

### 2. Answer + file submission models (DB-only, relational)

The base spec already ships `CourseApplication`, `ApplicationNote`, and
`ApplicationStateTransition`. This adds the per-question answer rows and the file row,
and a `config` FK on `CourseApplication` pinning the application to the config that
governed the course at apply time.

```
CourseApplication                       # (base spec model) — ADD:
  config      FK ApplicationConfig | None   # pins the form version at apply time

ApplicationAnswer              # ≈ student_progress.QuestionAnswer (models.py:503)
  application      FK CourseApplication (related_name="answers")
  question         FK ApplicationQuestion
  selected_options M2M ApplicationQuestionOption   # choice/checkbox
  text_answer      TextField (blank, default="")    # text
  last_updated_time
  # unique_together = [application, question]   (same as QuestionAnswer)

ApplicationFile                # PII document, private storage
  answer        FK ApplicationAnswer (related_name="files")
  file          FileField(storage=<private>, upload_to=<non-guessable, pk-based>)
  original_name CharField        # for display only, never used in the storage path
  mime_type     CharField        # validated by magic bytes, not the browser
  size_bytes    PositiveInteger
  scan_status   CharField(choices: pending|clean|infected, default=pending)  # seam; no scanner here
  superseded    bool(default=False)  # replaced files kept for audit, not hard-deleted
  uploaded_at
```

- `ApplicationAnswer` is deliberately a 1:1 copy of the `QuestionAnswer` shape so the two
  systems read the same way. File answers carry no value on the answer row itself; the
  `ApplicationFile` rows hang off it.
- Keeping documents in their own table (not a column on the answer) gives the PII the
  isolation required: private storage, replace-history (`superseded`), targeted
  retention/deletion, and a future `scan_status` workflow — all without touching the
  textual answers.

### 3. Multi-step applicant UX

Per `research_multistep_ux.md` (DB-backed draft, one URL per step, GOV.UK check-answers):

- **Entry:** the gated-course CTA "Apply" resolves the course's config via
  `get_application_config(course=course)` (404 if none), then creates/loads the learner's
  active `CourseApplication` (draft) for that `(course, config)` and redirects to step 1.
  The stored `config` FK pins the application to the config that governed the course at
  apply time, so a later content edit re-binding the course doesn't reshape an in-flight draft.
  (In the base spec, with no form, "Apply" creates and submits the application directly.)
- **One real URL per step:** `GET/POST /applications/<id>/step/<order>/`. GET renders the
  step pre-populated from saved answers; POST validates only that step's fields, upserts the
  relevant `ApplicationAnswer` rows (mirroring `FormProgress.save_answers`,
  `models.py:226`), then 303-redirects to the next step or the review page. Browser back,
  refresh, bookmark all work; draft survives logout/device switch (it is on the user's
  account in the DB, not session/cookie).
- **HTMX inside a step only** (per project conventions): inline 422 validation, file upload,
  conditional reveal. Whole-step swaps are not used.
- **Progress indicator:** all steps visible, numbered + labelled, current highlighted,
  completed ticked; collapses to "Step N of M: <label>" on mobile.
- **Check your answers (final step):** GOV.UK summary cards per step; per-section "Change"
  link → `GET .../step/<order>/?return=review`, whose POST honours `?return=review` and
  redirects back to review without walking later steps. Optional unanswered questions show
  "Not provided". Submit button labelled "Submit application for <course>". Submit runs full
  cross-step required-answer validation; on failure, redirect to the first incomplete step
  with errors.
- **Lock on submit:** after `submitted`, the applicant view is read-only; the only re-edit
  path is a reviewer `request_changes` → `changes_requested`, which re-enables Change links
  and surfaces the reviewer's required message + a per-step indication of what to fix.

Once the form exists, the **review spec's** `submit` transition gains its
"validates required answers across all steps" behaviour, and `request_changes` /
`resubmit` become meaningful (there is now something for the applicant to correct). **The
state machine these reference comes from `application-review-ui`, not the base spec** — see the
dependency note under "Seams already in place" below.

### 4. File uploads

- **A question type** (`FILE_UPLOAD`), configured per question: `file_max_bytes`,
  `file_mime_allowlist`, `file_max_count`.
- **Upload endpoint** (HTMX): native `<input type="file">` → `hx-post` to an upload view
  that creates an `ApplicationFile`, returns a partial showing name/size + Replace/Remove.
  Validation: size (per-question + Django's `FILE_UPLOAD_MAX_MEMORY_SIZE`), MIME **by magic
  bytes** (not the browser `Content-Type`), extension allowlist, count. On failure return
  HTTP 422 with a re-rendered field partial.
- **Private storage + permission-checked serving.** No private media path exists today
  (`spec_research_codebase.md §11`); build it: a non-public storage location and a
  login-required serve view that checks the requester is the owning applicant **or** a
  reviewer with `view_application` on that application. Never serve documents from public
  `MEDIA_URL`. Storage path is pk/uuid-based; the original filename is display-only.
- **Replace** keeps the old row (`superseded=True`) for audit; hard-deletion happens only on
  retention/erasure.
- **Out of scope (seams kept):** virus scanning (`scan_status` field present, defaults
  `pending`, no scanner wired) and EXIF stripping.

### 5. Review UI additions

The **`application-review-ui` spec's** single-application review screen shows applicant identity,
state actions, internal notes, and the transition log. This adds the **answers + inline document
previews** (signed/permission-checked serve on click) to the main area of that screen. (Whichever of
the two follow-ups lands second renders the answers/documents in that screen; until then they are
viewable on whatever review surface the review spec has shipped.)

---

## Seams already in place

This work is purely additive, but its seams now come from **two** predecessor specs:

- From `applying-for-courses` (base): `CourseApplication` exists as a standalone model (user,
  course, timestamps); this adds the `config` FK and answer/file children. The access backend's
  "Apply now" CTA already routes to an application-entry view; this work changes that view to create
  a draft + redirect to step 1 instead of `get_or_create` + redirect to status.
- From `application-review-ui` (review): the `django-fsm-2` **state machine** — `submit`,
  `request_changes`, `resubmit`, etc. — and the `application_state_changed` signal. The base spec
  ships **no** state machine, so this work's `submit` validation, lock-on-submit, and
  request-changes re-edit path all hang off the review spec's FSM.
- `ApplicationFile.scan_status` is a new seam introduced here.
- `get_application_config(*, course)` is introduced here as the single course→config lookup.

> **Ordering dependency (new):** because the state machine moved out of the base spec, this spec
> depends on `application-review-ui` for the FSM. If `application-forms` lands **first**, it must
> introduce a minimal `draft`/`submitted` state itself (and `application-review-ui` then extends it
> with the reviewer transitions); if it lands second, it reuses the review spec's FSM unchanged.
> Confirm at this spec's planning time.

## Dependencies / settings new to this work

- Private file storage config for application documents (base settings + prod S3 private
  bucket/prefix; dev filesystem under a non-served path).
- `content_engine` Pydantic schema + `save_application_config()` content-loader dispatch.
- A library for magic-byte MIME sniffing (evaluate during this spec's research).

## Structure-review edges introduced here

- **Loader edge:** the content-loader (`content_engine`) dispatching the
  `APPLICATION_CONFIG` content type to `course_applications` models creates a loader-only
  `content_engine → course_applications` reference. Mirrors how the loader already knows
  every content model. If rejected, move the config models into `content_engine` (submission
  models stay in `course_applications`). Flag for `/plan_structure_review`.
