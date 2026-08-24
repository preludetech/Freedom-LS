# Research: where to draw the boundary, and what to call it

## Executive summary

**Recommendation: option B — one `form_engine` app owning definition, attempts and marking, with the
consequences of a result staying with consumers behind a `form_attempt_completed` signal.** Option A
(a `models/` package inside `content_engine`) is not a competing option — it is a no-regret
prerequisite that unlocks no reuse. Option C (three apps: definition / responses / marking) is
rejected because marking is not separable from `Form.strategy` and it multiplies edges for no
consumer. Option D (leave the models put, add form identity and a context backend) delivers **all**
of the reuse value on its own — it is the strongest rival, not a straw man, and the right answer if
the move is rejected on design grounds. Naming: `freedom_ls/form_engine/`
with `label = "freedom_ls_form_engine"`; not a bare `freedom_ls/forms/`, and no `Form` →
`Questionnaire` rename. The authorisation seam should copy the existing `COURSE_ACCESS_BACKEND`
settings-string pattern rather than invent one. On the prior research's strongest objection — that
extraction adds roughly seven graph edges — the answer is that edge count is not coupling: those
imports exist today and the graph simply cannot see them, and one worse edge
(`content_engine → course_applications`) gets prevented.

---

## 1. The option space

### Option A — `models/` package inside `content_engine`

Split `content_engine/models.py` into `models/base.py`, `models/content.py`, `models/course.py`,
`models/forms.py`, `models/files.py`, all re-exported from `models/__init__.py` so every existing
`from freedom_ls.content_engine.models import Form` keeps working. Same app label, same tables.

**Pros.** Zero migrations, zero new edges, single PR, mechanical. Django does not care whether a
model class is defined in `models.py` or `models/forms.py`, only which app config owns it. This is
the standing decision in `final_pre_deploy_db_structure_cleanup` ("do later", no deadline pressure).

**Cons.** Unlocks nothing. Every drafted duplicate still gets built, because the barrier was never
file layout.

**Verdict: not an alternative — a prerequisite.** Do it first regardless of what follows. It makes
the eventual move a directory rename rather than a surgical extraction from a 605-line file, and if
the extraction is rejected it is still worth having.

### Option B — one `form_engine` app: definition + attempts + marking — **recommended**

Owns: `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`, `QuestionType`,
`FormStrategy`; `FormProgress`, `QuestionAnswer`; `scoring.py`, `submissions.py`; the form admin,
factories, pydantic models and save functions; `quiz_verdict()` and `count_form_questions()`.

Emits `form_attempt_completed`. Does **not** own: `CourseProgress`, `TopicProgress`, the completion
receiver, the player views, `unpassed_forms()`, `get_content_status()`.

**Pros.**
- Puts the whole "a form, an attempt at it, and its score" concept behind one boundary. A consumer
  that wants a questionnaire imports one app.
- Marking sits with the thing it marks. `Form.strategy` is a field on `Form`;
  `FormProgress.score()` dispatches on it; the pass mark is `Form.quiz_pass_percentage`. Nothing is
  gained by putting the dispatch in a different app from the enum.
- Deletes a real edge: `learner_progress → content_engine` exists partly for `Form`,
  `FormQuestion`, `QuestionOption`, `FormStrategy` and `FREE_TEXT_QUESTION_TYPES`.
- Makes the `content_engine → course_applications` inversion unnecessary.

**Cons.**
- Five table renames. **Free at the database level** — the extraction lands before
  `final_pre_deploy_db_structure_cleanup`, whose reset regenerates every `0001_initial` afterwards,
  so there is no data to preserve and no content-type remap (`research_extraction_mechanics.md` §4).
  Still a code-level break for downstream projects, and still needs `upgrade_notes.md`.
- Roughly seven new graph edges (§4 below).
- A `content_base` app for the abstract bases and the pydantic registry. Abstract models mean zero
  tables and zero migrations, so this is nearly free — and it is what keeps `content_engine` and
  `form_engine` from importing each other. Without it the pair is mutual
  (`form_engine → content_engine` for the bases, `content_engine → form_engine` for the loader);
  with it the graph is a DAG. See `research_extraction_mechanics.md` §1.

### Option C — three apps: definition / responses / marking

**Rejected.** The user's framing — "layer marking things on top of that app somewhere else" — is
right about the *shape* of the system but the cut lands in the wrong place. There are two candidate
cuts and only one is real:

- **definition | (attempt + marking)** — this is option B, and the cut is real: authoring-time shape
  versus a user's run at it.
- **(definition + attempt) | marking** — not real. `scoring.py` is 36 lines of pure function and
  `FormProgress.score()` is a five-line dispatch on a field of `Form`. Separating them creates an
  app whose entire content is one `if/elif`, and every scoring change then touches two apps.

What genuinely *is* layered on top is the **consequence** of a result: course progression gating
(`get_content_status`, `unpassed_forms`), deadlines, cohort reporting, at-risk rules. Those already
live in the apps that own the policy, which is the correct place for them, and option B leaves them
there. So the three-layer instinct is already satisfied — the layers are
`form_engine` / consumers / their UIs, not definition / response / marking.

Note one caveat worth keeping on file: `research_form_schema.md` argued that application answers are
PII and should not share storage with quiz answers. That is an argument about the *response* table,
not the *definition* models, and it survives option B intact — a consumer with PII concerns can
store its own answer rows against shared question definitions. If that becomes a requirement, the
cut is "shared definitions, per-consumer responses", which is still two apps, not three.

### Option D — seam only: leave the models where they are

Add form identity (slug route, `preview_url()`), a form-context/authorisation backend, and a
context-agnostic runner — all inside `content_engine` and `learner_interface`. Move nothing.

**Pros.** Delivers 100% of the reuse value. Zero migrations, zero table renames, zero new edges, no
upgrade notes, no downstream recipe. Can land at any time, before or after deploy. Directly attacks
the actual blocker identified in `research_current_coupling.md`.

**Cons.** Leaves `content_engine` as the home of a primitive that is no longer about course content,
which is a naming lie that gets more expensive to correct with every downstream project that writes
against it.

**Verdict: the strongest rival, and the two are not exclusive** — B and D are the two halves of the
same work. What used to separate them was cost: B was cheap only inside a closing migration window,
D was the same price forever. With the extraction sequenced ahead of
`final_pre_deploy_db_structure_cleanup`, B's database cost is gone outright, so the only remaining
question is whether the boundary is right. D stays the correct answer if the move is rejected on
design grounds.

---

## 2. Naming

**`freedom_ls/form_engine/`, `label = "freedom_ls_form_engine"`.**

- **Against a bare `freedom_ls/forms/`.** Every FLS app may have its own `forms.py` holding
  `django.forms` subclasses — `accounts/registration_forms.py`, `educator_interface/forms.py`,
  `reports/forms.py`, `site_aware_models/forms.py`, `webhooks/forms.py` already do. An app named
  `forms` makes `freedom_ls.forms` read as the Django module at every import site, and a downstream
  project with its own `forms` app cannot start without the label.
- **`form_engine` parallels `content_engine`,** which is the established vocabulary for "the app
  that owns a family of authored models".
- **The label is mandatory and load-bearing.** 20 of 23 FLS apps set
  `label = "freedom_ls_<app>"`, and `final_pre_deploy_db_structure_cleanup` Decision 6 proposes a
  conformance guardrail asserting it. Without it the tables land as `form_engine_*` and collide with
  any downstream app of the same name.
- **Against renaming `Form` → `Questionnaire`.** Tempting, since the domain is widening past quizzes.
  Rejected: it multiplies the size of the break — every import, template variable, URL name, test and
  authoring doc — for vocabulary alone, and `learner-terminology-rename` is fresh evidence of what
  that costs. The word "form" is already the authoring vocabulary in `demo_content/` and in
  `claude_plugins/fls-content/skills/content-types/resources/form-files.md`.

Alternatives considered and rejected: `questionnaires` (renames the domain without renaming the
models — worse), `assessments` (narrower than the use cases that motivated this), `forms_core`
(no precedent in the tree).

---

## 3. The authorisation seam should copy an existing pattern

FLS already has the exact pattern this needs, twice, and the comment above one of them states the
principle better than a new design would:

```python
# config/settings_base.py:419-425
# Ships with applications enabled. The free-only core default backend
# ("freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend") is the no-applications
# fallback. This is a project settings string in `config`, NOT a course_access import — so
# course_access still never depends on course_applications.
COURSE_ACCESS_BACKEND = (
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)
```

`COURSE_ACCESS_CONFIG_VALIDATOR` and `FREEDOM_LS_ICON_BACKEND` use the same idiom: a dotted path in
project settings, resolved via `import_string`, so the low layer never imports the high one.

Applied here, a **form-context backend** answers, for a `(user, form, context)` triple: may this user
answer it, where do they go on exit, and what chrome wraps the runner. The course player becomes the
first implementation rather than a special case; `application-forms` and a standalone-questionnaire
context become additional implementations. This keeps `form_engine` from ever importing `Course`.

Two things to get right, both learned from the existing backends:

- **Register, don't hardcode.** `course_access` ships a `FreeOnlyCourseAccessBackend` default so the
  core works with no configuration. A form-context backend needs the same: a default that permits a
  form to be answered only through a course, so behaviour is unchanged until someone opts in.
- **Keep the seam narrow.** `CourseAccessDecision` is a small typed result and `access_config` is
  documented BACKEND-PRIVATE (`content_engine/models.py:178-181`). Copy that discipline; a context
  backend that leaks course concepts into its return type has not decoupled anything.

This is **scope §3 of the idea and explicitly not part of the extraction cut.** It is recorded here
so the extraction does not accidentally foreclose it.

---

## 4. The seven-edges objection, answered

The prior research's most concrete finding, restated accurately:

> Splitting forms out doesn't shrink `content_engine`'s fan-in — it *doubles* it, giving every one
> of those six apps a second edge to maintain instead of one. […] the graph gains at least seven new
> edges […] for the same total amount of coupling, just spread thinner.

**Conceded: the count is correct.** `learner_progress`, `learner_interface`, `educator_interface`,
`reports`, `learner_management` and `qa_helpers` each import `Form` alongside `Topic`/`Course` in
the same functions, so each gains a `--> form_engine` edge, plus `content_engine --> form_engine`
for the loader and two edges into `content_base` for the bases.

One refinement before the substance: the `content_base` app trades the mutual
`content_engine ↔ form_engine` pair for two edges into an abstract-only app, at the cost of one
extra node and no migrations. The arithmetic barely moves; the *shape* does, because the result is
acyclic. A count that includes a cycle and one that does not are not comparable numbers.

Four things the count leaves out:

1. **Edges are not coupling; they are visible coupling.** Every one of those imports exists today.
   `docs/app_structure.md` currently shows one edge where there are two distinct dependencies,
   because both endpoints happen to live in one app. Extraction does not create the coupling — it
   stops hiding it. The document's own header calls itself "the authoritative picture of inter-app
   dependencies"; a picture that under-reports is worse than one with more arrows.
2. **One edge genuinely disappears.** `learner_progress → content_engine` exists for `Form`,
   `FormQuestion`, `QuestionOption`, `FormStrategy` and `FREE_TEXT_QUESTION_TYPES` — and, after the
   attempt models move, for `Course` in `signals.py` only. Replace that receiver with a signal
   subscription and the edge is gone outright, which is the same kind of win
   `final_pre_deploy_db_structure_cleanup` finding 6 counts as worth doing on its own.
3. **A worse edge is prevented.** `application-forms/idea.md:68-74` is prepared to add
   `content_engine → course_applications` — the content layer pointing at a consumer app. Seven
   sibling edges are a legibility cost; one inverted edge is a structural defect.
4. **The polymorphic call sites are honest.** `isinstance(item, Form)` next to a `Topic` branch is
   two real dependencies in one function. After extraction the import list says so.

**What the objection gets right and is not answered away:** `compliance-exam-remediation` wants a
`FormQuestion` (or per-option) pointer at a `Topic`/`Activity` for "reference relevant content". That
is an ordinary FK today and a cross-app FK afterwards. Cross-app FKs are ordinary Django, but this
one points *back up* into `content_engine` from `form_engine`, alongside the abstract-base edge. It
is a genuine cost, it is small, and it should be listed in the plan rather than discovered.

---

## 5. External precedent

The prior research surveyed this and its conclusion still holds on its own terms; extending it
rather than re-deriving it:

- **Moodle** moved question code out of the quiz module into a top-level, quiz-independent question
  bank in 1.6, so other activity types could reuse questions from a shared category hierarchy. The
  driver was **cross-activity reuse of individual questions**. The prior research noted FLS has no
  analogous driver, since `compliance-form-randomization` scopes V1 pools to a single form — and
  that remains true. But the *system-level* half of the precedent is the relevant one here: Moodle
  separated "a bank of questions" from "an activity that uses them" precisely because assessment
  outgrew the one activity it was born in. That is the situation `application-forms` describes.
- **Open edX** makes every unit of course content an XBlock: self-contained, with its own model,
  view and handler, runnable independently of any specific course. Adopting XBlocks wholesale would
  be exactly the scope creep the cleanup idea rules out. But the narrow lesson transfers and is the
  one this idea acts on: **the thing that makes a content unit reusable is that it has its own view
  and handler, not that it has its own table.** That is an argument for option D's seam being the
  valuable half — and for not mistaking the app move for the win.

Neither precedent supports "give the existing quiz models a Django app" as a self-justifying move.
Both support "make the assessment primitive addressable and reusable" once a second consumer exists.
That is why this idea recommends doing both, in the order the costs dictate.

---

## 6. Recommendation

**B, sequenced against D.**

1. Option A now — the `models/` package. No regrets either way.
2. Option B, before `final_pre_deploy_db_structure_cleanup` — so the reset that follows discards
   the migration history and there is no data to preserve. `content_snapshots` and
   `compliance-form-randomization` are paused until after deployment, so nothing competes for this
   tree.
3. Option D's seam when the first consumer needs it, which means re-scoping `application-forms` onto
   the shared primitive instead of letting it build its copy.

If B is rejected, do D anyway — it is where the reuse value actually is, and it costs nothing that
B was going to pay for.

status: ok
