# Better course progress tracking

## Problem

Progress is currently keyed on `(user, content item)`, not on a learner's *pass through a course*:

- `TopicProgress` — `unique_together = ["user", "topic"]`
- `CourseProgress` — `unique_together = ["user", "course"]`
- `FormProgress` — many rows per `(user, form)`, one per attempt (the one model that already has attempt semantics)

Three consequences fall out of that:

**1. A learner can only ever do a course once.** `UserCourseRegistration` is hard-unique on
`(site_id, collection, user)`, and the two progress constraints above mean there is nowhere to put a
second pass. Renewals, recertification, and cohort re-runs after a fail cannot be represented at all.

**2. Sharing content between courses corrupts progress in both.** Nothing in `ContentCollectionItem`
stops the same `Topic` or `Form` being linked into two courses — this is possible *today*, just not
yet exercised. Because `TopicProgress` has no course dimension and `calculate_course_progress_percentage`
tests against a **global per-user set** of completed item IDs, completing a topic in a "revision"
course would silently tick it in the full course, and vice versa. The planned modular-courses feature
walks straight into this.

**3. Progress can't be attributed.** With a learner registered both directly and via a cohort, there is
no way to say which registration a completion happened under — which the queued `certificates` and
`basic_reports` work will both want.

## Goal

Give a learner's pass through a course a first-class identity that owns their progress, so a course can
be taken more than once and shared content stays independent per course.

## Shape

Promote today's `CourseProgress` into **`CourseRun`** — the per-learner, per-course container that owns
all item progress. It already does most of this job: it is created lazily when a learner starts, and it
carries start / last-accessed / completed times, the percentage, and the resume pointer. The change is to
let there be more than one per `(user, course)`, and to make item progress hang off it.

```
CourseRun  (was CourseProgress)
    user, course
    user_registration    -> nullable FK   (provenance: how access was granted)
    cohort_registration  -> nullable FK   (provenance)
    is_current           -> bool
    start_time / last_accessed_time / completed_time
    progress_percentage
    last_accessed_item   -> GFK resume pointer (unchanged)

    UNIQUE (user, course) WHERE is_current

TopicProgress.run  -> FK CourseRun (non-null)
FormProgress.run   -> FK CourseRun (non-null)
```

The registration FKs are **provenance, not identity**. They record how the learner got in; they are not
what progress points at, and nothing on the read path has to branch on them.

### Why this shape

`is_registered_for_course()` stays exactly as it is — derived live from cohort membership on every check.
That is the load-bearing consequence: removing someone from a cohort revokes access immediately, with no
sync service, no staleness window, and no N×M materialised rows. The alternative shape (auto-create a
`UserCourseRegistration` per cohort member) buys a single unified registration concept but pays for it
with a reconciliation service that Moodle itself doesn't trust — it runs an hourly cron *behind* its
event observers as a backstop.

Progress gets one non-nullable, non-polymorphic FK. No generic FK on the hot path, no two-nullable-FK
branching in every consumer, one `select_related` hop.

This also completes a pattern FLS already half-adopted: `CohortDeadline`, `StudentDeadline` and
`UserCohortDeadlineOverride` already hang off registrations rather than off `(user, course)`.

## Placement-scoped item progress

`TopicProgress` and `FormProgress` are scoped to the **placement** — the `ContentCollectionItem` row that
links the content into a course or part — not to the bare `Topic`/`Form`:

```
TopicProgress:  UNIQUE (run, placement)
FormProgress:   many rows per (run, placement), one per attempt
```

This is the definition-vs-usage split every comparable system draws: Open edX keys `StudentModule` on
`(student, module_state_key, course_id)`; SCORM scopes to a registration; LTI to a `resource_link_id`.
Progress attaches to where content is *used*, never to the shared content object itself.

Scoping to the run alone would already give per-course independence (a run is per-course). Going to
placement additionally handles the same topic appearing twice within one course, and it pays for part of
its own cost: `update_course_progress_on_completion` currently has to trace *upward* from a content item
through `ContentCollectionItem` to find every course that contains it. A placement-scoped progress row
already knows its placement and its run, so the course is known directly and that traversal disappears —
which is most of why that function is long enough to carry a `@claude` refactor TODO.

The cost is real and should not be hand-waved at spec time: `children()` must expose placement identity,
every "has this learner completed this topic" check must decide whether it means *this placement*, and
deleting a placement needs an explicit policy. A removed placement must **not** cascade-delete the
completion record — mirror `CourseProgress.last_accessed_content_type`'s existing `SET_NULL` treatment so
history survives a content edit.

## Runs are created explicitly

A new `CourseRun` is created only by a deliberate action — an educator or admin re-registering a learner,
or a renewal. Reactivating a lapsed registration resumes the existing run.

This distinction matters: renewal and cohort re-runs want a clean start, but unregister-then-re-register
(access revoked in error, or a lapsed subscription restored) is exactly the case where the learner should
get their work back. An automatic rule cannot tell those apart.

A new run **hard-resets item completion** — no partial credit carried across runs. Every product surveyed
(Totara, Moodle `local_recompletion`, Docebo, Absorb) defaults this way, and none offers cross-run
carry-over. The one place "keep the best score" legitimately exists is across attempts *within* one run,
which `FormProgress` already supports.

Resolution rule when several runs exist: **the current run** (`is_current`). All learner-facing views and
all default reports read only that row. Prior runs stay in the table, queryable, but never merged into a
default result set — which is how Absorb avoids the double-counting its competitors' users complain about.

## Explicitly not in scope

- **No attempt-history UI.** Prior runs are queryable but not surfaced to learners or educators yet.
- **No validity / expiry / recertification-window concept.** Totara-style windows are real complexity
  (drift rules, window-open state, auto-re-enrolment) with a documented failure mode where an early
  retake isn't credited. This work is the substrate one would sit on; adding `valid_until` later is
  additive once multiple runs exist, and a rewrite if they don't.
- **No unregister flow.** There isn't one today — no view, no admin action, no command sets
  `is_active=False`. This idea doesn't build one.
- **No modular-courses authoring.** Only the schema that stops it being a lossy migration later.

## Open questions for the spec phase

**Does `UserCourseRegistration`'s unique constraint need to change at all?** Probably not, and this is a
useful narrowing. With repeat-pass identity living on `CourseRun`, a registration can stay "does this
person currently have access", toggled by `is_active`, while run history carries the dates. Renewal
reactivates the registration and starts a new run; a cohort re-run means a new `Cohort`, so the
`(site, course, cohort)` constraint is untouched. Confirm this before anything else — every other
decision is downstream of it. If historical *registration* rows turn out to be wanted independently of
runs, the answer is a partial unique index (`condition=Q(is_active=True)`), not dropping the constraint.

**Which run do the webhooks mean?** `course.registered` and `course.completed` carry no run or
registration id today. Both this work and the queued `xapi_implementation` will independently want one.

**Does `FormProgress` need a content snapshot?** Content can change between a learner's first and second
run. Pairing `FormProgress` with the queued `content_snapshots` work is a natural fit but is not in scope.

## Known landmines

- `student_interface/views.py:1071` — `course_finish` does `get_object_or_404(CourseProgress, user=, course=)`.
  This raises `MultipleObjectsReturned` the moment a second run exists. It is a hard 500 on course
  completion for exactly the learners this feature serves, and must be fixed in the first change that
  touches read paths.
- Several read paths silently pick an arbitrary row rather than crashing — `.first()` on assumed
  singletons in `get_resume_index` and the player chrome, `{cp.course_id: cp}` dict collapses in
  `get_current_courses` / `get_course_listing`, and `Subquery(...)[:1]` in the educator matrix. These
  produce plausible-but-wrong percentages with nothing to grep for. They need tests asserting *which*
  run's data appears, not just that the page renders.
- `FormProgress.get_or_create_incomplete` / `get_latest_incomplete` / `finalise_stale_incomplete` are
  used across four view call sites. Scoping some but not all of them lets an attempt started under one
  run be resumed or finalised under another.
- Test coverage for "two runs, same course, same learner" is entirely net-new — the current constraints
  make such a test impossible to write today.
- The two `@claude` TODOs in `student_progress/models.py` are entangled with this change. Fold them in
  rather than touching that code twice. Do not delete them either way.

## Sequencing

This should land **before** `basic_reports` and `certificates`. Both read `CourseProgress` directly;
built first, they would silently report on an arbitrary run. `certificates` in particular must bind to a
frozen completion record rather than a live `(user, course)` query — Moodle's `mod_customcert` regenerates
from a mutable completion date, so certificates silently change after a recompletion reset, which is the
opposite of tamper-evident.

## Research

- `research_lms_enrolment_models.md` — Moodle / Canvas / Open edX / Totara / SCORM / LTI
- `research_recertification_and_retakes.md` — renewal, retakes, completion history, certificate binding
- `research_cohort_group_enrolment.md` — materialise vs derive group access
- `research_shared_content_across_courses.md` — definition vs usage, modular courses
- `research_django_modelling_and_migration.md` — constraints, FK shapes, migration mechanics
- `research_fls_impact_surface.md` — full blast radius with `path:line` citations
