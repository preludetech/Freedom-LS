Note: spec_dd/2. in progress/better_course_progress_tracking/idea.md will change how users are associated with formprogress

# Extract form functionality out of content_engine into its own app

## Goal

Give FLS one questionnaire primitive that is usable outside course content — guidance
questionnaires, ability and preference measurement, course-application forms — instead of the
course-only one it has today plus the parallel copies that are already being drafted. The target is
a new `freedom_ls/form_engine/` app owning the form definition, the attempt, and the marking, with
the *consequences* of a result (course progression, deadlines, cohort reporting) staying with the
apps that care about them.

**This idea reverses a recorded decision.** `spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/idea.md`
lists "Extract forms into their own app" under **Won't do**. That decision was correct for the
question it was asked. It is not correct for this one. See "The prior verdict, and what has changed".

## Background

### What lives where today

Forms are course content. `Form → FormPage → (FormContent | FormQuestion) → QuestionOption` sit in
`content_engine/models.py:421-567` next to `Course`, `CoursePart`, `Topic` and `Activity`, on the
same `BaseContent`/`TitledContent`/`MarkdownContent` abstract bases (`models.py:55-143`).

The three layers a reader might expect are already three apps, but the split runs along the wrong
seam:

- **Definition** — `content_engine`: models, pydantic schema (`schema.py:223-332`), nine admin
  classes (~180 of 279 lines of `admin.py`), five factories, five loader functions
  (`content_save.py:355-417`).
- **Attempt + marking** — `learner_progress`: `FormProgress` (`models.py:76-482`, 407 lines, the
  largest model in the codebase), `QuestionAnswer` (`models.py:483-502`), `scoring.py` (36 lines),
  `submissions.py` (32 lines), `queries.py` (51 lines).
- **Player** — `learner_interface`: `view_form`/`form_start`/`form_fill_page`/`course_form_complete`/
  `form_submit_and_exit` (`views.py:832-1337`), `course_form_page.html` (581 lines),
  `_exam_runner_base.html`, the Alpine `examRunner*` components.

The important and under-appreciated fact: **the attempt layer is already course-free.**
`FormProgress` is keyed `(user, form)` and has no `Course` FK at all. `scoring.py` and
`submissions.py` are pure functions. The single course coupling in the whole app is
`signals.py:35`, which walks `ContentCollectionItem` up to a `Course` on completion.

What is *not* course-free is **identity and authorisation**:

- Every form route is `courses/<slug:course_slug>/<int:index>/…` (`learner_interface/urls.py:27-44`).
  A form-first URL design was written and abandoned — it survives commented out at `urls.py:58-72`.
- The only resolver is `get_form_for_index(course, index)` (`learner_interface/utils.py:748`). A form
  has no addressable identity; it is "the Nth viewable item of a course".
- All authorisation to answer a form is *course* authorisation: `_course_access_redirect`
  (`views.py:577`) calls `raise_404_if_hidden_unregistered` plus the `COURSE_ACCESS_BACKEND`. There
  is no form-level permission concept anywhere — `role_based_permissions/` and `course_access/`
  contain zero `Form` references.
- `Form` has no `preview_url()`, so `<c-content-link>` to a bare form renders an empty `href`.

### The prior verdict, and what has changed

`final_pre_deploy_db_structure_cleanup/research_forms_app_extraction.md` answered
*"are forms complicated enough to deserve their own app?"* with **no**, and its reasoning holds:
the definition models are small, the hard parts already live elsewhere, the abstract bases have no
good new home, and extraction adds roughly seven dependency-graph edges without shrinking
`content_engine`'s fan-in. It also named its own revisit trigger:

> "Revisit only if a concrete reuse case for forms *outside* course content ever appears — not to
> satisfy a feeling that a 605-line file is big."

That trigger has fired, and the evidence is duplication that is already drafted, not hypothetical:

- **`spec_dd/0. drafts/application-forms/idea.md`** proposes mirroring
  `Form → FormPage → FormQuestion → QuestionOption` "in shape and load through the **same
  content_save pipeline**" (lines 25-26) as `ApplicationConfig`/`ApplicationStep`/
  `ApplicationQuestion`/`ApplicationQuestionOption`/`ApplicationAnswer`, with `ApplicationAnswer`
  "deliberately a 1:1 copy of the `QuestionAnswer` shape". To make the loader work it accepts a new
  **`content_engine → course_applications`** edge (lines 68-74) — the dependency graph inverted, to
  avoid a coupling that a shared primitive would remove.
- **`spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_form_schema.md`** rejected a
  shared abstraction on two premises that have both since lapsed: "we have only two consumers", and
  `Form` is file-backed while application forms would be admin-built. The application-forms draft now
  asks for the file-backed loader itself.
- **`spec_dd/0. drafts/add_demographics_to_registration_flow_and_profile/idea.md`** is a
  configurable questionnaire with no course anywhere in sight.

Counted honestly, this is one strong consumer, one medium, and several that do not count.
`in-app-feedback` is a fixed rating-plus-text model and deliberately decoupled; the shipped
`ADDITIONAL_REGISTRATION_FORMS` are Python-authored `django.forms` on purpose. Neither is evidence
for a shared primitive. See `research_reuse_case.md`.

## Scope

### 1. What moves, what stays, and what the abstract bases do

**Moves to `form_engine`:** `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`,
`QuestionType`, `FREE_TEXT_QUESTION_TYPES`, `FormStrategy`; the nine form admin classes; the five
form factories; the form pydantic models; `FormProgress`, `QuestionAnswer`, `scoring.py`,
`submissions.py`; `quiz_verdict()` and `count_form_questions()` (currently misfiled in
`learner_interface/utils.py:147,739`).

**Stays put:** `ContentCollectionItem`, `Course`/`CoursePart`/`Topic`/`Activity`/`File`,
`CourseProgress`, `TopicProgress`, `learner_progress/signals.py`, the whole player view layer.

**Moves to a new `content_base` app:** `BaseContent`, `TitledContent`, `MarkdownContent` — and, on
the same argument, `schema.py`'s pydantic bases (`BaseBaseContentModel`, `BaseContentModel`,
`MarkdownContentModel`, the `ContentType` enum and the `_registry`).

**The abstract bases.** The prior research is right that this has no clean answer and demands an
explicit one. **Decision: a small `content_base` app that owns the abstract bases and nothing else.**
Both `content_engine` and `form_engine` depend on it; neither depends on the other for bases.

Why this beats keeping them in `content_engine`:

- **It costs nothing at the database level.** Abstract models produce no tables and no migrations —
  Django does not even require an abstract model's module to be in an installed app. `content_base`
  can therefore land on its own schedule, **before** the extraction and independent of the migration
  reset, which keeps the move itself to concrete models only.
- **It removes the mutual edge.** Keeping the bases put gives `form_engine → content_engine` (bases)
  alongside `content_engine → form_engine` (loader). With `content_base` the graph is a DAG:
  `content_engine → content_base`, `form_engine → content_base`, `content_engine → form_engine`.
- **It dissolves the registry problem in §4.** With the pydantic bases and `_registry` in
  `content_base`, both apps register into a registry neither owns, so there is nothing to fork and
  nothing to re-couple.
- **Precedent exists.** `panel_framework` is an installed app with zero models.

Constraints on it, all load-bearing:

- **Name it `content_base`, not `content_engine_base`.** Two apps depend on it; naming it after one
  of them reads as "form_engine depends on content_engine", which is the confusion it exists to
  remove. Label `freedom_ls_content_base`.
- **Do not put the bases in `base` instead.** `base` looks ideal — no `models.py`, bottom of the
  graph, zero runtime deps — but `BaseContent` extends `SiteAwareModel`, so it would add
  `base → site_aware_models` while `site_aware_models → base` already exists. That is a genuine
  cycle, worse than the one being fixed.
- **It removes today's cycle; it does not prevent one.** The loader edge stays, so any future
  `form_engine → content_engine` import re-creates the pair —
  `compliance-exam-remediation`'s "reference relevant content" is exactly that. A string FK
  (`"freedom_ls_content_engine.Topic"`) dodges the Python import, but `/ds:app_map` is ast-based, so
  that dependency would be real and *invisible* — worse for the graph than an edge you can see.
- **The cycle it removes was never an `ImportError`.** `content_engine/models.py` never imports form
  models; only `content_save.py` and `content_tags.py` do, lazily. The win is legibility and passing
  `/fls-dev:plan_structure_review`, not a crash avoided. Say so rather than overselling it.

Record the remaining smell honestly: `file_path`/`meta`/`tags` are *content-file* fields that an
admin-authored form does not want, and a `FormPage` carries a `file_path` for a file it is not.
`content_base` does not fix that — it makes the eventual split into file-backed and not-file-backed
halves cheap, because it is surgery inside a small dedicated app rather than inside `content_engine`.
Still out of scope here.

### 2. Attempts and marking: two layers, not three

Marking belongs **with** forms, not layered on top of them. `Form.strategy` is a field on the form;
`FormProgress.score()` dispatches on it; a quiz's pass mark is `Form.quiz_pass_percentage`. Splitting
scoring into a third app would separate a dispatch from the enum it dispatches on and add edges for
no consumer.

What *is* layered on top is the **consequence** of a result. That seam already exists and is already
correctly shaped: `learner_progress/queries.py:28` `completed_form_ids_by_user()` returns
`{user_id: {form_id}}` — course code asks "which forms are done", form code never asks about courses.
Extraction replaces the one remaining import with a signal: `form_engine` emits
`form_attempt_completed`, and `learner_progress/signals.py` subscribes instead of `post_save` on a
model it no longer owns. Everything downstream (progression gating in
`learner_interface/utils.py:165` `get_content_status`, deadlines, cohort reporting) keeps working
unchanged.

### 3. The identity and authorisation seam

**This is the part that actually unlocks non-course use, and it is not the app move.** A form needs:

- **An identity** — a slug-based route and a `preview_url()`, so a form can be linked to and
  answered without a course index.
- **An authorisation seam** — something that answers "may this user answer this form, in this
  context?" for a context that is not a course. Follow the existing `COURSE_ACCESS_BACKEND`
  precedent (`config/settings_base.py:423`, resolved via `import_string`) rather than inventing a
  pattern: a form-context backend that returns can-answer, exit URL, and the chrome partial to wrap
  the runner in. The course player becomes the first implementation of that backend, not a special
  case.
- **A context-agnostic runner** — `form_fill_page` builds ~15 context keys, roughly half of them
  course chrome. The template partials in `course_form_page.html` are already generic; the view is
  what needs the seam.

This is deliberately **not** part of the extraction cut. See "Sequencing".

### 4. The content_save and pydantic-registry seam

One pydantic registry (`schema.py:70,336`) is populated by `__init_subclass__` and walked once by
`validate.py`; one `@transaction.atomic` importer (`content_save.py:492-698`) builds a single
`content_by_path` map spanning every content type and resolves `Course` children against it;
`FormPage.derive_content_type` (`schema.py:274-278`) is form logic called from generic
`validate.py:187-191`.

**Decision: the registry moves to `content_base`; the loader stays whole in `content_engine` and
imports form models from `form_engine`.** With `BaseBaseContentModel`, `BaseContentModel`, the
`ContentType` enum and `_registry` in `content_base`, both apps register into a registry neither
owns — there is nothing to fork and nothing to re-couple, and `validate.py` keeps its single walk.
`FormPage.derive_content_type` travels with the form schema classes into `form_engine`; the generic
parser calls it polymorphically off the registry, which it already does.

The **importer** is the one place where a real choice remains. One `content_engine → form_engine`
edge, in exchange for keeping one transaction, one `content_by_path` map and one validation walk.
This is the same shape the application-forms draft already proposed for its own config models —
except pointed at a shared primitive instead of a second copy. Detail in
`research_extraction_mechanics.md`.

### 5. Migrations: there is no data to preserve

**Decided: this lands before `final_pre_deploy_db_structure_cleanup`.** That spec's one-time,
project-wide migration reset therefore runs *after* the extraction and regenerates every app's
`0001_initial` on top of it. Two consequences, and they remove most of what would otherwise be the
cost of this work:

- **No data preservation, no backfills, no content-type recipe.** Five tables change name
  (`freedom_ls_content_engine_form` → `freedom_ls_form_engine_form`, and four more; nothing sets
  `db_table`, so names derive from the app label). Ordinarily a cross-app move is dangerous —
  Django's `RenameContentType` fires only for `RenameModel` **within one app**, so it leaves stale
  `django_content_type` rows and silently orphans `ContentCollectionItem`,
  `CourseProgress.last_accessed_*`, the three deadline models, guardian object permissions and
  `auth_permission`. **None of that applies here**: FLS databases are rebuilt from scratch, no
  downstream project has migrated a database it intends to keep, and the reset that follows discards
  the migration history anyway. Drop the dev database, recreate, migrate, re-import demo content.
- **The intermediate migrations are throwaway.** Whatever `makemigrations` produces for the move is
  deleted by the reset. Do not spend effort making it elegant, and do not hand-write a data
  migration for it.

Authored form content survives regardless, because it is file-backed: `content_save` re-imports
`demo_content/` and UUIDs are written back into the source files, so form, page, question and option
identities are stable across a rebuild. The only thing lost is learner attempt data
(`FormProgress`/`QuestionAnswer`), which exists in dev only.

**What still breaks, and still needs writing down:** this remains a loud break at the *code* level —
import paths, app labels, table names, template paths, permission codenames. Downstream projects
that reference `freedom_ls.content_engine.models.Form` must edit their code. So `upgrade_notes.md`
is still required, modelled on
`spec_dd/3. done/2026-08-22_15:42_learner-terminology-rename/upgrade_notes.md` — but only its
find-and-replace and settings sections. Its §9 and manual step 5 (the `django_content_type` recipe)
have no analogue here and must not be copied in.

### 6. Dependency-graph impact, and the seven-edges objection

The objection is true as stated: `learner_progress`, `learner_interface`, `educator_interface`,
`reports`, `learner_management` and `qa_helpers` all import `Form` alongside `Topic`/`Course` in the
same functions, so each gains a second edge, plus `content_engine → form_engine` for the importer
and two edges into `content_base`.

`content_base` (scope §1) changes the *shape* of the objection rather than its arithmetic. The count
is roughly the same — one edge is traded for two — but the graph becomes acyclic, which the
keep-the-bases-put version is not. An edge count that includes a mutual pair and one that does not
should not be weighed as equal.

The answer to the count itself is that edge count is not coupling. Those imports exist today; the graph just cannot see
them because they hide inside one app. What the extraction changes is that the coupling becomes
*legible*, and one edge disappears for real — `learner_progress → content_engine` for `Form` — while
a much worse edge is prevented: the `content_engine → course_applications` inversion the
application-forms draft is currently prepared to accept. Weigh it as +7 legible edges against
+1 inverted edge and N duplicated model families. Full argument in `research_boundary_options.md`.

## Sequencing

All of this lands **before** `final_pre_deploy_db_structure_cleanup`, which is what makes the
database side a non-issue (scope §5). Within that, order by dependency, not by value.

1. **`models/` package:** split `content_engine/models.py` into a `models/` package with `forms.py`,
   re-exported from `__init__.py`. This is already the standing "do later" decision in
   `final_pre_deploy_db_structure_cleanup`; it is a no-regret prerequisite either way, not an
   alternative to extraction. Doing it first turns step 3 into a directory move rather than surgery
   on a 605-line file.
2. **The `content_base` app** (scope §1). Abstract models only — zero tables, zero migrations.
   Landing it before the move means step 3 deals with concrete models and nothing else.
3. **The app move** (scope §2, §4, §5, §6). `content_snapshots` and
   `compliance-form-randomization` are paused until after deployment, so nothing in flight competes
   for this tree.
4. **The identity and authorisation seam** (scope §3), when a consumer needs it. The first consumer
   is `application-forms`, which must be re-scoped onto the shared primitive rather than building
   its second copy.

Steps 1 and 2 are worth doing even if step 3 is rejected outright. Step 4 is where the reuse value
actually lands, and it is the one piece that can follow at any distance.

## Alternatives considered

- **`models/` package only.** The standing decision. Zero migration, zero new edges, and zero reuse
  unlocked — it is a file-navigability fix, and every drafted duplicate still gets built.
- **Three apps (definition / responses / marking).** Rejected: marking is not separable from
  `Form.strategy`, and it multiplies edges for no consumer.
- **Seam-only: leave the models put, add form identity and a context backend.** Delivers all of the
  reuse value on its own. Rejected as a *substitute* only because the move is now close to free —
  it leaves `content_engine` owning a primitive that is no longer about course content, for no
  saving. It remains the right answer if the move is rejected for other reasons.
- **Renaming `Form` → `Questionnaire` on the way out.** Rejected: multiplies the size of the break
  for vocabulary alone.
- **Keeping the abstract bases in `content_engine`** (this idea's own first answer). Rejected in
  favour of `content_base`: it leaves `content_engine` and `form_engine` importing each other for no
  gain, when the fix costs no migration. See scope §1.
- **Putting the bases in `base`.** Rejected — it would create `base → site_aware_models` against an
  existing `site_aware_models → base`, a real cycle. See scope §1.

## Out of scope

- Splitting the abstract bases into file-backed and not-file-backed halves.
- A `FILE_UPLOAD` question type, question pools, per-attempt records, timers — all live in their own
  drafts and none of them depend on this.
- Admin-authored (non-file-backed) forms. The extraction does not add them; it stops the boundary
  from being the reason they cannot exist.
- Reconciling the `Won't do` entry in `final_pre_deploy_db_structure_cleanup`. Named here, decided
  by the user.

## Open questions for the user

1. **Does this supersede the `Won't do` entry?** That spec is *in progress* and the two documents
   now disagree in writing. **Deferred** — the two cannot both stand; pick one and edit the loser.
2. **Where does this sit relative to the migration reset?** **Decided: before it.**
   `final_pre_deploy_db_structure_cleanup` runs afterwards, so there is no database to preserve, no
   backfill and no content-type surgery.
3. **Breakage posture.** **Decided: loud break, no compatibility shims** — but a *code* break only.
   `upgrade_notes.md` covers import paths, labels and template paths; there is no data recipe to
   write.
4. **App name.** **Decided: `freedom_ls/form_engine/`, `label = "freedom_ls_form_engine"`.** Not a
   bare `freedom_ls/forms/` — it reads as `django.forms` and collides with the per-app `forms.py`
   convention.
5. **Does `application-forms` get re-scoped onto the shared primitive, or does it ship its copy
   first?** **Deferred** — this is the decision that determines whether the extraction pays for
   itself.
6. **A `content_base` app for the abstract bases.** **Decided: yes** — zero migrations, breaks the
   mutual edge, dissolves the registry problem, and can land ahead of everything else. Named
   `content_base`, not `content_engine_base`. What is *not* decided is whether the pydantic bases
   and `_registry` go with it in the same cut or follow separately.

## Reference research

- `research_reuse_case.md` — the prior verdict, and the evidence its revisit trigger has fired;
  would-be consumers ranked by strength; the cost of not extracting.
- `research_current_coupling.md` — where every piece of form code lives today and how course-bound
  each piece is, including the ten places that assume a form is reached through a course.
- `research_boundary_options.md` — the option space, naming, the context-backend pattern, the
  seven-edges argument, and external precedent (Moodle, Open edX).
- `research_extraction_mechanics.md` — the cost sheet: abstract bases, registry, importer, table
  renames and the content-type remap, plugin re-sync, sequencing against in-flight specs, and the
  new-app checklist.
