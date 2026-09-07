# Research: what the reuse-of-`form_engine` decision requires of this spec

The reuse decision is made: `CourseApplication` gets a FK to `Form`, and application answers land in
`FormProgress`/`QuestionAnswer` — the same tables quiz answers use. This does not re-argue that
decision. It answers the question the August research (`research_reuse_case.md`) left open: PII
isolation "is still true, and still an argument for separate tables — but not for separate models."
Below is what has to be true of this spec's design for that isolation to actually hold once both
answer kinds share one table.

The first real form's questions (age, town/province, working status, ability to pay, nationality)
are exactly the kind of attribute FLS's own POPIA/GDPR research (`spec_dd/3. done/2026-03-13_21:21_security-audit/research_popia.md`,
`research_gdpr.md`) flags as needing tighter retention and access control than ordinary learner data.

## 1. Read paths — enumerated

There are exactly four code paths today that can read a `QuestionAnswer` row, plus the places a fifth
kind of answer-adjacent data (form progress rows) surfaces. Each is checked against the concrete
question: **could an educator's cohort report show an application answer sat before the applicant was
ever registered?**

### 1a. Django admin — `freedom_ls/form_engine/admin.py`

`FormProgressAdmin` (`form_engine/admin.py:191-228`) and `QuestionAnswerAdmin` (`:231-261`) are both
plain `SiteAwareModelAdmin`. Neither overrides `has_delete_permission` (unlike every content-definition
admin in the same file — `FormAdmin`, `FormPageAdmin`, `FormQuestionAdmin`, `FormContentAdmin`,
`QuestionOptionAdmin` — which all hard-code `return False`). Neither filters or flags by
`form.strategy`. `QuestionAnswerAdmin.list_display` includes `answer_preview` (`:254-261`), which
renders the raw `text_answer` or selected option text straight into the changelist row — this is
**correct exposure only if the spec's decision that "reviewing answers is Django-admin-only" also means
"whoever already has admin access to `QuestionAnswer` is an acceptable reviewer of application PII,"**
which is a scoping question, not a code bug (see §3).

This is a real leak surface for the review step, not a hypothetical: any staff user holding
`form_engine.view_questionanswer` (superuser, or any future grant — see `role_based_permissions/roles.py`,
where no role currently holds this permission) sees every application's age/town/province/nationality
answer interleaved with every quiz's answers, site-wide, with no course-level scoping. There is no
`GuardedSiteAwareModelAdmin` (`site_aware_models/admin.py:21-30`) in use here, so guardian's per-object
grants — the mechanism the rest of FLS uses for "this reviewer sees only their own cohort/organisation" —
do not apply to `QuestionAnswer` today.

### 1b. `freedom_ls/reports/indexes.py` — the cohort report

This is the path the prompt specifically asks about, and the answer is **no, an educator's cohort report
cannot see application answers, and it is not because of a filter — it is because the join chain that
builds the report can never reach an application's rows at all.**

- `build_course_catalogue` (`reports/indexes.py:218-260`) derives `catalogue.form_ids` exclusively from
  `reg.course.viewable_items()` — the resolved `Topic`/`Form` children of a course's content collection
  (`ContentCollectionItem`, per the domain glossary). A `CourseApplication.form` is reached through a
  direct FK on `CourseApplication`, never through `ContentCollectionItem`, so an application form is
  never a member of `catalogue.form_ids` regardless of anything else in the report.
- `load_form_progress_rows` (`reports/indexes.py:310-336`) additionally requires
  `course_attempt__course_progress__cohort_registration__in=...` — i.e. every `FormProgress` row the
  report can even query for must already have a `CourseFormAttempt` (`learner_progress/models.py:242-278`)
  linking it to a registered learner's `CourseProgress`. `CourseFormAttempt` rows are created in exactly
  one place, `get_or_create_incomplete` (`learner_progress/attempts.py:77-103`), which requires an
  existing `CourseProgress` — which requires an existing registration. An applicant, by definition, has
  no `CourseProgress` for the course they're applying to. So an application's `FormProgress` is created
  outside that helper (it must be — there is no registration to hang a `CourseFormAttempt` off), has no
  `CourseFormAttempt`, and is therefore structurally unreachable by `load_form_progress_rows`'s join.
- `load_selected_options_by_pair` (`:518-541`) is scoped to `completed_attempt_ids`, which
  `fold_form_progress_rows` (`:339-384`) builds only from rows `load_form_progress_rows` already
  returned — so the same exclusion holds one level down.

**This holds even after the applicant is later approved and registered**, provided (and only provided)
the approval step does not retroactively wire the applicant's existing application `FormProgress` into a
new `CourseFormAttempt`. Nothing in the current codebase would do that automatically — `get_or_create_incomplete`
always looks up by `(course_progress, collection_item)`, never by `(user, form)`, specifically to avoid
resuming an attempt from the wrong context (`learner_progress/attempts.py:1-14`) — but this is a design
constraint this spec must state explicitly for the approval work to inherit: **an application's
`FormProgress` must never be adopted into a `CourseFormAttempt`.** If a course ever needs the applicant to
also *sit* the same form as course content post-approval, that must be a fresh `FormProgress`, not the
application's.

### 1c. `freedom_ls/educator_interface/views.py` — the cohort data table

Same guard, independently implemented: `_progress_maps` (`educator_interface/views.py:441-467`) queries
`CourseFormAttempt.objects.filter(course_progress__cohort_registration=selected_reg, ...,
collection_item_id__in=visible_form_item_ids)`. Identical reasoning to §1b — an application `FormProgress`
has no `CourseFormAttempt`, so it cannot appear in an educator's per-learner grid either.

### 1d. `freedom_ls/learner_interface/views.py` — the learner's own results/runner pages

This is the course-content form runner (`get_or_create_incomplete`, `show_form_page`, etc., around
`learner_interface/views.py:924-1013`). It is keyed on a `CourseProgress`, so an unregistered applicant
cannot reach it for the application form — there is no `CourseProgress` to key on. This is *correct*
non-exposure, but it also means **this view is the wrong place to answer an application form**: it is not
merely unused by applicants today, it cannot be used by them without first inventing a `CourseProgress`
that shouldn't exist pre-registration. Whatever view lets an applicant answer their form must be new
code in `course_applications`, not a reuse of this one (see §5).

The applicant's own status page, `course_applications/application_status.html` via
`application_status` (`course_applications/views.py:65-81`), does not read `QuestionAnswer` at all today
— it is a static confirmation. It already gets ownership right
(`get_object_or_404(CourseApplication, pk=pk, user=request.user)`, `views.py:76`), which is the pattern
every new read/write path for answers must copy.

### 1e. API

`learner_interface/apis.py` has one `FormProgress`-reading block and it is entirely commented out
(`apis.py:3-123`). There is no live API surface reading `QuestionAnswer` or `FormProgress`.

**Summary table:**

| Path | Function | Can it reach an application answer? | Why / why not |
|---|---|---|---|
| Django admin | `QuestionAnswerAdmin`, `FormProgressAdmin` | **Yes** | No filter by strategy or by application-ness; this is the intended, decided review surface — see §3 for what it needs |
| Cohort report | `reports/indexes.py: load_form_progress_rows` | **No** | Requires `CourseFormAttempt`, which application `FormProgress` never gets |
| Educator data table | `educator_interface/views.py: _progress_maps` | **No** | Same `CourseFormAttempt` requirement |
| Learner/applicant results runner | `learner_interface/views.py` | **No** (route doesn't apply) | Requires `CourseProgress`, which doesn't exist pre-registration |
| API | `learner_interface/apis.py` | **No** | Dead code, commented out |

## 2. The discriminator

**Use `Form.strategy`, with a new `FormStrategy` member for application forms** — not the
`CourseApplication` FK, and not the absence of a `CourseFormAttempt`.

`FormStrategy` today (`form_engine/enums.py:25-29`) has exactly two members: `CATEGORY_VALUE_SUM` and
`QUIZ`. Add a third — e.g. `FormStrategy.APPLICATION` — and require every `Form` used as
`CourseApplication.form` to carry it. This is a one-hop, indexed-by-FK check
(`form_progress.form.strategy` or, in a `.values()`/`.annotate()` query,
`form_progress__form__strategy`), it lives on the `Form` row itself (permanent, travels with the
definition regardless of what happens to any individual application), and it is the same field every
other strategy-conditional branch in the codebase already keys on — `build_course_catalogue`
(`reports/indexes.py:248`), `FormProgress.score()` (`form_engine/models.py:495-503`), `get_incorrect_quiz_answers`
(`:521`). A reporting or export path that needs to defensively exclude application rows —
even though §1b shows the *existing* cohort report already can't reach them structurally — should do so
by excluding `strategy=FormStrategy.APPLICATION`, not by re-deriving "not an application" from the
absence of a `CourseFormAttempt` (a negative, structural inference that only happens to be true today and
is easy to invalidate by accident — see the adoption warning in §1b).

The `CourseApplication` FK is the wrong thing to standardize the discriminator on, for two reasons.
First, it is a property of the *application record*, not of the *answer row* — testing it means a
reverse join from `CourseApplication` rather than a filter reachable directly from `QuestionAnswer` or
`FormProgress`. Second, whatever `on_delete` this spec picks for `CourseApplication`'s pointer at its
`FormProgress` (§4 recommends nullable/`SET_NULL`) means that pointer can legitimately go absent while
the `FormProgress`/`QuestionAnswer` rows still exist — so "does a `CourseApplication` currently point at
this" is not even a stable test of "is this an application answer" once retention work happens.

Concretely, this spec should add the enum member and enforce (at minimum via a `full_clean`/model
validation on `CourseApplication`, not merely a convention) that `CourseApplication.form.strategy ==
FormStrategy.APPLICATION`. That is also what closes the one real configuration hole: nothing today stops
an admin from placing an `APPLICATION`-strategy `Form` into a course's content collection as if it were a
quiz. If that ever happened, registered learners would start creating ordinary `CourseFormAttempt`-linked
`FormProgress` rows against a form built for age/nationality/employment-status questions, which
*would* then surface in reports and educator views — not because the applicant's original answers leaked,
but because the same `Form` definition was reused somewhere it shouldn't be. The strategy field is the
one place to make that check land.

## 3. Admin exposure

The decision that review is Django-admin-only means the admin **is** the access-control boundary for
application PII, not just a UI convenience — so it has to be treated with the same rigor as
`LegalConsent`'s admin, which is FLS's existing precedent for admin-facing consent/PII data
(`accounts/models.py:165-217`, `fls-dev:registration` skill).

**Where `LegalConsent`'s precedent applies directly:**

- `LegalConsent`'s admin is registered fully read-only — no add, no change, no delete
  (`fls-dev:registration` SKILL.md: "The admin is read-only: no add, no change, no delete"). Today's
  `QuestionAnswerAdmin` and `FormProgressAdmin` are not read-only — `FormProgressAdmin` doesn't override
  `has_delete_permission` at all (default Django behaviour: deletable if the staff user holds
  `delete_formprogress`), and both admins' fields are editable except the timestamp fields. For
  application answers this is inverted from what the feature wants: **quiz answers are legitimately
  editable/re-scoreable by no one in the admin today either**, but an application reviewer changing an
  applicant's stated nationality or ability-to-pay from the admin, or deleting the evidentiary record of
  what they answered, is a materially different risk than editing a quiz score. The spec should make
  `QuestionAnswer` (and, for rows belonging to an application, `FormProgress`) admin-read-only for the
  application case, following `LegalConsent`'s model-level `save()` guard (`accounts/models.py:198-210`)
  plus a read-only admin registration, rather than relying on the same shared admin surface quizzes use.
  Because `QuestionAnswer` is one table for both purposes, this has to be either (a) a per-strategy
  conditional in `QuestionAnswerAdmin.has_change_permission`/`has_delete_permission` keyed off
  `obj.question.form_page.form.strategy == FormStrategy.APPLICATION`, or (b) a second, dedicated
  `ModelAdmin` registered against a filtered queryset/proxy for application answers specifically. Given
  the shared-table decision, (a) is the smaller change and keeps one admin surface; (b) would need a
  proxy model, which is more machinery than this feature has asked for.
- `LegalConsent`'s admin ties directly to the model's own append-only enforcement
  (`accounts/models.py:198-210`, "this guard only covers `.save()`... the admin is registered as fully
  read-only as the second layer of defence"). The equivalent second layer for `QuestionAnswer` is
  needed precisely because `.set()` on `selected_options`, direct `.save()`, and `QuerySet.update()`/
  `bulk_update()` all currently reach the row unguarded.

**Where `LegalConsent`'s precedent does not fit:**

- `LegalConsent` is one row per consent event and is genuinely append-only by nature (a consent, once
  given, is a historical fact). Application answers are **not** append-only in the same sense during the
  draft phase — an applicant must be able to correct an answer before submitting (see §5, threat 3), so
  the read-only-after-the-fact boundary has to be "read-only once submitted", keyed on `CourseApplication`
  state, not "read-only from the moment the row exists." `LegalConsent`'s all-or-nothing read-only admin
  is the wrong shape to copy literally; the *pattern* (model-level guard + admin-level second layer) is
  right, the *trigger condition* is different.
- `LegalConsent` has no site-scoped-but-not-course-scoped review problem, because nobody reviews
  `LegalConsent` per-course. Application answers are reviewed per-course (an instructor should see their
  own course's applicants, not another course's). `SiteAwareModelAdmin` scopes to site only; it has no
  concept of "this course's applications." Nothing in `role_based_permissions` (`roles.py:13-102`) grants
  any role today a `view_questionanswer`/`view_formprogress` permission, so in practice only superusers
  can review right now — which is *accidentally* safe rather than *designed* safe. The spec should either
  (a) explicitly restrict `QuestionAnswer`/`FormProgress` admin visibility to superusers until a
  scoped-review permission exists (i.e., document the current de facto restriction as the deliberate
  boundary, not an oversight), or (b) if any non-superuser role is meant to review applications in this
  iteration, build that on `GuardedSiteAwareModelAdmin` (`site_aware_models/admin.py:21-30`) with a
  guardian per-course grant, mirroring how instructor/TA roles are object-scoped elsewhere
  (`role_based_permissions/roles.py:32-57`). Do not grant a bare `view_questionanswer` Django permission
  to `instructor`/`ta`/`organisation_staff` — that permission is table-wide, not course-scoped, and would
  hand every instructor every course's applicants' PII.

**Concretely, what the admin needs, minimum:**
- `list_display`/`fieldsets` on `QuestionAnswer` and `FormProgress` should not change shape per-strategy
  (one admin, one table), but write access to an application-strategy row should be denied once its
  `CourseApplication` has left the applicant-editable state — enforced in the admin (`has_change_permission`)
  and, per the `LegalConsent` pattern, in the model too.
- `QuestionAnswerAdmin.answer_preview` (`admin.py:254-261`) is fine to keep for reviewers — showing the
  actual PII to a reviewer is the point — but it means the admin's `list_display` itself is a place a
  screenshot or shared-screen review session leaks PII more easily than a detail page. Not a code change;
  a note for whoever writes the reviewer-facing product doc.
- No file-upload question type exists in this form (age/town/province/employment/pay/nationality are all
  text/choice), so none of `content_engine`'s upload/serving-permission machinery is implicated here.

## 4. Retention and deletion

### The chain as it stands today

- `User → FormProgress`: `CASCADE` (`form_engine/models.py:205-207`).
- `FormProgress → QuestionAnswer`: `CASCADE` (`form_engine/models.py:575-577`, via `QuestionAnswer.form_progress`).
- `FormProgress → Form`: **`PROTECT`** (`:202-204`) — "an attempt is the audit record of a sitting, so
  deleting the form out from under it would erase what was answered." Applies unchanged to application
  forms: an admin can never delete the `Form` row backing an application config once anyone has started
  one. Same behaviour as quizzes; not a new risk.
- `QuestionAnswer → FormQuestion` (the `question` FK): **`PROTECT`** (`:578`) — blocks deleting a single
  question definition while any answer (quiz or application) references it. Also unchanged; also not new.
- `User → CourseApplication`: `CASCADE` (`course_applications/models.py:32-36`).
- `CourseApplication → Course`: `CASCADE` (`:37-41`).

**Deleting a `User` today cascades correctly and completely** through every table an application would
touch: `User → FormProgress → QuestionAnswer` and `User → CourseApplication`, both `CASCADE` all the way
down. There is no `PROTECT` anywhere on the `User` side of this chain. So a full-account deletion is
structurally satisfiable today, mechanically — but it is not what "delete a rejected applicant's answers"
usually means, because it deletes the *entire account*: every other course's progress, cohort membership,
quiz history, everything. Nothing in FLS lets you delete *just* the PII from one application while leaving
the person's account and their other course history intact — because that requires deleting one specific
`FormProgress` (which is structurally possible: `FormProgress.delete()` cascades cleanly to its
`QuestionAnswer` rows and nothing else, since it has no `PROTECT` pointing at it), and no admin/workflow
surface distinguishes "this `FormProgress` is an orphaned application sitting, safe to delete on its own"
from "this `FormProgress` is a quiz attempt whose deletion would silently corrupt a `CourseProgress`
percentage via its `CourseFormAttempt`." `FormProgressAdmin` doesn't override `has_delete_permission`
(§3), so the *capability* already exists for a staff user with `delete_formprogress`; there is simply no
guidance or scoping saying it is safe to use for an application `FormProgress` and unsafe for a quiz one.
The `FormStrategy.APPLICATION` discriminator from §2 is what makes that distinction cheap to check before
someone (or some future tooling) reaches for it.

### What this spec must decide, specifically

`CourseApplication` gains a FK to `Form` (the config) and needs some way to reach the specific
`FormProgress` holding one applicant's answers (a FK either direction — most naturally
`CourseApplication.form_progress`, a nullable one-to-one, mirroring how `CourseFormAttempt.form_progress`
is the one-to-one linking a sitting to its course-side row). The `on_delete` on that new FK is the one
concrete decision this research flags:

**Recommendation: `CourseApplication.form_progress` should be nullable, `on_delete=models.SET_NULL`.**
This mirrors an existing FLS pattern in the same neighbourhood — `CourseFormAttempt.collection_item`
is nullable with `on_delete=SET_NULL` specifically so "removing a placement does not erase the sitting"
(`learner_progress/models.py:261-267`). The same shape applies here in reverse: a future purge of the
*PII payload* (the `FormProgress`/`QuestionAnswer` rows — the age, town, nationality, etc.) should be a
single clean delete that does **not** collaterally destroy the review audit trail that the (not-yet-built)
approval workflow will hang off `CourseApplication` — its state, `decided_at`, `decided_by`,
`ApplicationNote`/`ApplicationStateTransition` rows named in `course_applications/models.py:23-27`. If
this FK were `PROTECT` instead (mirroring `FormProgress.form`), a purge would be blocked outright as long
as the `CourseApplication` still exists — which is backwards for a rejected/withdrawn applicant, since
the audit record is exactly the thing you want to keep *after* the PII is gone. If it were `CASCADE` in
the `CourseApplication → FormProgress` direction, deleting the `FormProgress` would also silently delete
the review decision itself, which is the wrong thing to lose.

### What is and isn't satisfiable

Getting the FK direction/`on_delete` right (above) is what makes a **future** targeted deletion capability
possible without a schema change at that point. It does not, by itself, give FLS a deletion-request
*workflow* — no such workflow exists anywhere in FLS today (no self-service or admin-triggered
"erase my data" flow was found; `spec_dd/3. done/2026-03-13_21:21_security-audit/research_popia.md` and
`research_gdpr.md` both list "account deletion / right to erasure" as work items, not shipped features).
**Building that workflow is out of scope for this spec** (see §6) — the ask here is narrower: don't choose
an `on_delete` that forecloses it later.

## 5. What the threat model will ask

None of the following controls exist today, because none of the code they'd apply to exists today — the
applicant-facing "answer the application form" view is new work this spec scopes. Naming that plainly
rather than softening it:

1. **IDOR on a `FormProgress`/`CourseApplication` belonging to another applicant.** No control exists yet
   because no view exists yet. It must copy `application_status`'s pattern exactly:
   `get_object_or_404(CourseApplication, pk=pk, user=request.user)` (`course_applications/views.py:76`),
   then operate on `application.form_progress` — never accept a bare `FormProgress` pk from a URL or form
   field. UUID primary keys (`SiteAwareModel`) make guessing infeasible but are not an ownership check on
   their own and must not be treated as one.
2. **Cross-site read through a non-site-scoped query.** Covered automatically for any view running inside
   a normal request, because `SiteAwareManager.get_queryset()` (`site_aware_models/models.py:65-76`)
   filters by the thread-local request's site unconditionally. This stops holding the moment code runs
   without a request — exactly why `reports/indexes.py` filters every loader by an explicit `site_id=`
   parameter (`indexes.py:1-15`, "runs from a background task, which has no HTTP request"). If any
   application-review automation (digest email, export, background approval hook) is added later, it
   must filter `site_id=` explicitly the same way; nothing enforces that generically, and it is easy to
   get wrong by copying a view-layer query into a task.
3. **An applicant editing answers after submission.** `FormProgress.save_answers()`
   (`form_engine/models.py:290-311`) has no state check of any kind — it will upsert answers on any
   `FormProgress` regardless of `completed_time`. No existing caller needs to guard this today because
   the course-content runner controls *when* it's called, not `save_answers` itself. The new
   application-answering view must enforce "no further writes once submitted" itself, keyed on
   `CourseApplication`'s state once the review FSM lands (`course_applications/models.py:23-27` — currently
   there is no state at all, so today there is *nothing* stopping a re-POST after submission; this is a
   gap that exists in the current standalone model and must be closed by the time answers can be
   submitted).
4. **A form bound to a course the applicant never applied to.** Controlled by never resolving `Form` from
   client input: the view must derive the form as `application.form` (from the owned, looked-up
   `CourseApplication`), never accept a `form_id`/`form_slug`/`course_slug` from the POST body to select
   which form's questions to save against.
5. **Mass assignment through the answer-saving path.** `save_answers()` only ever writes answers for the
   `questions` iterable its caller passes in (`form_engine/models.py:299-311`); it reads
   `post_data.getlist(f"question_{question.id}")` / `.get(...)` keyed by *known* question objects, not by
   whatever keys the POST body happens to contain, so a client cannot inject an answer for a question
   outside that iterable. This safety is entirely inherited from the caller's `questions` argument — the
   existing course runner sources it from `page_questions()` (`form_engine/queries.py`), scoped to one
   form's one page; the new application view must do the same, deriving `questions` from
   `application.form`'s own pages, never from anything in the request. Separately, and pre-existing:
   `submitted_option_ids()`/`selected_options.set(...)` (`models.py:310`, `submissions.py:13-15`) does not
   verify a submitted option id actually belongs to the question being answered — any valid
   `QuestionOption` pk from anywhere (a different question, a different form) would be accepted into the
   M2M without error. This is not introduced by the reuse decision and is not specific to application
   answers, but it now also applies to them, and no existing control catches it.
6. **A `Form` used for applications also being placed as course content.** Covered in §2 — nothing today
   prevents an `APPLICATION`-strategy `Form` from being added to a course's `ContentCollectionItem` tree
   like an ordinary quiz. If that happened, registered learners' answers to it would flow through the
   ordinary `CourseFormAttempt` path and *would* surface in reports/educator views — correctly, because at
   that point they're the registered learner's own quiz-shaped answers, not the original applicant's. The
   risk is applicant confusion/data-shape mismatch (a nationality/pay-method "quiz" appearing in a course),
   not a PII leak of the original application — but it is exactly the kind of admin misconfiguration the
   `strategy` validation in §2 should make impossible rather than merely discouraged.

## 6. What this spec should not build

Checked against what the June 2026 research (`research_form_schema.md`) floated for a *separate-model*
application system, and against what's actually needed for this shared-table, no-file-upload, first form:

- **Encryption at rest.** June research §1 raised it (`spec_dd/0. drafts/encryption-at-rest`) as a reason
  favouring separate tables. It is correctly out of scope now: `deployment-security-checklist.md` §2/§6
  already covers database and backup encryption at the infrastructure layer, which applies to this data
  exactly as it applies to every other row in the same database. No new field-level encryption is being
  asked for and none should be added.
- **Virus scanning.** June research §3 designed a `scan_status` field and a ClamAV pipeline for
  `ApplicationFile`. This form has no `FILE_UPLOAD` question type — age, town, province, working status,
  pay method, and nationality are all text/choice answers. Nothing here is a file. If a later form adds a
  file-upload question, that spec is where scanning gets designed; it does not belong in this one.
- **A retention scheduler / automated purge.** The security-audit research's `RetentionMixin` pattern and
  `PROGRESS_RETENTION_DAYS`-style settings (`research.md`/`research_gdpr.md`/`research_popia.md`) are
  future, standalone work items, not shipped anywhere in FLS today. This spec's job is narrower and
  already stated in §4: pick an `on_delete` that doesn't block a *future* targeted purge. Building the
  scheduler itself is out of scope.
- **Field-level redaction in the admin.** Masking specific answers (e.g., showing nationality only to
  certain reviewers) was never proposed even in the June separate-model research; the access control the
  decided design relies on is "admin-only, and admin visibility is the boundary" (§3), not per-field
  masking within the admin. Don't add it.
- **A new approval-workflow audit model in this spec.** `ApplicationNote`/`ApplicationStateTransition`
  and the FSM state field are explicitly future work already named in
  `course_applications/models.py:23-27` ("when application review lands"). This research's only
  dependency on that future work is the `on_delete=SET_NULL` recommendation in §4, which is additive and
  does not require building the FSM now.

status: ok
