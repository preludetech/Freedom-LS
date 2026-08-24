# Research: is there a real reuse case for forms outside course content?

## Executive summary

**Yes — one strong, one medium, and a pile that do not count.** The prior research
(`spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/research_forms_app_extraction.md`)
declined to extract forms and named its revisit condition precisely: *"Revisit only if a concrete
reuse case for forms outside course content ever appears."* That condition is met, and it is met in
the strongest possible form — not a hypothetical, but a **drafted design that duplicates the entire
`Form → FormPage → FormQuestion → QuestionOption` family model-for-model and accepts an inverted
dependency edge to make it work** (`spec_dd/0. drafts/application-forms/idea.md`). A second, weaker
case (configurable demographic questions at registration) has no course in it at all. Two premises
the *original* duplicate-don't-share decision rested on
(`spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_form_schema.md`) have both lapsed
since it was written. Set against that, two candidates that look like consumers are **not**:
`in-app-feedback` is a fixed rating-plus-text model that deliberately avoids questionnaire
machinery, and `ADDITIONAL_REGISTRATION_FORMS` is Python-authored `django.forms` by design. The
honest tally is therefore narrower than "everything wants forms" — but one full-family duplicate is
already enough, because the thing being duplicated is the whole primitive.

## 1. The prior verdict, quoted fairly

Two documents record the standing decision.

`research_forms_app_extraction.md` (351 lines), executive summary:

> **Recommendation: no — do not extract forms into their own Django app.** Split
> `content_engine/models.py` (and, opportunistically, `schema.py`/`admin.py`) into a `models/`
> package with a `forms.py` module instead — same app label, same tables, zero migration, most of
> the organisational benefit.

and its closing sentence:

> Revisit only if a concrete reuse case for forms *outside* course content ever appears — not to
> satisfy a feeling that a 605-line file is big.

`final_pre_deploy_db_structure_cleanup/idea.md`, in a section headed "The forms question, answered":

> **No.** The intuition is real but mis-locates the complexity. […] What forms actually want is a
> `models/` package with a `forms.py` module inside the same app — same label, same tables, zero
> migration, most of the organisational benefit. […] That is the honest answer, not a hedge.

and under **Won't do**:

> - **Extract forms into their own app.** Answered above.

**Everything in those two documents remains factually true.** Nothing below contradicts a fact in
them. What has changed is the input the conclusion was conditioned on — which is exactly what the
author anticipated by writing a revisit condition rather than a closed door.

Two mechanical caveats when quoting that research:

- It predates `learner-terminology-rename` (landed 2026-08-22) and refers to `student_progress`,
  `student_interface`, `student_management`. Translate to `learner_progress`, `learner_interface`,
  `learner_management`.
- Its line citations for `content_engine/models.py` (e.g. "302-451") predate later edits; the form
  block is now `models.py:421-567`.

## 2. The strong case: `application-forms`

`spec_dd/0. drafts/application-forms/idea.md` (14.5 KB) designs the questionnaire that sits in front
of `CourseApplication`. It is explicit that it is a copy:

> Mirror `Form → FormPage → FormQuestion → QuestionOption` (`content_engine/models.py:302–451`) in
> shape and load through the **same content_save pipeline**  — lines 25-26

The proposed models, with the draft's own annotations:

| New model | Draft's own comment |
|---|---|
| `ApplicationConfig` | the `Form` analogue |
| `ConfiguredCourse` | — |
| `ApplicationStep` | the `FormPage` analogue |
| `ApplicationQuestion` | "mirrors FormQuestion + a file type" (line 46) |
| `ApplicationQuestionOption` | "mirrors QuestionOption (no `correct` — applications aren't scored)" (line 56) |
| `ApplicationAnswer` | "deliberately a 1:1 copy of the `QuestionAnswer` shape so the two systems read the same way" |
| `ApplicationFile` | genuinely new (file upload) |

That is five of seven models existing solely because the current ones cannot be reached from outside
a course.

### The inverted edge

The draft runs straight into the boundary and resolves it the only way available to it:

> Because the loader lives in `content_engine`, the config models either (a) live in
> `content_engine`, or (b) the loader is extended to register the `course_applications` config
> models. **Decision:** the config models live in `course_applications`, and `content_save` is
> extended to dispatch the new content type to them […] The structure review must confirm this
> **`content_engine → course_applications`** *loader-only* edge is acceptable  — lines 68-74

`content_engine` is the lowest content layer in the graph (`docs/app_structure.md`:
`content_engine → base, icons, markdown_rendering, site_aware_models`, with nine apps depending on
it). Pointing it at `course_applications` — which itself depends on `accounts`, `content_engine`,
`course_access`, `learner_management` and `site_aware_models` — inverts the graph and creates a
cycle in spirit if not in import order. The draft knows this and flags it for structure review
(line 246-249), with a fallback of *moving the application config models into `content_engine`* —
which is the same admission from the other direction: **the form primitive's home is wrong.**

### The one genuinely new requirement

`FILE_UPLOAD` is not in `QuestionType` (`content_engine/models.py:17-24`). The draft notes it: *"The
file type is the one genuinely new question type."* It also brings private storage with a
permission-checked serve view, a `scan_status` seam, and magic-byte MIME sniffing. None of that
argues against a shared primitive — a shared `FormQuestion` gains one more `QuestionType` member and
one optional child model, which is strictly less work than seven new models.

## 3. The medium case: demographics at registration

`spec_dd/0. drafts/add_demographics_to_registration_flow_and_profile/idea.md` (660 bytes):

> create demographic models and forms. It needs to be configurable […] we might want to plug into
> the extensible registration system by asking certain demographic questions when users register for
> the system.

Nationality, city/country, gender, date of birth; explicitly *"Don't go overboard make a minimal
implementation."* No course appears anywhere. This is a configurable questionnaire answered by a
user who may not be enrolled in anything — precisely the case the current `Form` cannot serve,
because answering one requires passing `_course_access_redirect` (`learner_interface/views.py:577`).

It is graded **medium** rather than strong for two reasons: it is tiny, and the shipped
`ADDITIONAL_REGISTRATION_FORMS` mechanism (below) is a legitimate way to build it without any form
model at all.

## 4. What does *not* count, and why saying so matters

An idea doc that inflates its consumer count is easy to dismiss. These three look like evidence and
are not.

**`spec_dd/2. in progress/in-app-feedback/`** — reads like a survey app; is not. Its spec
(`1. spec.md:15-60`) defines `FeedbackForm` with a *fixed* shape: one `rating_label`, one
`text_prompt`, one `thank_you_message`, plus anti-fatigue counters. There are no question rows and
no option rows. Its research file
(`research-technical-patterns.md:177`) recommends generating a `django.forms.Form` from the DB
definition at render time. It is deliberately decoupled — *"the feedback app doesn't need to know
about `TopicProgress` or `CourseProgress`"*. **A shared form primitive would be over-engineering
for it.** Count it as zero.

**`ADDITIONAL_REGISTRATION_FORMS`** (shipped, `spec_dd/3. done/2026-05-05_08:18_better-registration/`,
documented in the `fls-dev:registration` skill) — plain `django.forms.Form` subclasses loaded by
dotted path, gating platform access post-verification. This is FLS's *existing* standalone-form
mechanism and it is a different paradigm on purpose: Python classes authored by a developer, not
content authored in files or in the admin. It is evidence that **not every questionnaire wants the
content-form stack**, which is a useful constraint on scope, not a consumer.

**`compliance-exam-remediation`, `exam-timeouts`, `sacaa question-pools-and-remediation`,
`compliance-form-randomization`** — all grow the form model surface (per-option explanations, timers,
question pools, per-attempt realized order) and all are firmly course-bound. They are **neutral** on
the app boundary and were correctly read that way by the prior research. One of them,
`compliance-exam-remediation`, is a live argument *against* extraction: *"reference relevant
content"* most naturally means a `FormQuestion` pointing at a `Topic`/`Activity`, which is an
ordinary FK today and a cross-app FK after extraction. That cost is real; see
`research_boundary_options.md`.

## 5. The premises that lapsed

The decision to duplicate rather than share was made once already, deliberately, with reasons.
`spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_form_schema.md` evaluated three
options and chose Option B (a separate `ApplicationForm` model in a new app):

> ### Option C — shared abstraction (rejected)
> Extract a common `QuestionnaireSchema` package both apps depend on. Sounds clean, but:
> - Premature: we have only two consumers. Per project conventions ("Don't build functionality that
>   is not explicitly requested", "Don't create abstract base classes unless asked"), this is
>   over-engineered today.
> - Would force a refactor of `content_engine` that is out of scope for this spec.

Its five decisive reasons, checked against today:

| # | Reason given (2026-06) | Status now |
|---|---|---|
| 1 | **Authoring model mismatch** — `Form` is file-backed via `BaseContent.file_path`; application forms would be admin-built | **Lapsed.** `application-forms/idea.md:25-26` now asks to *"load through the same content_save pipeline"* — file-backed. The premise was abandoned by the very draft it was written for. |
| 2 | **PII isolation** — application answers are PII, quiz answers are not | **Still true, and still an argument for separate tables — but not for separate models.** A shared `FormQuestion` definition does not force shared answer storage; see `research_boundary_options.md` on splitting definition from response storage. |
| 3 | **Behavioural divergence** — `FormProgress` triggers `update_course_progress_on_completion`, applications must not | **Weakened.** That trigger is one `post_save` receiver in `learner_progress/signals.py:35`, and extraction replaces it with an explicit signal subscription. It is a wiring detail, not a shape difference. |
| 4 | **No scoring semantics** — `Form.strategy` is required | **Still true and cheap to fix** (`strategy` becomes nullable, or gains an `UNSCORED` member). Note the irony: an *application* form that is not scored is exactly the "questionnaire, not quiz" case this idea is about. |
| 5 | **Approval workflow has its own home** | **Still true and unaffected.** Nobody proposes moving the FSM into a forms app. |

Two of five have lapsed outright, two are weakened, one is untouched and irrelevant to the boundary.
The "only two consumers" premise is the one that matters most, and it was conditioned on a count
that has since grown.

That research also proposed a mitigation which is worth reading as a tripwire that has now been hit:

> **Copy the templates initially; extract shared partials only if and when a clear reuse pattern
> emerges.**

## 6. The cost of not extracting

Stated plainly, so it can be weighed against the seven-edges cost in
`research_boundary_options.md`:

1. **Two full question/answer model families**, diverging from the day they land. Every future form
   capability gets built twice or built once and silently missing from the other:
   `FILE_UPLOAD` (applications only), question pools (quizzes only), timers (quizzes only),
   per-option explanations (quizzes only).
2. **An inverted dependency edge**, `content_engine → course_applications`, accepted by the
   application-forms draft as the price of reusing the loader.
3. **Two renderers.** `course_form_page.html` is 581 lines with per-question partials
   (`form-input-multiple-choice`, `form-input-checkboxes`, `form-input-short-text`,
   `form-input-long-text`) plus the Alpine `examRunner*` components and the answered-count and
   `beforeunload` guards. A copy inherits none of the bug fixes.
4. **Two reporting paths.** `reports/indexes.py` is the only question-level consumer and is entered
   through Cohort → Course (`build_course_catalogue`, `indexes.py:211`). Application answers would
   need a parallel one from scratch.
5. **A third stack after that.** The pattern repeats for the next questionnaire — demographics,
   whatever follows — because each one hits the same wall in the same place.

## 7. What would falsify this

Written down so a future reader can check rather than re-argue:

- If `application-forms` is descoped or built on plain `django.forms` (the
  `ADDITIONAL_REGISTRATION_FORMS` paradigm), the strong case evaporates and the count drops back to
  "one tiny demographics draft". The prior verdict then stands unchanged.
- If the ordering against `final_pre_deploy_db_structure_cleanup` were reversed — the reset first,
  the extraction after — the cost side changes shape entirely: every downstream project would pay a
  hand-written `django_content_type` migration, and the seam-only alternative
  (`research_boundary_options.md`, option D) would become the better answer.
- If nothing needs a non-course form to be *answerable* (only *definable*), then the identity and
  authorisation work is unnecessary and the app move alone buys very little.

status: ok
