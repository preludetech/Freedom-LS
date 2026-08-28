# Research: what the rest of the roadmap already demands of the progress model

Reading-only pass over `spec_dd/`. No web research. Baked-in design treated as fact throughout: a
`CourseProgress` row becomes one `Learner`'s pass through one `Course`; it gains `is_active` with
`UNIQUE (learner, course) WHERE is_active`; it carries nullable `learner_registration` /
`cohort_registration` FKs (exactly one set, both `SET_NULL`) and its life follows that registration;
`TopicProgress`/`FormProgress` re-scope from the bare `Topic`/`Form` to the `ContentCollectionItem`
that places the content in a course.

Note on provenance: the feature's own `idea.md` (`spec_dd/2. in progress/better_course_progress_tracking/idea.md`)
still describes an earlier design — a `CourseRun` model keyed on `(user, course, organisation)` with
`is_current` and **no** registration FK, explicitly rejecting one (`idea.md:82-95`, "Rejected: also
hanging `user_registration` / `cohort_registration` FKs off the run"). The design this task treats as
fact — `Learner`-keyed, `is_active`, registration FKs present — is a later revision that lived in the
now-deleted `1. spec.md` (see the last section below). Findings here are written against the current,
fact-treated design, and flag the few places the idea file's older shape leaks through.

---

## 1. `learner-management-actions`

`spec_dd/1. next/learner-management-actions/idea.md` is sequenced explicitly after this feature and
depends on its progress-record shape to specify the move-a-learner action:

> "**Sequencing: this comes after `better_course_progress_tracking` lands.** The cohort-move action
> below is specified in terms of that work's progress-record model, and cannot be written against
> `main`." (`idea.md:6-7`)

It names the destructive baseline this feature currently accepts:

> "Under `better_course_progress_tracking` that sequence is destructive: the deletion fires the
> retirement receiver (spec §5.6), and the learner's next visit resolves a different registration and
> starts a new progress record from zero (spec §5.3). A learner 60% through a course loses that 60%
> because an educator moved them between cohorts. The current spec records this as an accepted
> consequence (§3.1, §14 'no merge or transfer') — this feature is where the mitigation lands."
> (`idea.md:26-30`)

It weighs three designs, faithfully reproduced:

1. **A transfer step inside the move action** that re-points the progress record's
   `cohort_registration`. "Smallest change; leaves the destructive path open to anyone who does the
   move the manual way." (`idea.md:48-49`) — **Implies for identity/retirement:** the identity key
   stays as designed (`learner`, `course`); retirement stays a receiver reacting to registration
   deactivation, and this option just adds one more caller that re-points `cohort_registration` before
   the deactivation-then-reactivation sequence would otherwise fire it. Cheapest, narrowest, and the
   only one of the three that changes nothing about how retirement is triggered elsewhere.
2. **Deferring the retirement check to `transaction.on_commit`**, guarded by "does the learner still
   hold any active registration for this `(course, organisation)`?" (`idea.md:50-52`) — **Implies:**
   retirement stops being "fires the instant this registration deactivates" and becomes "fires only if,
   by end of transaction, nothing else grants access." This changes the retirement rule from a
   per-registration receiver into a per-transaction reconciliation, which is a materially different
   shape from a `SET_NULL` FK reacting to a single deactivation — it has to reason about *all* of a
   learner's registrations for that course, not just the one that changed.
3. **Treating the registration FK as current-registration bookkeeping rather than identity**, so
   resolution re-points and resumes instead of retiring (`idea.md:53-55`) — **Implies:** this is the
   most invasive option against the baked-in design. It would mean `learner_registration`/
   `cohort_registration` stop being "the grant that created this pass, frozen at creation" and become
   "whichever grant currently backs this row" — mutable pointers, not provenance. The idea's own words:
   "Simplifies the current spec's three-row resolution table to two rows, at the cost of needing an
   explicit trigger for retakes" (`idea.md:54-55`). This is the one option that would require this
   feature's spec to *not* treat the registration FK as append-only provenance, which is a direct
   conflict with the "its life follows that registration" framing in the baked-in design — worth
   flagging now rather than after `learner-management-actions` is specced against whichever choice
   this feature ships.

It also draws the scope boundary this feature should mirror:

> "**Cross-organisation moves are out of scope.** Organisation is part of the progress record's
> identity key, so a learner moving between organisations *should* start a fresh progress record —
> that is `better_course_progress_tracking` §2.1 working as designed, not a bug to fix here."
> (`idea.md:57-59`)

Note: `Organisation` is not literally in `CourseProgress`'s key under the baked-in design — `Learner`
carries the organisation, one row per `(user, organisation)` — so "organisation is part of the identity
key" is true transitively (through `learner`), not as a separate column. The sibling idea's phrasing
predates knowing this and should be read that way rather than literally once reconciled.

**What it requires of the progress model:** a decidable, single answer to "what happens to a learner's
`CourseProgress` when their granting registration is swapped for another one in the same organisation
within one transaction" — the retirement rule as currently scoped (react to *this* registration's
deactivation) makes the naive same-organisation cohort move destructive by default, and this feature's
spec should say explicitly which of the three mitigation shapes it leaves room for, rather than
resolving it silently as "whatever the receiver already does."

---

## 2. `content_snapshots`

`spec_dd/2. in progress/content_snapshots/0. idea.md` is deliberately consumer-agnostic:

> "The system stands alone — it has no dependency on, or knowledge of, any particular consumer."
> (`0. idea.md:3`)
>
> "Consumers of this API are out of scope for this spec. The app is built to be useful, not to satisfy
> any particular caller." (`0. idea.md:57`)

Its public API is three functions:

> "`take_snapshot(content_obj) -> Snapshot`... `get_latest_snapshot(content_obj) -> Snapshot | None`...
> `get_snapshot(snapshot_id) -> Snapshot`" (`0. idea.md:53-55`)

Its hard dependency rule, which fixes the FK direction any consumer must respect:

> "The app must not depend on any other freedom_ls app beyond `content_engine` (and
> `accounts`/`site_aware_models` where the base classes require it)." (`0. idea.md:23`)
>
> Restated as a success criterion: "The `content_snapshots` app has no imports from apps other than
> `content_engine`, `accounts`, and `site_aware_models`." (`0. idea.md:75`)

**FK direction, made explicit:** `content_snapshots` cannot import from `learner_progress`, so a
consumer relationship can only be `learner_progress → content_snapshots` (a `snapshot_id` stored on
`FormProgress`/`TopicProgress`, or on the run), never the reverse. `learner_progress` already depends
on `content_engine` today, so adding a `content_snapshots` edge from `learner_progress` costs nothing
structurally — it does not create a cycle and does not touch `content_snapshots`'s own graph.

Is a progress record pinning a snapshot id a natural first consumer? Yes, and the `content_snapshots`
idea was written with this exact question already in its sights, quoting this feature's own idea file
back at itself:

> "Editing content and calling `take_snapshot` again produces a new snapshot row; the prior snapshot is
> unaffected and still resolvable by id." (`0. idea.md:73`)

This feature's idea file carries the open question directly:

> "**Does `FormProgress` need a content snapshot?** Content can change between a learner's first and
> second run. Pairing `FormProgress` with the in-progress `content_snapshots` work is a natural fit but
> is not in scope here." (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:232-234`)

This idea now makes the question **answerable**, in two different senses that must not be conflated:

- **Per-question-answer text** (what exact words was one `QuestionAnswer` answering) is already
  answered by a *different*, narrower research pass: `final_pre_deploy_db_structure_cleanup`'s
  deletion-semantics research recommended a `question_text`/`selected_option_texts` snapshot directly
  on `QuestionAnswer` (see §7 below) and that research explicitly updates this feature's open question:
  "This recommendation should be reflected back into `content_snapshots`'s own open question list
  (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:143-144`, 'Does `FormProgress` need
  a content snapshot?') — the answer for the per-question-answer text is 'no, `QuestionAnswer` already
  carries its own,' narrowing what `content_snapshots` needs to solve for `FormProgress` to the
  structural question."
  (`spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md:165-169`)
  **However**, that research's own idea file overturned the recommendation: "**No snapshot column on
  `QuestionAnswer`.**... on review the urgency argument does not hold... It is recorded here as a note
  for those specs, not built." (`final_pre_deploy_db_structure_cleanup/idea.md:110-116`) So the
  per-answer text snapshot is **not built anywhere yet** — the open question in this feature's idea
  file is not actually closed by anything shipped or committed, only by a considered-and-declined
  research recommendation.
- **The structural question** ("what did the whole `Form` look like on the day this pass attempted
  it") is squarely `content_snapshots`'s job once it has a consumer, and a `CourseProgress`/
  `FormProgress` row is the obvious first one: a re-registered learner starting a fresh pass through
  edited content is exactly the "content changed between runs" scenario `content_snapshots` exists for.

**What it requires of the progress model:** if this feature wants a `FormProgress`/`TopicProgress` row
to reference "what the content looked like when this pass touched it," the only legal shape is a
nullable `snapshot_id` (or FK once `content_snapshots` ships models) stored on the progress side,
never the reverse — and this feature should either take that dependency now (naming
`content_snapshots` as its first real consumer) or explicitly re-defer it, rather than leave the open
question sitting unanswered a second time.

---

## 3. `certificates`

The idea file is three lines: "Implement certificates. This will make the LMS more marketable...
verifiable, tamper-evident certificates with a public verify URL." (`spec_dd/1. next/certificates/idea.md:1-3`)

The substance is in this feature's own idea file and in `final_pre_deploy_db_structure_cleanup`'s
roadmap-pressure research, both already anticipating what a tamper-evident certificate needs from a
progress record:

> "`certificates` in particular must bind to a frozen completion record rather than a live `(user,
> course)` query — Moodle's `mod_customcert` regenerates from a mutable completion date, so
> certificates silently change after a recompletion reset, which is the opposite of tamper-evident. A
> certificate now also has to name the organisation the learner earned it through, which is another
> thing it can only get from a run."
> (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:285-288`)

And, independently, from the roadmap-pressure research:

> "`certificates` ... Needs a new `Certificate` model (hash/token, public verify URL) FK'd to a frozen
> completion record. `better_course_progress_tracking/idea.md:167-171` already names the exact
> requirement ('must bind to a frozen completion record rather than a live `(user, course)` query') and
> the sibling spec's `CourseRun` (a new, per-pass row, `idea.md:41-54`) *is* that frozen record.
> `certificates` needs zero of its own structural decisions once that lands — just a new, additive
> table pointing at it."
> (`spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:32`)

Translated into the baked-in design's nouns: a certificate needs (a) a **stable identifier for which
pass** — the `CourseProgress` row's own primary key, which is now per-pass rather than per-`(user,
course)` and therefore already distinguishes "this run" from "a later retake"; (b) an
**organisation** — `Learner.organisation`, reachable from `CourseProgress.learner.organisation`; and
(c) a **frozen completion date** — `CourseProgress.completed_time`, which must not be mutated by a
later reset once a certificate has been issued against it (a live FK to a mutable row is only
tamper-evident if the row it points at is itself immutable at the field the certificate cites).

**What it requires of the progress model:** `CourseProgress` must be the durable, per-pass anchor a
`Certificate` FK can point at with `on_delete=PROTECT` (or an equivalent no-silent-loss policy), and
`completed_time` must not be rewritten once set by any later recalculation — a certificate's whole
tamper-evidence story depends on that field being append-only in practice, not just in principle.

---

## 4. `report-upgrades`

`spec_dd/1. next/report-upgrades/idea.md` proposes snapshotting a *different* kind of configuration
onto a *different* kind of permanent record, but it is the identical shape of problem as pinning a
pass to a content snapshot:

> "**Snapshot the resolved configuration onto the report.** Configuration is editable, reports are
> permanent. Store the resolved config (a JSON blob) on `GeneratedReport` at generation time, so anyone
> can answer 'why was this student flagged?' after the thresholds have been changed. Cheap to add, and
> it is the difference between an auditable record and a PDF nobody can account for."
> (`report-upgrades/idea.md:290-295`)

Both cases are "a mutable configuration/content object changes after a permanent record was produced
from it; the permanent record must carry a frozen copy or reference of what it actually used, not a
live pointer that silently reinterprets itself." `report-upgrades` solves it with an inline JSON
snapshot on the consuming record; `content_snapshots` solves the content case with a dedicated,
append-only snapshot table with its own id. This feature's progress record sits between both patterns:
it is itself the kind of "permanent record" report-upgrades and certificates want to point at
(§3 above), and it is a candidate consumer of the content-snapshot pattern for its own content
references (§2 above).

Also directly relevant: the sequencing warning about the report app resting on already-shipped ground
now applies to this feature the same way:

> "Note separately: this idea's own header (`report-upgrades/idea.md:1-9`) says it 'needs revision
> before it is specced' because `basic_reports` removed the settings-module rules hook it was written
> against — it is not spec-ready, but that is an idea-freshness problem, not a schema-pressure one."
> (`final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:39`)

**What it requires of the progress model:** nothing structural today — `report-upgrades` upgrades
`GeneratedReport`/`Organisation`, not `CourseProgress`. But it establishes the house pattern ("snapshot
the resolved thing onto the permanent record, once, at the moment of permanence") that this feature
should reuse rather than reinvent if/when it decides how a pass records what content it used.

---

## 5. `xapi_implementation`

`spec_dd/1. next/xapi_implementation/0. idea.md` builds an append-only event stream that is a parallel
source of truth to progress rows, using xAPI's actor/verb/object/result shape "as a design guide, not
strict compliance" (`0. idea.md:5`). It defines ~10 verbs including `registered`, `progressed`,
`completed` (`0. idea.md:38, 65-66`) and explicitly wants to support "seeing where people typically
struggle and how long people take to do different things" (`0. idea.md:83`) — which needs a stable way
to group events into "this learner's attempt/pass," not just "this learner, this content, ever."

The convergent-demand signal, surfaced independently in the roadmap-pressure research and corroborated
from the xAPI standard itself:

> "**The one real signal: a run/registration id, wanted independently by two features.**
> `better_course_progress_tracking/idea.md:140-141` states this directly, in its own words: 'Which run
> do the webhooks mean? `course.registered` and `course.completed` carry no run or registration id
> today. Both this work and the queued `xapi_implementation` will independently want one.' This is
> corroborated from the xAPI side by the standard itself: xAPI's own `Context` object has a standing
> `registration` (UUID) field for exactly 'which instance of this person doing this activity does this
> statement belong to' (`xapi_implementation/research_xapi_standard.md:13`) — the xAPI research already
> landed on the same concept the progress-tracking idea named, independently, without either document
> citing the other."
> (`final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:85-93`)

And the concrete recommendation for whoever specs xAPI:

> "point its event table's registration/attempt concept at `CourseRun`'s id rather than re-deriving or
> reinventing its own attempt identity, since that identity will already exist by the time xAPI is
> built." (`final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:100-103`)

Translated to the baked-in design's nouns: xAPI's `Context.registration` should point at
`CourseProgress.id` — the per-pass row's own primary key is already "which instance of this person
doing this course" in exactly the sense xAPI's field wants. This feature does not need to build
anything for xAPI beyond ensuring `CourseProgress.id` is a stable, non-reused identifier for a pass
(which the `UNIQUE (learner, course) WHERE is_active` design already gives it — a retired row keeps its
id even after `is_active` flips off).

Should a verb be reserved for pass start / retirement? The idea file's verb list does not currently
include one (`0. idea.md:38, 60-66` list `viewed`/`experienced`, `completed`, `attempted`, `answered`,
`registered`, `progressed`, `submitted`, `interacted` — no explicit "pass started" or "pass retired").
Once this feature makes a pass a first-class, creatable/retirable object, `xapi_implementation`'s
eventual verb catalogue has a real reason to add one (distinct from `registered`, which is about access
grant, not pass lifecycle) — worth a forward note in that idea's own document, not a decision this
feature has to make.

**What it requires of the progress model:** a stable, never-reused per-pass identifier suitable as an
xAPI `registration` value — `CourseProgress.id` already satisfies this under the baked-in design, with
no additional field needed, provided retirement never deletes or recreates the row (soft retirement via
`is_active=False`, not a hard delete-and-recreate).

---

## 6. Randomised question pools — `compliance-form-randomization` and question-pools-and-remediation

`spec_dd/2. in progress/compliance-form-randomization/idea.md` and
`spec_dd/0. drafts/xx. sacaa question-pools-and-remediation/idea.md` both add a third axis to what a
`FormProgress` attempt records: **pass × pool × attempt**, not just pass × attempt.

The per-attempt record requirement, stated directly:

> "Randomization must be **stable within an attempt** (reloads, back-navigation and resume show the
> same order/subset) and **reproducible for review**. Seed the shuffle once per attempt and persist the
> **realized order/selection** (the exact pages, questions, and option orders the learner saw). Scoring,
> educator review, and compliance audit read from this record, not from a re-derived shuffle."
> (`compliance-form-randomization/idea.md:47-53`)

And the design-directions section names exactly where this lands:

> "**Per-attempt record** — store an explicit `realized_order` (and/or seed) on `FormProgress`;
> `QuestionAnswer` currently records no 'served set', so this is new."
> (`compliance-form-randomization/idea.md:94`)

The sibling SACAA idea adds retry-within-pool semantics that also key off the same per-attempt
identity:

> "**Randomisation seeding.** Probably seeded by `(FormProgress, pool)` so reloads are stable. Decide
> whether a retry re-seeds or draws 'next unseen variant'."
> (`0. drafts/xx. sacaa question-pools-and-remediation/idea.md:65`)
>
> "**Per-attempt records.** Currently `QuestionAnswer` has no attempt counter. Mastery gating and
> educator surfacing both need attempt-level data. Model change required."
> (same file, `:64`)

Both new fields (`realized_order`/seed, an attempt counter) are additive to `FormProgress` as it is
already scoped by this feature (per-`ContentCollectionItem`, many rows per `(run, placement)`, one per
attempt). Nothing here asks `FormProgress`'s *keying* to change — it asks for **more state per attempt
row**, which this feature's re-scoping to `ContentCollectionItem` neither helps nor hinders. The
`final_pre_deploy_db_structure_cleanup` roadmap-pressure research already confirms this:

> "The per-attempt realized-order record is a new JSON-shaped field on `FormProgress`, which already
> carries exactly this kind of thing (`scores`, a `JSONField`, `freedom_ls/student_progress/models.py:91-93`)
> — direct precedent for adding another one."
> (`final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:37`)

**What it requires of the progress model:** nothing structural — `FormProgress`'s existing per-attempt
row shape (one row per attempt, `scores` as a `JSONField` precedent) already accommodates a
`realized_order`/seed field and an attempt counter as pure additions. The one thing worth confirming in
this feature's own spec is that "one attempt = one `FormProgress` row, scoped to one `CourseProgress`
pass" remains true once pools exist — a pool-driven retry must still be a new `FormProgress` row under
the *same* `CourseProgress`, not a new pass.

---

## 7. `final_pre_deploy_db_structure_cleanup` — does it collide with this feature's delete-and-add-non-nullable plan?

**No collision — the two are sequenced to cooperate, and the cleanup idea says so explicitly.**

The cleanup's own idea file states the sequencing in so many words:

> "**Sequencing:** the reset must happen **after** `learner-terminology-rename`,
> `learners-associated-with-organisations`, and `better_course_progress_tracking` all land, because
> every one of them changes models in the apps this idea would otherwise regenerate migrations for
> twice. Doing the reset first would mean regenerating `0001_initial` files that are immediately stale
> the moment the next sibling spec merges — wasted work..."
> (`spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/research_migration_reset_strategy.md:234-238`)

And the umbrella idea file's own sequencing section repeats it, plus a direct instruction not to touch
this feature's models mid-flight:

> "`learners-associated-with-organisations` (already depends on the rename landing first) and
> `better_course_progress_tracking`. The latter restructures `CourseProgress` → `CourseRun` and
> re-keys `TopicProgress`/`FormProgress` to placements — **do not index or add timestamps to models it
> is mid-redesign on**."
> (`final_pre_deploy_db_structure_cleanup/idea.md:162-165`)

Why there is no collision, concretely: this feature's plan (delete all existing `CourseProgress`/
`TopicProgress`/`FormProgress` rows, then add the new non-nullable columns with no backfill) is only
safe *because* there is no production data yet — exactly the same precondition the migration-reset
idea is built on:

> "**FLS is never deployed standalone.**... There is no evidence anywhere in `spec_dd/` that
> `manage.py migrate` has ever been run against a database any project intends to keep."
> (`final_pre_deploy_db_structure_cleanup/research_migration_reset_strategy.md:93-111`)

Both this feature's own migration and the later project-wide reset are exploiting the same open
window. The reset runs **after** this feature lands, which means: this feature ships its own ordinary
forward migration now (whatever shape it needs — deleting rows, adding non-nullable columns, no
backfill), and the later, separate, one-time reset simply regenerates a fresh `0001_initial` per app
that captures the **final** shape, including whatever this feature's migration produced. The
awkward-looking intermediate migration this feature writes (delete-then-add-non-nullable) does not need
to survive forever — it gets folded away entirely when the reset deletes and regenerates
`learner_progress`'s migration history. The recommendation is explicit that this reset is a **declared,
one-time exception** to the "never edit existing migration files" rule (`CLAUDE.md`), not a precedent:

> "this is a declared, one-time exception, and it should be recorded as one... Treat the reset as a
> single, explicitly-scoped, once-only action taken by this idea — not a precedent that migration files
> are generally editable."
> (`final_pre_deploy_db_structure_cleanup/research_migration_reset_strategy.md:224-232`)

One genuine dependency running the other way, worth carrying into this feature's own spec: the
deletion-semantics research (part of the same cleanup effort) recommends `PROTECT` on
`FormProgress.form`, `TopicProgress.topic` and `CourseProgress.course`
(`final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md:53-55`) — a change to the
*content-side* `on_delete` policy, not the placement-side one this feature already owns. The same
research is careful to keep the two apart:

> "**Do not conflate this unit's `PROTECT` recommendation with `better_course_progress_tracking`'s
> `SET_NULL` decision for placements** — they are different deletion axes... `better_course_progress_tracking`
> decides what happens when a `ContentCollectionItem` *placement* is removed... `SET_NULL`... This unit
> decides what happens when the `Form`/`Topic`/`Course` row *itself* is hard-deleted — `PROTECT`. Both
> are correct; they answer different questions and must not be merged into one decision in the plan
> phase."
> (`final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md:256-262`)

**What it requires of the progress model:** nothing this feature needs to change to accommodate the
cleanup — the cleanup accommodates *it*, by running last and by explicitly telling its own author not
to touch `learner_progress`/`content_engine` models this feature is mid-redesign on. The one thing this
feature's spec should carry forward rather than rediscover: `FormProgress.form`, `TopicProgress.topic`
and `CourseProgress.course` should end up `PROTECT` (a hard-deleted `Form`/`Topic`/`Course` must not
silently wipe every learner's history for it), and that is a separate decision axis from this feature's
own `SET_NULL`-on-placement-removal rule — both belong in the final schema, neither should be merged
into the other's reasoning.

---

## 8. `periodic_reports`

`spec_dd/0. drafts/00. periodic_reports/0. idea.md` is a draft for scheduled report generation. It is
built directly on `basic_reports`'s existing model and inherits that app's assumption of one live
`CourseProgress` percentage per `(user, course)` per point in time. Under a multi-pass model, a weekly
scheduled report comparing "this week's cohort snapshot" against "last week's" is silently comparing
across whatever the **current** run happens to be for each learner at each point in time — a learner
who starts a second pass mid-period changes what "this cohort's completion rate" meant for the *earlier*
report retroactively, if the report ever recomputes live rather than reading a frozen snapshot. This
draft does not yet discuss multi-pass data at all; it inherits `basic_reports`'s single-run assumptions
wholesale and should be flagged for review once this feature ships, rather than discovered when someone
schedules a report against a course with retakes in flight.

**What it requires of the progress model:** nothing today (still a draft, not yet dependent on
progress-model internals) — but any spec written for it after this feature ships must decide whether a
period's report reads the learner's *current* pass only (matching `basic_reports`'s existing
first-attempt/latest-attempt conventions, §13 below) or needs to reason about passes that started or
retired mid-period. This feature's spec should name `is_active`/`completed_time` as the fields a
periodic report would key its period boundaries against, so that decision has something concrete to
reason from.

---

## 9. Attempt lifecycle — `compliance-exam-remediation` and `exam-timeouts`

`spec_dd/1. next/compliance-exam-remediation/idea.md` is a two-line stub: "a short explanation of
answers (why they are right/wrong)... reference relevant content" (`idea.md:6-7`) — purely additive
fields on `FormQuestion`/`QuestionOption`, per the roadmap-pressure research's own verdict:

> "Optional per-answer explanation/reference text is a new nullable field on `FormQuestion`/
> `QuestionOption`... No key or uniqueness changes."
> (`final_pre_deploy_db_structure_cleanup/research_roadmap_pressure.md:38`)

`spec_dd/0. drafts/00. exam-timeouts/idea.md` is more substantial and touches `FormProgress` directly:

> "Extend the existing `FormProgress` record in `student_progress` with: `started_at`...
> `time_limit_seconds`... `deadline_at`... `auto_submitted_at`... A state field or equivalent,
> distinguishing not-started / in-progress / submitted."
> (`exam-timeouts/idea.md:27-33`)

None of these fields have any dependency on the `(user, course)` → `(learner, course)` re-key, or on
the `Topic`/`Form` → `ContentCollectionItem` re-scope this feature performs — they are new columns on
the existing `FormProgress` row, additive regardless of what identity that row hangs off. The one
interaction worth naming: exam-timeouts' `deadline_at` is "server-authoritative" and pinned at
attempt-start (`idea.md:13, 30-31`) — it is **per-attempt**, which under this feature's design means
per-`FormProgress` row, scoped to whichever `CourseProgress` pass the attempt belongs to. Nothing about
multiple passes changes that; a learner on their second pass through a course gets a fresh
`FormProgress` row (per §6 above) and the timer logic applies identically.

**What it requires of the progress model:** nothing — both features add fields to `FormProgress` that
are orthogonal to this feature's re-keying and re-scoping. Confirm in this feature's spec that
`FormProgress`'s per-attempt-row shape survives the re-scope to `ContentCollectionItem` intact (it must,
since these two ideas assume it), and that a fresh `CourseProgress` pass produces fresh, correctly-timed
`FormProgress` rows rather than resuming stale attempt state from a prior pass.

---

## 10. `educator-interface-quick-view-panel`

`spec_dd/1. next/educator-interface-quick-view-panel/idea.md` renders per-cell detail for a topic- or
form-progress cell in the cohort progress table, listing "attempt number, started/submitted timestamps,
score... pass/fail status" per `FormProgress` row and "when the student started and finished the
topic" for `TopicProgress` (`idea.md:54-58`, `48-51`). Once a learner can have more than one
`CourseProgress` pass through a course, **a cell in that table stops meaning "this learner's
progress on this item, full stop"** and starts meaning "this learner's progress on this item, *for
whichever pass the table is currently showing*." The idea's own scope statement already assumes the
single-pass world implicitly — it says nothing about which pass's attempts populate "one row per
attempt," and under a multi-pass model that ambiguity becomes a real question: does the panel show every
attempt across every pass, or only the current pass's attempts?

**What it requires of the progress model:** the panel needs an explicit, decidable answer to "which
`CourseProgress` pass does this progress-table cell belong to" before it can be specced honestly — the
educator interface's cohort progress table (which this panel is a drill-down from) must already resolve
that question for the cell itself to make sense, and the panel inherits whatever answer the table gives.
This feature's spec should state which `CourseProgress` row the educator-facing progress table reads
(almost certainly "the current, `is_active=True` one" — mirroring the resolution rule this feature
already applies elsewhere), since that answer is what the quick-view panel will build on.

---

## 11. `critical_security_fixes` and `user-data-retention-idea.md` — brief notes

`spec_dd/1. next/critical_security_fixes/idea.md` documents that the educator interface's cohort
detail page and progress matrix are readable by any authenticated user with no permission check
(`idea.md:14-16`, `29-36`). This is an access-control defect in the *view* layer, not a progress-model
shape question — it does not touch how `CourseProgress`/`TopicProgress`/`FormProgress` are keyed. No
requirement on this feature beyond the general one every organisation-scoped surface already carries:
once progress is `Learner`-keyed (and therefore organisation-scoped through `Learner.organisation`),
any query serving the educator interface must filter through that organisation the same way the rest of
the interface already does, so this defect's eventual fix and this feature's re-key do not silently
diverge on which organisation's data a given view is allowed to show.

`spec_dd/1. next/user-data-retention-idea.md` asks, unresolved, "how does deletion interact with
cohorts, certificates, and educator/admin records that may have legal weight?" (`idea.md:19`) and
explicitly hands the `on_delete` policy for user-owned data to a future spec. The deletion-semantics
research already flags the direct interaction with this feature:

> "`FormProgress.user`, `TopicProgress.user`, `CourseProgress.user`... Keep — **hand off to retention
> spec**... once `PROTECT` is added on the *content* side (§1a), a learner's evidence survives content
> edits, but still dies immediately if the *user* is deleted, with no canonical `delete_user()` flow
> deciding whether that's correct."
> (`final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md:80`)

Under this feature's re-key, that FK moves from `user` to `learner` (`CourseProgress.learner`,
reachable to the person via `learner.user`) — the retention question is unchanged in substance
(does progress survive a user's deletion, or a `Learner` row's deactivation-versus-hard-delete), just
relocated one hop. Nothing for this feature to decide; worth a one-line pointer in its own spec so the
eventual retention spec finds the right FK to reason about.

**What it requires of the progress model:** nothing to build now for either — both are noted so this
feature's spec does not silently assume either problem is solved.

---

## 12. Shipped: `learners-associated-with-organisations`

This is the sibling this feature's `Learner`-keying directly inherits from.
`spec_dd/3. done/2026-08-23_17:20_learners-associated-with-organisations/1. spec.md` shipped the
`Learner` model this feature keys `CourseProgress` on:

> "Introduce an explicit **`Learner`** model: a row recording that an `accounts.User` is associated
> with an `Organisation`. A user may be a Learner of several organisations on the same Site."
> (`1. spec.md:10-11`)

Two decisions from that spec bind this feature directly:

**`deadline_utils.py` stays user-scoped, deliberately, and this feature should follow the same
reasoning wherever a progress lookup is keyed by "the person," not "this specific enrolment path":**

> "**`learner_management/deadline_utils.py` does not gain a `learner__is_active` condition**... Every
> one of these is keyed on a **user**, not on a learner, and must stay that way: a deadline belongs to a
> person studying a course, and a person holding two `Learner` rows for the same course should see the
> same deadline through either. `learner__user=user` preserves today's answer exactly; `learner=learner`
> would silently narrow it."
> (`1. spec.md:371-377`)

This is a direct precedent for a question this feature must also answer: when a learner holds two
`Learner` rows (two organisations) and therefore potentially two `CourseProgress` passes for the same
course, does a *deadline* (or any similarly person-scoped, not-organisation-scoped concept) resolve per
`user` or per `learner`? The Organisation spec's answer for deadlines is "per user, deliberately" — this
feature should state its own answer for anything analogous rather than let it fall out of whichever
query happens to get written first.

**Deactivating a `Learner` never cascades to progress, and this feature's registration-follows design
must honour the same principle:**

> "**Records never cascade; entitlement does.** Deactivating a `Learner` leaves every registration,
> membership and progress row exactly as it was — that is the Moodle failure being avoided... What
> removal changes is entitlement: §5.1's gate stops returning `True`, so the learner cannot open content
> held through that organisation. Data preserved, access suspended. Reactivation restores access with
> nothing to rebuild, precisely because nothing was destroyed."
> (`1. spec.md:883-887`)

This feature's own retirement rule (deactivate the registration → the progress record retires) must be
read as consistent with, not a violation of, this principle: **retirement here means `is_active=False`
on `CourseProgress`, never a cascade-delete** — the same "suspend, don't destroy" discipline the
`Learner` model already established one layer up. The spec should say so explicitly, since a reader
who only knows the `Learner` precedent could otherwise assume "life follows the registration" means the
progress row disappears.

Non-goals worth carrying forward as a direct precedent for scope discipline:

> "**No suspension surface outside the admin.** `Learner.is_active` is flipped in the Django admin
> only... **No per-organisation content scoping.** The gate asks whether *any* active `Learner` of this
> person backs an active enrolment for the course; it never asks which organisation the current request
> is 'for'."
> (`1. spec.md:1236-1243`)

**What it requires of the progress model:** `CourseProgress.learner` must be the FK (not a
denormalised `user`/`organisation` pair — `learner.organisation` is already the single source of that
fact, per `1. spec.md:287-289`'s reasoning about `LearnerCourseRegistration` dropping its own
`organisation` field for the identical reason); retirement must be implemented as `is_active=False`,
never a cascade or hard delete; and any progress-adjacent concept that is "about the person" rather
than "about this specific organisational relationship" (deadlines being the shipped example) should
default to resolving through `learner__user=user`, matching the precedent, unless this feature has a
specific reason to diverge.

---

## 13. Shipped: `basic_reports`

`spec_dd/3. done/2026-08-21_20:12_basic_reports/1. spec.md` and its `upgrade_notes.md` already encode
strong single-pass assumptions that this feature's multi-pass model directly disturbs.

**First-attempt-only rule for cohort-wide analysis:**

> "Per quiz: each question people got wrong, with the incorrect options chosen and how often, computed
> over **first attempts only**. Ranked worst-first by error rate." (`1. spec.md:332-333`)

**Latest-attempt rule for individual scores:**

> "That quiz score means the **latest** attempt." (`1. spec.md:283`)

**What "complete" means, keyed on a single `CourseProgress` row per learner per course:**

> "A student with no `CourseProgress` row has not started and is 0%, not omitted — `CourseProgress`
> rows only exist for explicitly registered users (`student_progress/models.py:568-572`)."
> (`1. spec.md:223-224`)

Both the "first attempt" and "latest attempt" rules are currently well-defined only because there is
exactly one `CourseProgress` per `(user, course)` and therefore exactly one ordered sequence of
`FormProgress` attempts to pick a "first" or "latest" from. Once a learner can have multiple
`CourseProgress` passes, "first attempt" (for cohort-wide item analysis) and "latest attempt" (for an
individual's score) both become ambiguous unless scoped explicitly to **one pass**: is "first attempt"
the first attempt of the learner's *current* pass, or literally the first attempt they ever made across
every pass they've had? A cohort quiz-confusion report that silently pools first attempts across every
pass a learner has ever had would conflate a first-timer's honest mistake with a retaker's first attempt
on their second run — precisely the kind of silent, undetectable analytical corruption this feature's
own idea file worries about for shared content (`idea.md:37-42`, item 3).

**Pass-required completion, shipped as a breaking change this feature must not regress:**

> "Course progress and course completion now ask whether the learner **passed**, not merely whether
> they submitted... `/courses/<slug>/finish` no longer stamps `completed_time` while any quiz in the
> course is unpassed."
> (`upgrade_notes.md:60-71`)

This is now baked into what `CourseProgress.completed_time` means, and this feature's per-pass
`CourseProgress` must preserve it per-pass: a learner's second pass completing does not retroactively
change whether their *first* pass's `completed_time` was ever stamped, and each pass independently
recomputes "has every quiz in this pass been passed" against **that pass's own** `FormProgress` rows,
never pooling attempts from a different pass.

Also directly relevant to the report's staleness concern generalised across passes:

> "**Completion percentage recomputed, not read from cache**... A wrong number on a screen gets
> refreshed; a wrong number in a filed PDF is permanent. The report derives completion from the
> progress rows themselves and says so in the definitions block."
> (`1. spec.md` — the summary-table row quoted at line 61)

**What it requires of the progress model:** `basic_reports`' existing "first attempt" (cohort analysis)
and "latest attempt" (individual score) conventions must be explicitly re-scoped to "within one
`CourseProgress` pass" once this feature ships, and the report's definitions block should be updated to
say so — otherwise a cohort with retakes in flight gets a quiz-confusions table that is silently wrong
in a way nobody currently has a test for, since (per the current spec) "test coverage for 'two runs,
same course, same learner' is entirely net-new" (`better_course_progress_tracking/idea.md:272-273`).

---

## 14. Shipped: `fls-integration-system-checks` — conventions any new check must follow

`spec_dd/3. done/2026-08-23_16:23_fls-integration-system-checks/1. spec.md` sets the house conventions
this feature must follow if its spec adds any `manage.py check` (for example, warning about the
`learner_registration`/`cohort_registration` "exactly one set" invariant, or about a stale content
reference once `content_snapshots` lands):

**App-label-namespaced IDs, one condition per ID:**

> "**App-label-namespaced IDs** (`freedom_ls_learner_interface.W001`). Do not copy `icons/checks.py`'s
> flat `freedom_ls.E00N` scheme (D3)." (`1. spec.md:294-295`)
>
> "**D3 — app-label-namespaced check IDs**, not the flat `freedom_ls.E00N` scheme. Extended here to a
> corollary: one ID means one condition, which is what motivates the E001/E002 split above."
> (`1. spec.md:308-310`)

**Registration behind `AppConfig.ready()`, at import time via `@register()`:**

> "Register at import time via `@register()`; `ready()` only imports the module." (`1. spec.md:296`)

**No DB access, checks must never raise:**

> "**No DB access** — read `settings` and `apps` only... **Checks must never raise.** Django does not
> catch check exceptions; a raised exception breaks `check`/`runserver`/`migrate` with a raw
> traceback." (`1. spec.md:299-304`)

**Retired IDs are never reused:**

> "`freedom_ls/reports/checks.py` sets the house rule for check-ID churn — it keeps a legend line
> reading 'W003 — Retired. Do not reuse the id: a project may still be silencing it.' Follow that
> convention when rewriting the `course_access` legend." (`1. spec.md:247-250`)

**The `app_configs` contract, for a scoped `manage.py check <app>` run:**

> "**Respect the `app_configs` contract:** when `app_configs is not None`, early-return `[]` unless the
> owning app's label is in it, so scoped `manage.py check <app>` runs stay correct." (`1. spec.md:300-302`)

**What it requires of the progress model:** nothing structural — this is a process constraint on *how*
this feature registers any system check it adds (for example, a check that a `CourseProgress` row
carries exactly one of `learner_registration`/`cohort_registration`, if such an invariant cannot be
enforced by a database constraint alone). Any such check must live in `learner_progress/checks.py`,
registered from `LearnerProgressConfig.ready()`, with an app-label-namespaced ID
(`freedom_ls_learner_progress.E00N`/`W00N`), one condition per ID, no DB access, and a legend that never
reuses a retired ID.

---

## Constraints this feature must respect

1. **Retirement must be `is_active=False`, never a cascade or hard delete** — matching the `Learner`
   precedent's "records never cascade; entitlement does"
   (`learners-associated-with-organisations/1. spec.md:883-887`). A hard delete would break
   `certificates`' need for a durable, `PROTECT`-able anchor (§3) and `xapi_implementation`'s need for
   a never-reused pass identifier (§5).
2. **`content_snapshots` may only ever be depended on, never depend on `learner_progress`.** Any
   snapshot reference this feature stores must be a nullable FK/id on the progress side
   (`content_snapshots/0. idea.md:23, 75`).
3. **The `on_delete=PROTECT` decision for `FormProgress.form`/`TopicProgress.topic`/
   `CourseProgress.course`** (hard-deleting the content itself) is a separate axis from this feature's
   own `SET_NULL`-on-placement-removal decision, and the two must not be merged
   (`final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md:256-262`).
4. **This feature's migration must land before, and must not be touched by, the project-wide migration
   reset** — the reset runs last, regenerates `0001_initial` per app from the *final* shape, and is a
   declared one-time exception to "never edit existing migration files," not a precedent this feature
   should imitate (`final_pre_deploy_db_structure_cleanup/research_migration_reset_strategy.md:234-238`,
   `224-232`).
5. **Do not add indexes or timestamps to models this feature is mid-redesign on** — the cleanup idea
   explicitly defers that work until after this feature lands
   (`final_pre_deploy_db_structure_cleanup/idea.md:162-165`).
6. **`basic_reports`' "first attempt" and "latest attempt" conventions must be re-scoped to "within one
   pass," not silently pooled across a learner's `CourseProgress` history** (§13). This feature's spec
   should say so explicitly rather than leave it to be discovered as a report bug.
7. **A `CourseProgress` row's identifier must remain stable and reusable as an xAPI `registration`
   value** and as a `Certificate` FK target — never recreated in place, never reused for a different
   pass (§3, §5).
8. **Any new system check follows the house conventions**: app-label-namespaced ID, one condition per
   ID, registered from `AppConfig.ready()`, no DB access, never raises, respects the `app_configs`
   contract, never reuses a retired ID (§14).
9. **`FormProgress`'s per-attempt-row shape must survive the re-scope to `ContentCollectionItem`
   intact** — `exam-timeouts` and the question-pool ideas both add fields to that row and assume its
   existing one-row-per-attempt semantics are unchanged (§6, §9).

---

## Decisions this feature should make now rather than later

1. **Decide, in the spec, which of `learner-management-actions`'s three mitigation shapes (§1) the
   retirement design leaves room for.** The current "retirement reacts to this registration's
   deactivation" design makes a naive same-organisation cohort move destructive by default. At minimum,
   state explicitly whether a future move-action's re-pointing of `cohort_registration` (option 1, the
   cheapest) is compatible with the retirement receiver as specced, since that sibling feature cannot
   be written until this one commits to an answer.
2. **Decide now whether `CourseProgress`/`FormProgress` takes a first, real dependency on
   `content_snapshots`, or explicitly re-defers the question a second time.** The open question in this
   feature's idea file ("does `FormProgress` need a content snapshot?") has not actually been closed by
   anything shipped — the adjacent research recommendation to snapshot per-answer text on
   `QuestionAnswer` was explicitly declined (`final_pre_deploy_db_structure_cleanup/idea.md:110-116`).
   Leaving it open a second time means the next feature to touch this (report-upgrades, certificates,
   or a future content-audit need) rediscovers the same unanswered question with less context than
   exists right now.
3. **State explicitly, in the spec, which `CourseProgress` row an organisation-scoped or
   person-scoped surface should read when more than one exists** — `basic_reports`' definitions block,
   the quick-view panel (§10), and any future periodic report (§8) all need the same answer
   ("the current, `is_active=True` pass for the resolved organisation"), and it should be stated once,
   here, rather than independently re-derived by each consumer.
4. **Decide whether deadlines and any other clearly person-scoped (not organisation-scoped) concept
   resolve per `user` or per `learner`/`CourseProgress`**, following the `deadline_utils.py` precedent
   (§12) — and say so in the spec even where the answer is "unaffected, this feature introduces no new
   person-scoped concept," so a future reader does not have to re-derive the precedent from a different
   app.
5. **Name `CourseProgress.id` explicitly as the future xAPI `registration` value and the future
   `Certificate` FK target in the spec's own words**, even though neither downstream feature is built
   yet — this converts two independently-arrived-at future requirements (§3, §5) into a single design
   note this feature's authors can point at, rather than trusting both future specs to rediscover it.

---

## Documents that will need reconciling once this idea settles

- **`spec_dd/1. next/learner-management-actions/idea.md`** cites the deleted `1. spec.md`'s section
  numbers directly and will not resolve until the replacement spec exists: "the retirement receiver
  (spec §5.6)" (`idea.md:27`), "the learner's next visit resolves a different registration and starts a
  new progress record from zero (spec §5.3)" (`idea.md:28`), "The current spec records this as an
  accepted consequence (§3.1, §14 'no merge or transfer')" (`idea.md:29-30`), and "that is
  `better_course_progress_tracking` §2.1 working as designed" (`idea.md:58-59`). It also still names
  the pre-rename app and model: `student_management/admin.py:22-45`, `UserCourseRegistration`, and
  `CourseProgress` (`idea.md:12, 92-99`) — all of which are now `learner_management`,
  `LearnerCourseRegistration`/`CohortCourseRegistration`, and the re-keyed `CourseProgress` this feature
  produces.
- **This feature's own `idea.md`** (`spec_dd/2. in progress/better_course_progress_tracking/idea.md`)
  describes an earlier design (`CourseRun`, `is_current`, no registration FK, `(user, course,
  organisation)` identity — `idea.md:64-99`) that the baked-in design this task treats as fact has
  since superseded (`Learner`-keyed, `is_active`, `learner_registration`/`cohort_registration` FKs
  present). The idea file itself will need updating to match whatever the replacement spec settles on,
  including its "Rejected: also hanging `user_registration`/`cohort_registration` FKs off the run"
  section (`idea.md:82-95`), which the baked-in design directly reverses.
- **`spec_dd/2. in progress/final_pre_deploy_db_structure_cleanup/idea.md` and its research files**
  refer to this feature by its old shape throughout — "`CourseProgress` → `CourseRun`" and
  "re-keys `TopicProgress`/`FormProgress` to placements" (`idea.md:163-164`), and the roadmap-pressure
  research's "the sibling spec's `CourseRun` (a new, per-pass row, `idea.md:41-54`) *is* that frozen
  record" (`research_roadmap_pressure.md:32`). These should be re-checked once this feature's real
  final model name and shape are settled, since "`CourseRun`" may not be the name that ships.
- **`content_snapshots/0. idea.md`**'s own open question about a consumer, and this feature's mirrored
  open question about needing a snapshot, should be reconciled into one answer rather than left as two
  documents each deferring to the other.

status: ok
