# Research: what in `form_engine` assumes a form is course content

Scope: given the decision to hang `CourseApplication` off an existing `Form` (via `FormProgress`/
`QuestionAnswer`) rather than build the `ApplicationConfig` family, what has to change for a `Form` to
be defined, addressed, answered and stored with no course anywhere near it.

Short answer: **less than the prior research feared.** `form_engine` itself (models, scoring,
signals, admin, factories) already has no course dependency at all — it was extracted in August 2026
specifically to make this possible, and its own tests already exercise a `FormProgress` with no
course in sight. The two real gaps are narrower than "form identity and a pluggable backend": (1)
`FormStrategy` has no non-scored member, so `FormProgress.score()` raises for anything but
`CATEGORY_VALUE_SUM`/`QUIZ`; (2) nothing gives a `Form` a URL, and the one admin gap that matters for
an admin-authored (not YAML-authored) form — slug generation on save — was never built because every
`Form` today comes through the YAML loader. Everything else that touches a form — the paging
machinery on `FormProgress`, the fill-page template, the progress signal — is course-agnostic already
or degrades safely when there is no course.

## 1. `FormStrategy` and the unscored case

`Form.strategy` (`freedom_ls/form_engine/models.py:48-51`) is a required `CharField` with
`choices=FormStrategy.choices` — no `null=True`, no `blank=True`, no default. `FormStrategy`
(`freedom_ls/form_engine/enums.py:25-29`) has exactly two members: `CATEGORY_VALUE_SUM`, `QUIZ`.
`FormProgress.score()` (`models.py:495-503`):

```python
def score(self):
    if self.form.strategy == FormStrategy.CATEGORY_VALUE_SUM:
        self.score_category_value_sum()
    elif self.form.strategy == FormStrategy.QUIZ:
        self.score_quiz()
    else:
        raise Exception(f"Unhandled Strategy: {self.form.strategy}")
```

`complete()` (`models.py:313-322`) always calls `self.score()`, and `complete()` is the only path that
sets `completed_time` (also enforced in `FormProgressAdmin.readonly_fields`, `admin.py:208`). So an
application `Form` needs a `strategy` value `score()` handles, or every submission 500s.

**Minimal correct change: add a third `FormStrategy` member (`UNSCORED`), not a nullable `strategy`.**
The field is already required and every reader already branches on the three-way choice; making it
nullable would still need a new branch wherever `None` reached it, so nullability buys nothing over a
new enum member and reopens a question (can `strategy` be blank on a quiz?) the model deliberately
never allowed. This is exactly the fix flagged in prior research as "still true and cheap to fix":
`spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/research_reuse_case.md` §5, reason 4.
`score()` needs one more branch (`elif self.form.strategy == FormStrategy.UNSCORED: return`, leaving
`scores` at its default `None`), and the enum has to be added in **two** places that must stay in sync
— `form_engine/enums.py` (the Django `TextChoices`) and `form_engine/schema.py:22-26` (the pydantic
`StrEnum` used for YAML-authored content, unaffected by this spec but still part of the enum's
contract).

Tracing every other reader confirms none of them need a change:

- **`quiz_percentage()`** (`models.py:221-241`) raises `ValueError` when `strategy != QUIZ` — already
  covers `UNSCORED` via the existing guard, no change.
- **`passed()`** (`models.py:243-249`) raises when `quiz_pass_percentage is None` — an `UNSCORED` form
  will always have this `None` (see below), so `passed()` is simply never called for one; nothing
  calls it without going through `quiz_verdict()` first.
- **`quiz_verdict()`** (`form_engine/queries.py:6-29`) already returns `None` for
  `form.strategy != FormStrategy.QUIZ` — covers `UNSCORED` for free.
- **`get_incorrect_quiz_answers()`** (`models.py:505-569`) already returns `[]` for
  `strategy != QUIZ` — covers `UNSCORED` for free.
- **The pydantic `Form` schema validator** (`schema.py:51-74`, `validate_quiz_fields`) only
  special-cases `FormStrategy.QUIZ` vs. everything else, requiring `quiz_show_incorrect` and
  `quiz_pass_percentage` be `None` for any non-quiz strategy. `UNSCORED` falls into the existing
  `else` branch with zero changes — the same rule that already applies to `CATEGORY_VALUE_SUM`. This
  schema only matters for YAML-authored forms; an admin-authored `UNSCORED` application form does not
  go through it at all (see §3), but the Django model has no equivalent guard, so nothing stops an
  admin setting `quiz_pass_percentage` on an `UNSCORED` form by mistake — worth a model-level
  `clean()` if this is meant to be enforced, but not required for the spec to work.
- **Templates.** `course_form_complete.html:8` branches `{% if form.strategy == "QUIZ" %} … {% else %}
  …`. The `else` branch already renders a plain "Form complete!" banner and only shows the
  `scores`/`show_scores` block (a leftover for `CATEGORY_VALUE_SUM`, `course_form_complete.html:184`)
  when `scores` is truthy — an `UNSCORED` form leaves `scores` `None`, so this template already
  degrades correctly with zero changes, *if* it is reused at all (see §4 on why it probably should
  not be, given review is admin-only).
- **`reports/indexes.py`** only buckets `Form` rows into `quiz_form_ids` when
  `item.strategy == FormStrategy.QUIZ` (`indexes.py:248`); everything else — `CATEGORY_VALUE_SUM` today,
  `UNSCORED` tomorrow — is already excluded from the quiz-only reporting path with no change needed.
  This module is unreachable for application forms anyway, because it walks
  `registration.course.viewable_items()` (`indexes.py:238`) and an application `Form` is never placed
  in a course (§3).

## 2. `FormProgress` does not need a `CourseProgress` or `CourseFormAttempt`

`FormProgress` is keyed `(user, form)` with no FK to anything course-shaped
(`form_engine/models.py:197-219`). The domain glossary already states the design intent verbatim:
`FormProgress` "knows nothing about courses, so a form can also be sat outside one"
(`.claude/skills/domain-glossary/SKILL.md:104`), and `learner_progress/signals.py`'s own docstring
names *an application form* as the exact example:

> "An attempt sat outside a course — a standalone survey, an application form — has no
> `CourseFormAttempt`, and there is no percentage anywhere for it to move. That is the whole reason
> the attempt layer lives in `form_engine`: completing one costs a single indexed lookup here and
> touches nothing else." — `freedom_ls/learner_progress/signals.py:106-109`

The receiver itself (`signals.py:96-119`) confirms this is not aspirational:

```python
@receiver(form_attempt_completed, dispatch_uid="learner_progress.form_attempt_completed")
def recalculate_course_progress_on_form_attempt(sender, attempt, **kwargs):
    course_attempt = (
        CourseFormAttempt.objects.filter(form_progress=attempt)
        .select_related("course_progress__course")
        .first()
    )
    if course_attempt is None:
        return
    recalculate_progress_percentage(course_attempt.course_progress)
```

A completed attempt with no `CourseFormAttempt` row (the CourseApplication case) hits `if
course_attempt is None: return` — a clean no-op, not a raise, not silent corruption of anything. This
receiver is the *only* place `form_attempt_completed` is consumed today (confirmed by
`form_engine/tests/test_import_independence.py`'s design note that `form_engine` never imports
`learner_progress`), so `FormProgress.complete()` for an application form sends the signal, one
indexed `SELECT` finds nothing, and returns.

The course-side helpers in `freedom_ls/learner_progress/attempts.py` — `get_or_create_incomplete`,
`get_latest_incomplete`, `finalise_stale_incomplete`, `completed_attempts` — all take a
`(course_progress, collection_item)` pair and are course-only by construction; the module docstring
says so explicitly ("Every course-side caller goes through here… Nothing outside this module may
resolve one from `(user, form)`", `attempts.py:10-13`). **None of them are usable for an application
form, and none need to be** — a `CourseApplication` flow creates its `FormProgress` directly
(`FormProgress.objects.create(user=…, form=…)`, mirroring what `get_or_create_incomplete` does at
`attempts.py:92-96` minus the `CourseFormAttempt` half) and resolves its own open attempt by
`(user, form)` — which is exactly the query `attempts.py`'s docstring says the course layer must
*not* use, precisely because that ambiguity does not exist outside a course: a learner has at most one
`CourseApplication` per `(user, course)` (`unique_application_per_site_user_course`,
`course_applications/models.py:46-51`), so at most one `Form` sitting to resolve.

`form_engine`'s own tests already prove this path works: `test_form_progress.py` and
`test_form_attempt_completed_signal.py` build `FormProgress` via `FormProgressFactory(user=…,
form=…)` with no `CourseProgress` anywhere in the test module, and `.complete()` scores and sends the
signal with no error (`form_engine/tests/test_form_attempt_completed_signal.py:36-61`).

## 3. Identity: `Form` has a slug, no route, and no admin-side slug generation

`Form` inherits `TitledContent` (`content_base/models.py:65-79`), which already carries
`slug = models.SlugField(max_length=500, …)` at `content_base/models.py:73-76` — **`Form` has had a
slug field since it existed**; §12 of the extraction spec is right that there is no *route*, not that
there is no field. `Form.Meta` already enforces `unique_form_slug_per_site`
(`form_engine/models.py:71-76`), the identical pattern `Topic` uses for
`unique_topic_slug_per_site` (`content_engine/models/topics.py:16-20`).

What is missing, confirmed by direct inspection:

- **No `form_engine/urls.py`.** `Glob freedom_ls/form_engine/**` lists every file in the app; there is
  no `urls.py`, no `views.py`. `Form` has no route at all.
- **No `Form.preview_url()`.** `Topic.preview_url()` is the only implementation in the codebase
  (`content_engine/models/topics.py:22-23`, `reverse("content_engine:topic_detail", …)`).
- **`get_unique_slug` (`site_aware_models/slugs.py:32-67`) is never called anywhere in `form_engine`.**
  It is called from the YAML loader (`content_engine/management/commands/content_save.py:270`,
  `fields["slug"] = get_unique_slug(model_class, site, base_slug, item.uuid)`) and from
  `OrganisationAdmin.save_model` (`organisations/admin.py:26-40`). Every `Form` today is created by
  that loader, so this gap has never mattered.
- **`FormAdmin` cannot create a `Form` with a usable slug today.** `FormAdmin.readonly_fields =
  ("slug",)` (`form_engine/admin.py:156`) and there is no `save_model` override — contrast
  `OrganisationAdmin.save_model` (`organisations/admin.py:26-40`), which sets
  `obj.slug = get_unique_slug(Organisation, site, slug_base_for(obj.name), existing_uuid=str(obj.pk))`
  when the slug is blank. `FormAdmin` has no equivalent, so an admin creating a `Form` by hand today
  saves it with `slug=""`; a second admin-created `Form` on the same site would violate
  `unique_form_slug_per_site`. **This is a concrete, previously-undocumented gap that this spec has
  to close if application forms are to be admin-authored** (which the "questions ship downstream, not
  in FLS" decision implies they will be, on whatever site deploys them) — either a `save_model`
  override on `FormAdmin` mirroring `OrganisationAdmin`'s, or an equivalent hook wherever application
  forms actually get authored.

One nuance worth flagging for whoever designs the applicant-facing route: the identity the *applicant*
needs is not necessarily `Form.slug`. `CourseApplication` already has its own addressable identity —
`course_applications:status` is keyed on `CourseApplication.pk` (`course_applications/urls.py`,
`views.py:65-81`) — and the natural place to hang a "fill in your application" route is off that pk
(or off the `FormProgress` it owns), the same way `course_applications:apply` and `:status` already
work, not off `Form.slug` directly. `Form.slug` / `preview_url()` matter for *authoring* identity (an
admin linking to or previewing a form) more than for the applicant runner's URL shape.

## 4. The runner view: what's course chrome vs. form-intrinsic

`form_fill_page` (`learner_interface/views.py:1037-1247`) context, split by what it actually needs:

| Context key | Source | Course chrome or form-intrinsic |
|---|---|---|
| `course` | param | **Course chrome** |
| `form`, `form_page` | `collection_item.child`, `form.pages.all()[n]` | Form-intrinsic |
| `form_progress` | `get_latest_incomplete(course_progress, collection_item)` | Form-intrinsic *value*, but resolved via a **course-only helper** (§2) |
| `current_page_num`, `total_pages` | form pagination | Form-intrinsic |
| `previous_page_url`, `has_next_page` (next url) | `reverse("learner_interface:form_fill_page", kwargs={course_slug, index, page_number})` | **Course-shaped URL**, form-intrinsic *concept* |
| `existing_answers` | `form_progress.existing_answers_dict(questions)` | Form-intrinsic |
| `page_links` | built from `all_pages` + `furthest_page`, each entry's `url` reverses the course route | Form-intrinsic data, **course-shaped URLs** |
| `answered_count`, `answered_other_pages`, `total_question_count` | `form_progress.answers` counts | Form-intrinsic |
| `submit_and_exit_url`, `save_and_exit_url` | `reverse("learner_interface:form_submit_and_exit"/"view_course_item", kwargs={course_slug, index})` | **Course-shaped URLs** |
| `required_answers_error` | validation | Form-intrinsic |
| `course_index`, `current_part`, `current_part_index`, `course_progress`, `can_record_progress`, `course_organisation`, `item_title`, `index` | `_player_chrome_context()` (`views.py:797-859`) | **100% course chrome** |

Roughly a third of the ~20 keys are pure course chrome (the `_player_chrome_context` spread, unpacked
into the same dict at `views.py:1227-1229`); the rest are form-intrinsic values wrapped in
course-shaped URLs. That matches the extraction spec's estimate ("roughly half… course chrome",
§12) closely enough that nothing in that estimate needs revising.

**Templates, concretely:**

- `course_form_page.html` (the paginated fill page) extends `_exam_runner_base.html`, which extends
  `_base.html` **directly** — "no sidebar, no course TOC" by its own comment
  (`_exam_runner_base.html:5-14`). Reading the body block top to bottom, it references `form`,
  `form.submit_on_exit`, `form_page`, `current_page_num`, `total_pages`, `answered_count`,
  `answered_other_pages`, `total_question_count`, `required_answers_error`, `previous_page_url`,
  `has_next_page`, `page_links`, `submit_and_exit_url`, `save_and_exit_url` — **not one course
  variable appears in the template itself.** It is already exactly as generic as §12 said the
  partials were; the coupling lives entirely in how the *view* builds the URLs it is handed, not in
  the template.
- `course_form.html` (the start screen: title, intro markdown, meta grid, previous attempts, CTA
  buttons) and `course_form_complete.html` (the results screen) both `{% extends
  "learner_interface/_course_base.html" %}`, which bakes in the docked course TOC sidebar
  (`sidebar_content`, `_course_base.html:59-80`), the breadcrumb (`player_breadcrumbs.html`) and the
  mobile course-progress bar (`_course_base.html:51-57`) — all of which read `course`, `course_index`,
  `course_progress`, `current_part`. **These two templates cannot render outside a course as-is.**
  Their *inner content* — `exam_meta_grid.html`, `exam_previous_attempts.html`, `exam_score_ring.html`
  — is itself course-free (verified: none of the three reference `course`), so the reusable unit is
  those partials, not the pages that currently wrap them.

Net for design: the actual answering surface (`course_form_page.html` + its partials) is close to
drop-in reusable behind a different URL scheme; the start/results *pages* need a different base
template (or to be skipped — see the note in §3 that review is admin-only, which may mean the
applicant only ever needs a thin "application received" page, not a scored results page at all).

## 5. Multi-page machinery on `FormProgress` — works unchanged

`get_current_page_number()` (`models.py:251-272`), `existing_answers_dict()` (`models.py:274-288`) and
`save_answers()` (`models.py:290-311`) all operate purely on `self` (`FormProgress`), `self.form.pages`
and `self.answers` — no course, no `collection_item`, no `CourseFormAttempt` reference anywhere in any
of the three. This is exercised directly and course-free in
`form_engine/tests/test_form_progress.py`, which builds a `Form`/`FormPage`/`FormQuestion` tree and a
bare `FormProgressFactory(user=…, form=…)` with no course in the test module at all, and asserts
`get_current_page_number()` resumes correctly across four scenarios (`test_form_progress.py:29-84`).
**No course assumption exists inside this machinery.** The only thing that is course-shaped is, again,
one layer up: the *view* resolves which `FormProgress` to call these methods on via
`get_latest_incomplete(course_progress, collection_item)` (§2) rather than `(user, form)` directly —
an application flow resolves its one `FormProgress` differently, but calls the identical methods on it
once resolved.

## 6. Blast radius

| File | Change | Necessity |
|---|---|---|
| `freedom_ls/form_engine/enums.py` | Add `FormStrategy.UNSCORED` | **Must** — §1 |
| `freedom_ls/form_engine/schema.py:22-26` | Add `FormStrategy.UNSCORED` to the pydantic enum, kept in sync | **Must** (enum must stay in sync; YAML forms unaffected by this spec but the two enums drift otherwise) |
| `freedom_ls/form_engine/models.py:495-503` (`FormProgress.score`) | Add `elif self.form.strategy == FormStrategy.UNSCORED: return` | **Must** — §1 |
| `freedom_ls/form_engine/admin.py` (`FormAdmin`) | `save_model` override generating a unique slug when blank, mirroring `OrganisationAdmin.save_model` | **Must**, if application `Form`s are admin-authored — §3 |
| `freedom_ls/course_applications/models.py` | Add `form = models.ForeignKey(Form, …)` to `CourseApplication`; new migration | **Must** — the spec's stated shape |
| `freedom_ls/course_applications/models.py:23-29` (NOTE comment) | Update: it currently says "gains `config FK ApplicationConfig`" — factually superseded by this decision | **Must** (it is stale, not a TODO/@claude comment protected from editing, but it actively misleads the next reader) |
| `freedom_ls/course_applications/views.py:27-32` (NOTE comment in `apply()`) | Same — says "resolve the ApplicationConfig"; needs to describe resolving/creating the `Form`/`FormProgress` instead | **Must**, same reason |
| `freedom_ls/course_applications/views.py` (`apply`) | Build/resolve the `FormProgress` for the applicant directly (`FormProgress.objects.get_or_create(user=…, form=course.access_config-resolved-form)`, no `learner_progress.attempts` helpers — §2) and redirect into a new answering flow | **Must** |
| New URLs/views for answering the application questionnaire | Route the applicant to a paging flow keyed on `CourseApplication.pk` (or its `FormProgress`), not `Form.slug`/course index — §3, §4 | **Must** |
| New template(s) for the applicant shell, including the relocated question partials | The question partials are `partialdef`s inside `course_form_page.html` and move to `freedom_ls/form_engine/templates/form_engine/` first; the applicant shell then includes them under a base with no course TOC. This gives `form_engine` template-level edges on `base` (`c-callout`) and `icons` (`c-icon`), both leaf apps, so the graph stays acyclic | **Must** — §4 |
| `freedom_ls/form_engine/urls.py`, `Form.preview_url()` | Give `Form` a route and a preview URL | **Would be nice** — only needed if something needs to *link to* a bare `Form` (an admin preview, a `<c-content-link>`); the applicant flow itself can be keyed on `CourseApplication.pk` instead (§3) |
| `FORM_CONTEXT_BACKEND` pluggable seam (§12 of the extraction spec) | A generalised "can this user answer this form, and what chrome wraps it" backend | **Would be nice**, not required for one hardcoded application flow; the extraction spec proposed it for the general case, this spec only needs one instance of it |
| `freedom_ls/reports/indexes.py` | None | **No change** — application `Form`s carry no course placement, so `viewable_items()`-driven report loaders never see them regardless of `strategy` |
| `freedom_ls/learner_progress/*` | None | **No change** — the course-progress signal receiver already no-ops correctly for a courseless `FormProgress` (§2); `attempts.py` is deliberately not used by the application flow |
| `freedom_ls/learner_interface/*` | Split `form_fill_page`: the form half (page bounds, required-answer check, `save_answers` call, page-link build, answer tallies, `_unanswered_required_message`) moves to `form_engine`; the course half (access redirect, `_blocked_item_redirect`, `_player_chrome_context`, the `attempts.py` helpers, submit-on-exit) stays and calls into it. Move the `form-input-*` / `form-question` `partialdef`s out of `course_form_page.html` into `form_engine` templates | **Must** — superseded by the idea's "The runner has to be split before either flow can share it". This row previously said "No change", on the assumption the application flow could include `learner_interface` partials in place; that would be an app edge pointing the wrong way. Observable exam-runner behaviour still must not change |

## Prior art: what still holds, what this decision overrides

- **`spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/1. spec.md` §12** — "A form
  usable outside a course needs three things it does not have": identity, an authorisation seam, a
  context-agnostic runner. All three claims are still factually accurate (confirmed independently in
  §3–§4 above); this spec does not need to build the general-purpose version of any of them
  (`FORM_CONTEXT_BACKEND`, a full slug route) because it has exactly one non-course consumer, not an
  open plugin point — see the "would be nice" rows above.
- **`research_reuse_case.md` §5** (the five reasons the June research gave for a separate
  `ApplicationForm` family), checked again here directly against the code rather than by report:
  - Reason 1 (authoring mismatch, file-backed vs. admin-built) — **confirmed lapsed**: `FormAdmin`
    already exists as a full CRUD surface (`form_engine/admin.py:151-179`), and `FormFactory` already
    creates `Form` rows with `file_path=""` (`form_engine/factories.py:30`). The only real gap is the
    missing slug-generation hook (§3), not a structural inability to create a `Form` outside the
    loader.
  - Reason 2 (PII isolation) — **still true and not addressed by this spec**, per the user's decision
    not to re-litigate it: `QuestionAnswer.text_answer` is a plain `TextField`
    (`form_engine/models.py:582`) with no field-level protection beyond whatever the database provides
    generally. Recorded here as a known, accepted gap, not a defect to fix in this spec.
  - Reason 3 (behavioural divergence via the course-progress signal) — **confirmed resolved**, and
    resolved exactly as `research_reuse_case.md` predicted ("replaces it with an explicit signal
    subscription… a wiring detail"): see §2's quote from `signals.py`.
  - Reason 4 (no scoring semantics) — **the one this spec must still fix**, via `UNSCORED` (§1),
    exactly as flagged.
  - Reason 5 (approval workflow has its own home) — **still true and explicitly out of scope**: the
    review FSM stays a `course_applications` concern per the user's decision; nothing here touches it.
- **`spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_form_schema.md`** — its Option A
  "cons" list (file-backed invariant, progress-hook coupling, PII mixing, quiz-field clutter,
  `content_engine` scope creep) maps one-to-one onto the five reasons above and is superseded the same
  way: the `form_engine` extraction (August 2026) already answered the progress-hook and
  `content_engine`-scope-creep cons by moving `Form`/`FormProgress` out of `content_engine` into a
  standalone app with none of that baggage; only the PII-mixing con is knowingly accepted rather than
  resolved.
- **`spec_dd/3. done/2026-06-23_13:04_applying-for-courses/1. spec.md`** — predates the `form_engine`
  extraction and the `ApplicationCourseAccessBackend`/`CourseApplication` shape that actually shipped;
  its model design is the one this spec deliberately does not build. Nothing in it needs citing beyond
  that it is superseded.

status: ok
