# Research: what queued work implies about today's schema

## Executive summary

Ten of the eleven queued items assessed here imply **nothing** about today's schema: every one of
them, if built as currently sketched, adds a new table and/or nullable field to a model that either
already exists or is itself brand new — nothing forces a change to an existing table's shape, keys,
or uniqueness. Two things happened while researching this that make the "implies nothing" answer
stronger than it would otherwise look: first, `basic_reports` and the Organisation layer have both
already merged into `main` since this idea was written (`freedom_ls/reports/models.py`,
`freedom_ls/organisations/models.py`, `Cohort.organisation`/`UserCourseRegistration.organisation`
all exist today, not just in spec form) — so `report-upgrades`, which this task treats as a queued
unknown, is actually additive against models that are already sitting in the repo, which is about as
low-risk as "implies nothing" gets. Second, `CourseApplication`'s own docstring
(`freedom_ls/course_applications/models.py:23-29`) already states, in writing, that its state-machine
expansion is additive and instructs future contributors not to architect it away — the roadmap
pressure this task went looking for has already been pre-empted at the model layer for that one item.
The one item that does imply something is `referral-link-tracker`'s deliberate choice not to subclass
`SiteAwareModel` — not because it needs a `site` field it doesn't have (it takes an optional
`contrib.sites` FK instead, by design), but because it is set to become the first app in the entire
dependency graph with zero edge to `site_aware_models` in `docs/app_structure.md`, a graph where every
other domain app has that edge. That isn't a schema change and doesn't need one; it needs a one-line
policy decision recorded now so a future contributor (or `/plan_structure_review`) doesn't "fix" it.
Separately, the one genuine convergent-demand signal — two independent features both wanting a
run/registration id on their records — is already flagged in `better_course_progress_tracking/idea.md`
itself and is fully satisfied by that spec landing; nothing new needs deciding for it either.

## Verdict table

| # | Item | Verdict | Why |
|---|---|---|---|
| 1 | `certificates` | implies-nothing | Needs a new `Certificate` model (hash/token, public verify URL) FK'd to a frozen completion record. `better_course_progress_tracking/idea.md:167-171` already names the exact requirement ("must bind to a frozen completion record rather than a live `(user, course)` query") and the sibling spec's `CourseRun` (a new, per-pass row, `idea.md:41-54`) *is* that frozen record. `certificates` needs zero of its own structural decisions once that lands — just a new, additive table pointing at it. |
| 2 | `post-mvp` (payment gateway + per-seat billing) | implies-nothing | `User` is already site-scoped (`freedom_ls/accounts/models.py:67-82`, via `SiteAwareModelBase`), so a per-Site seat count (`User.objects.filter(site=..., is_active=True).count()`) needs no new anchor today. If billing is ever scoped to Organisation instead of Site, the anchor that would be missing — "who belongs to this organisation" as a stored fact rather than a derived query — is exactly what the sibling `learners-associated-with-organisations` spec's new `Learner` model (`idea.md:11-20`) is being built to answer. That gap is being closed by an already-assumed-landing sibling, not by this cleanup. |
| 3 | Notification system + `student-communication` | implies-nothing | The comms design's audience/config-precedence chain (`student-communication/idea.md:108-157`) is deliberately built on generic references *into* `UserCourseRegistration`, `CohortCourseRegistration`, `Course`, and `Site` — none of which need a field added to host that reference. The idea doc is explicit that these are spec/plan-phase model decisions (`idea.md:13-14`, `176`), and nothing in the guiding principles requires any existing table to change shape. |
| 4 | `xapi_implementation` | implies-nothing (today) | The app doesn't exist yet (`freedom_ls/xapi_learning_record_store` per `docs/app_structure.md:37`, still the un-renamed stub). Whatever event table it eventually gets is entirely new, so any run/registration id it wants is a new nullable FK on a new table — see Convergent demand below for the one thing worth writing down for whoever specs it. |
| 5 | Course application review/approval | implies-nothing | `CourseApplication`'s own docstring (`freedom_ls/course_applications/models.py:1-29`) already documents the exact expansion ("gains `state = FSMField(protected=True)`... `ApplicationNote` + `ApplicationStateTransition`... swap the plain constraint for an active-state partial index") and closes with "Do not architect these away — leave this model standalone and additive." The roadmap pressure this task is checking for has already been written into the model itself. |
| 6 | `compliance-form-randomization` | implies-nothing | The new sub-page "group" primitive sits between `FormPage` and `FormContent`/`FormQuestion` (`freedom_ls/content_engine/models.py:456-568`) as a new table with new, nullable FKs from those two existing models — additive, no change to their current `order`/`form_page` shape. The per-attempt realized-order record is a new JSON-shaped field on `FormProgress`, which already carries exactly this kind of thing (`scores`, a `JSONField`, `freedom_ls/student_progress/models.py:91-93`) — direct precedent for adding another one. |
| 7 | `compliance-exam-remediation` | implies-nothing | Optional per-answer explanation/reference text is a new nullable field on `FormQuestion`/`QuestionOption` (`freedom_ls/content_engine/models.py:503-568`), which today hold only `question`/`text` content fields of the same shape. No key or uniqueness changes. |
| 8 | `report-upgrades` | implies-nothing | Both models it upgrades — `GeneratedReport` (`freedom_ls/reports/models.py:44-95`) and `Organisation` (`freedom_ls/organisations/models.py:28-76`) — already exist in `main`, not just in spec form (`basic_reports` and the Organisation cut have both merged; see recent commits). `ReportConfig`/`ReportAtRiskRule` are new models; the resolved-config JSON is a new nullable field on `GeneratedReport`. Note separately: this idea's own header (`report-upgrades/idea.md:1-9`) says it "needs revision before it is specced" because `basic_reports` removed the settings-module rules hook it was written against — it is not spec-ready, but that is an idea-freshness problem, not a schema-pressure one. |
| 9 | `multi-factor-authentication` | implies-nothing | An MFA device/secret table is a new table FK'd to `User`, no different in shape from any other `*Factory`-adjacent child table already in the codebase. "Configurable per test" is a new nullable boolean on `Form`, which already carries a boolean of exactly this shape (`submit_on_exit`, `freedom_ls/content_engine/models.py:441-447`). |
| 10 | `re-consent-idea.md` (T&C versioning) | implies-nothing | `LegalConsent` is already an append-only, per-document-type, per-version row (`document_version`, `git_hash`, `timestamp`, `freedom_ls/accounts/models.py:161-213`) and the "current" version is already resolved from versioned frontmatter in git at request time (`freedom_ls/accounts/legal_docs.py:56-66, 220-274`), not from a mutable DB row. "Latest accepted version for user X" vs. "current active version" is already a two-query comparison against data that exists today. A grace-period toggle is a new nullable field on `SiteSignupPolicy` (`freedom_ls/accounts/models.py:137-158`), which already holds boolean/JSON policy flags of the same shape. |
| 11 | `referral-link-tracker` | **implies-a-cheap-decision** | See §1 below. Not a schema change to any existing table — a documentation/convention decision. |

## 1. `referral-link-tracker`'s deliberate non-use of `SiteAwareModel`

The idea is explicit and has clearly already reasoned this through, not stumbled into it:
`referral-link-tracker/idea.md:29-33` states the app "must **not** import from FLS-specific apps
... or subclass FLS base classes (`SiteAwareModel`)," and `idea.md:102-106` repeats it for the model
layer ("The app does **not** subclass FLS's `SiteAwareModel`; FLS layers its own site-aware
querying/filtering on top of the app's models rather than the app depending on FLS's base class").
The idea even flags that its own research doc's model sketch needs correcting for this
(`idea.md:196-199`): `research_data_model.md`'s sketch subclasses `SiteAwareModel` directly
(`research_data_model.md:170, 194, 221-224`), and the idea author has already caught and overridden
that in favour of an optional `django.contrib.sites` FK, precisely to keep the app dependency-free
and extractable.

**What this does and doesn't imply for the pre-deploy cleanup:**

- It does not need a `site` field that's missing — the plain, optional `contrib.sites` FK it plans to
  use is a completely ordinary Django pattern and needs no FLS schema decision.
- It does set a precedent worth recording *now*, before it's built: `docs/app_structure.md` currently
  shows every domain app in the codebase with a `--> site_aware_models` edge — `accounts`, `content_engine`,
  `course_applications`, `course_interest`, `educator_interface`, `organisations`, `qa_helpers`, `reports`,
  `role_based_permissions`, `student_interface`, `student_management`, `student_progress`
  (`docs/app_structure.md:40, 46, 54, 66, 73, 80, 86, 91, 99, 107`, etc.) — `referral-link-tracker`
  will be the **first app in the graph with none**. There is currently no written convention anywhere in
  `docs/` describing when `SiteAwareModel` should or shouldn't be used — a repo-wide grep of `docs/` for
  `SiteAwareModel` returns nothing — so this precedent is being set by one idea document's reasoning,
  not by policy.
- The cheap decision to take now, before this is built: **explicitly document that "self-contained,
  extractable, reusable Django apps intended to be lifted out of FLS" are a deliberate, named exception
  to the SiteAwareModel convention**, with `referral-link-tracker` as the worked example. This is cheap
  precisely because it's a documentation change, not a code change — but it is worth doing *before* the
  app is built, not after, because the alternative failure mode is a future contributor or a
  `/plan_structure_review` pass treating the missing `site_aware_models` edge as an oversight and
  "fixing" it by subclassing `SiteAwareModel`, which would silently reintroduce the FLS coupling the
  idea spent a whole section arguing against.
- This is not evidence that `SiteAwareModel` is positioned wrong for anything else in the roadmap — every
  other item assessed here (certificates, MFA, comms, xAPI, reports) is ordinary FLS domain code with no
  extractability requirement, and should keep using `SiteAwareModel` exactly as everything else does.
  The exception is narrow and should stay narrow.

## Convergent demand

**The one real signal: a run/registration id, wanted independently by two features.**
`better_course_progress_tracking/idea.md:140-141` states this directly, in its own words: *"Which run
do the webhooks mean? `course.registered` and `course.completed` carry no run or registration id
today. Both this work and the queued `xapi_implementation` will independently want one."* This is
corroborated from the xAPI side by the standard itself: xAPI's own `Context` object has a standing
`registration` (UUID) field for exactly "which instance of this person doing this activity does this
statement belong to" (`xapi_implementation/research_xapi_standard.md:13`) — the xAPI research already
landed on the same concept the progress-tracking idea named, independently, without either document
citing the other.

Why this one is worth calling out and the others below aren't: two features arriving at the same need
from unrelated directions (a UX/data-integrity problem in one case, a 20-year-old external standard in
the other) is a much stronger signal than either wanting it alone. But note what it does *not* imply
for *this* pre-deploy cleanup: it doesn't force any change today. `better_course_progress_tracking`'s
new `CourseRun` model (`idea.md:41-54`) is the answer, and it lands from a spec that's already
in-flight and assumed to land per this task's fixed decisions. Nothing needs deciding in *this* unit's
scope beyond the one thing worth writing down for whoever eventually specs `xapi_implementation`: point
its event table's registration/attempt concept at `CourseRun`'s id rather than re-deriving or
reinventing its own attempt identity, since that identity will already exist by the time xAPI is built.

**A convergence that both sides already noticed and deliberately did not resolve — the "pool of
questions" concept.** `compliance-form-randomization/idea.md:77-78` says so itself: *"Note the overlap:
both touch a 'pool of questions' concept; the remediation spec will define its own primitives and may
later converge — that convergence is not a goal here."* This is included specifically as a contrast to
the run/registration id case above: it is the same *shape* of signal (two roadmap items wanting a
related concept) but the idea authors have already looked at it and decided, correctly, not to force a
shared primitive before either side is built. Nothing to add here beyond confirming that call still
holds — it does, and it is a good model for how "convergent demand" should usually be handled: noted,
not pre-built.

## Risks and gotchas

1. **Inventing schema for a feature nobody has specced.** The explicit risk this task was warned to
   guard against. It did not materialise here: every item that could have tempted a pre-built model
   (certificates' verify token, MFA's device table, comms' audience abstraction) turns out to need
   nothing from today's schema because it's either purely additive against existing tables or, in
   `certificates`' case, fully covered by a sibling spec that's already in flight. The one item that
   does get a recommendation in this report (`referral-link-tracker`, §1) gets a *documentation*
   decision, not a model — which is the right size of decision for an idea that hasn't been specced yet.
2. **`report-upgrades` is not spec-ready and its own header says so.** `report-upgrades/idea.md:1-9`
   flags that `basic_reports` removed the `REPORTS_AT_RISK_RULES_MODULE` settings hook the idea was
   written against, and several sections need reworking before this idea can be trusted as a spec input.
   Treat the "implies-nothing" verdict above as a statement about the *shape* of the change (new models,
   new nullable field), which survives that rework — not as a signal that the idea document is otherwise
   current.
3. **The "no organisation membership" non-goal was already reversed once.** The shipped Organisation cut
   stated "No organisation membership object" as a deliberate non-goal; `learners-associated-with-organisations`
   (`idea.md:14-20`) explicitly reverses it, with a paragraph recorded specifically so nobody re-litigates
   the original call without reading why. This is a useful precedent for this cleanup's own scope
   discipline: a documented non-goal is not permanent, but reversing one needs the same "written down,
   with reasoning" treatment that spec did — an undocumented reversal is how scope creep actually happens.
4. **Two structural facts assumed by the task turned out to already be true, not merely queued.** Both
   `basic_reports` and the Organisation cut have already merged into `main` (confirmed by reading
   `freedom_ls/reports/models.py` and `freedom_ls/organisations/models.py` directly, and by
   `Cohort.organisation`/`UserCourseRegistration.organisation` already being mandatory FKs in
   `freedom_ls/student_management/models.py:16-73`). This report treated `report-upgrades` as resting on
   already-shipped ground rather than on two more in-flight specs — worth this cleanup's author
   double-checking which of the "fixed decisions" sibling specs are still in-flight vs. already landed
   before finalising the refined idea, since the answer changes how much residual risk each queued item
   actually carries.

status: ok
