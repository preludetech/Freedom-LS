# Schema proposal: registration-scoped course progress

> Working note for `spec_dd/2. in progress/better_course_progress_tracking/`. Written against the
> tree on `better_course_progress_tracking`, after the `learner-terminology-rename`,
> `basic_reports`, `fls-integration-system-checks` and `learners-associated-with-organisations`
> merges. Feeds the spec phase; not itself a spec.

## The reframe

Create a `CourseProgress` row **at registration time**, fanning out one row per affected `Learner`
when the registration is cohort-wide. `TopicProgress` and `FormProgress` hang off that row.

This makes **`CourseProgress` the per-learner enrolment record.** It is
`research_django_modelling_and_migration.md` §2 option D — the recommended one — arrived at from the
other direction. That research proposed materialising a per-learner *registration* to collapse the
cohort/individual polymorphism before it reaches progress. Materialising the *pass* instead achieves
the same collapse without adding a model. Nothing downstream has to branch on "was this a cohort or
an individual registration?"

Two consequences fall out for free:

- **Site scoping fixes itself.** `Learner` is a `SiteAwareModel`, so `UNIQUE(learner, course)` is
  transitively per-tenant. No `site_id` in the uniqueness key, and consequence #1 of the idea file
  closes without an organisation column.
- **The signal's upward traversal dies.** `update_course_progress_on_completion`
  (`learner_progress/signals.py:35-97`) currently walks `ContentCollectionItem` upward to find every
  parent course of a completed item. A row that knows its `CourseProgress` knows its course
  directly. That retires the `@claude` TODO at `signals.py:43`, and it also stops the function
  minting `CourseProgress` rows for courses nobody registered for — consequence #5.

## Models

### `CourseProgress`

```python
class CourseProgress(SiteAwareModel):
    """One learner's pass through one course, granted by one registration."""

    learner = models.ForeignKey(
        Learner, on_delete=models.PROTECT, related_name="course_progress_records"
    )
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="progress_records"
    )

    #: "This is the live pass." NOT a permission flag — see Access control below.
    is_active = models.BooleanField(default=True)

    # Exactly one is set while active. Bound to the *registration*, never to
    # CohortMembership: membership churn is a bad lifecycle signal.
    learner_registration = models.ForeignKey(
        LearnerCourseRegistration, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="course_progress_records",
    )
    cohort_registration = models.ForeignKey(
        CohortCourseRegistration, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="course_progress_records",
    )

    #: Escape hatch for a future cohort-move that wants a clean per-cohort
    #: record instead of re-pointing. Column now; no behaviour built on it.
    continued_from = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="continuations",
    )

    created_at = models.DateTimeField(auto_now_add=True)      # registration minted it
    started_at = models.DateTimeField(null=True, blank=True)  # first content access
    last_accessed_time = models.DateTimeField(null=True, blank=True)  # explicit, not auto_now
    completed_time = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.IntegerField(default=0, db_index=True)

    #: Replaces the GenericForeignKey resume pointer. A concrete FK to the
    #: placement, so resume identifies a position even once a Topic can be
    #: placed twice.
    last_accessed_item = models.ForeignKey(
        ContentCollectionItem, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        verbose_name_plural = "Course progress records"
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "course"],
                condition=models.Q(is_active=True),
                name="one_active_pass_per_learner_course",
            ),
            models.CheckConstraint(
                # An active pass must name exactly one grant. A retired pass may
                # name none — SET_NULL has to be allowed to land somewhere legal.
                check=(
                    models.Q(is_active=False)
                    | (
                        models.Q(learner_registration__isnull=False)
                        & models.Q(cohort_registration__isnull=True)
                    )
                    | (
                        models.Q(learner_registration__isnull=True)
                        & models.Q(cohort_registration__isnull=False)
                    )
                ),
                name="active_pass_has_exactly_one_grant",
            ),
        ]
```

`clean()` should assert `learner.site_id == course.site_id`, and that the grant's course matches
`course`.

### `TopicProgress` / `FormProgress`

```python
class TopicProgress(CourseItemProgress):
    course_progress = models.ForeignKey(
        CourseProgress, on_delete=models.CASCADE, related_name="topic_progress"
    )
    #: Where the content sits (the placement).
    collection_item = models.ForeignKey(
        ContentCollectionItem, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="topic_progress",
    )
    #: What the content is. Kept alongside so "did they complete this topic
    #: anywhere in this pass?" stays a one-line filter.
    topic = models.ForeignKey(
        Topic, on_delete=models.PROTECT, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    complete_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Topic progress records"
        constraints = [
            models.UniqueConstraint(
                fields=["course_progress", "collection_item"],
                name="one_topic_progress_per_placement_per_pass",
            )
        ]


class FormProgress(CourseItemProgress):
    course_progress = models.ForeignKey(
        CourseProgress, on_delete=models.CASCADE, related_name="form_progress"
    )
    collection_item = models.ForeignKey(
        ContentCollectionItem, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="form_progress",
    )
    form = models.ForeignKey(
        Form, on_delete=models.PROTECT, related_name="progress_records"
    )
    # start_time / last_updated_time / completed_time / scores unchanged.
    # Many rows per (course_progress, collection_item) — one per attempt.
    # No uniqueness constraint, as today.
```

The `user` FK comes off both item-progress models. It is `course_progress__learner__user` now.

**No `attempt_number` column.** The reports defect the idea file describes — a new pass's first
sitting renumbered as N+1 — is fixed by *scoping* attempts to the pass, not by numbering them.
Ordering within a pass by `completed_time`/`start_time` already answers "first attempt" and "latest
attempt" once the pass bounds the set. An explicit counter would need allocation under concurrency
for no gain.

`QuestionAnswer` is unchanged apart from `__str__`, which reads `form_progress.user`.

### Read-path shape

Educator and report queries get *cheaper*, not dearer. "This cohort registration's item progress"
becomes `filter(course_progress__cohort_registration=X)` — one join, replacing the educator matrix's
current `OuterRef("learner__user")` subquery (`educator_interface/views.py:360-366`), which also
picks an arbitrary row and applies no organisation filter today. Suggested indexes:
`(course_progress, complete_time)` on `TopicProgress`, `(course_progress, completed_time)` on
`FormProgress`.

## Four things the sketch does not yet cover

### 1. `SET_NULL` and "exactly one" are in direct conflict

The idea file commits to both — `SET_NULL` on the grant FKs *and* exactly-one-is-set. Delete a
registration and the row violates its own invariant: the first `DELETE` on a `CohortCourseRegistration`
raises an `IntegrityError` from the database, not from application code. The conditional
`CheckConstraint` above resolves it by requiring exactly-one only while `is_active`.

The alternative is `PROTECT` on both grant FKs, relying on FLS having no unregister flow and using
`is_active` throughout. That keeps the invariant unconditionally but blocks deleting a cohort
registration that has ever been used. The conditional check is the better trade.

### 2. Eager creation breaks `start_time`

Today a `CourseProgress` row existing means the learner started. Minting at registration makes
`start_time` (an `auto_now_add`) meaningless, and `last_accessed_time` is currently `auto_now` — so a
background percentage recalculation bumps it. Hence the `created_at` / `started_at` / explicit
`last_accessed_time` split above.

This is not cosmetic. Everything that currently infers "has begun" from row existence or those
timestamps needs revisiting:

- `_detail_cta_label` (`learner_interface/views.py:130-136`) — the Start / Continue / Review CTA
- `get_current_courses` and `get_completed_courses` (`learner_interface/utils.py:683-728`)
- the reports' `NoRecordedActivityRule` (`reports/at_risk.py:56-64`) and `has_any_progress`

### 3. Pointing at `ContentCollectionItem` is safe — verified

`content_save` creates placements with `update_or_create` keyed on
`(site, collection_type, collection_id, child_type, child_id)`
(`content_engine/management/commands/content_save.py:677`), so re-importing content preserves row
PKs. It never sweeps stale items, so a placement disappears only by deliberate act. Two
consequences:

- `SET_NULL` on `collection_item` keeps the completion record when a placement is deleted. "Did this
  learner ever complete this?" is an audit answer that must survive a content edit — and per
  `research_shared_content_across_courses.md`, cascade-deleting it would be a genuine data-loss
  problem.
- Because PostgreSQL treats NULLs as distinct in a unique index, orphaned rows coexist happily under
  `one_topic_progress_per_placement_per_pass`. No special handling needed.

Keeping the `topic`/`form` FK alongside the placement FK is what keeps the read side cheap. Note this
goes one step further than `research_shared_content_across_courses.md` recommended (it favoured
course-scoping only, deferring placement-scoping until the same topic twice in one course became a
real requirement) — but with the `CourseProgress` FK already present, the placement FK costs one
column and closes the case permanently.

### 4. Do not make the pass the permission gate

Keep permission where it already lives — `is_registered_for_course`
(`learner_management/utils.py:69-101`), organisation-blind, exactly as the shipped Organisations spec
decided — and use the pass purely as the state container. Making the pass the gate drags in a nest
of edge cases: a learner removed from a cohort still has a live `cohort_registration`; a learner
holding both a cohort and an individual grant has one pass naming only one of them; and
`CourseProgress.is_active` starts doing double duty as both "current pass" and "may enter".

Three clean, separable checks:

| Question | Answered by |
|---|---|
| May the learner enter? | `learner.is_active` AND any live grant for this course (existing code, unchanged) |
| Which pass does the work land in? | the one active `CourseProgress` (the uniqueness constraint) |
| Which items are unlocked? | sequential-unlock read of `TopicProgress`/`FormProgress` *within that pass* |

State this explicitly in the spec. Four models now carry `is_active`, and this is the one place the
meanings could quietly diverge.

## Sync service

Fan-out is application logic — not a migration, not a database constraint. One idempotent service
function, called from four places, using `bulk_create` for large cohorts.

| Event | Action |
|---|---|
| `LearnerCourseRegistration` created or reactivated | ensure a pass exists |
| `CohortCourseRegistration` created or reactivated | fan out to all current members |
| `CohortMembership` created, cohort has an active course registration | ensure a pass exists |
| Membership removed, registration deactivated, learner deactivated | **do nothing to the pass** |

That last row is the important one. Every system surveyed in
`research_enrolment_bound_progress_lifecycle.md` preserves by default: Moodle's cohort-sync data
loss is the cautionary tale, Docebo deliberately decoupled group churn from enrolment, and every
system offering a real fresh start (SCORM's new registration, Absorb re-enrolment, Totara
recertification, Moodle `local_recompletion`) makes the reset an explicit named operation. Only an
explicit retake action retires a pass and mints a new one — and that belongs to
`spec_dd/1. next/learner-management-actions/`, not to this work.

Idempotency rule: if an active pass already exists for `(learner, course)`, leave it alone. Do not
re-point its grant FK, do not reset it.

Open items for the spec, not decided here:

- Transaction boundaries — fan-out on `post_save` versus `transaction.on_commit`, and what a partial
  failure mid-fan-out leaves behind.
- `FormProgress.get_or_create_incomplete` / `get_latest_incomplete` / `finalise_stale_incomplete`
  take `(user, form)` today across six call sites in `learner_interface/views.py`. They become
  `(course_progress, collection_item)`. Scoping some but not all lets an attempt started under one
  pass be resumed or finalised under another.
- `course.registered` fires from `LearnerCourseRegistration.save()` and uses `Learner._base_manager`
  deliberately. Because the pass now exists by then, the payload can carry the pass id as well as
  `organisation_id` — but the organisation lookup it gains must respect the same no-ambient-site
  constraint.

## The two future cases

**Moving a learner between cohorts.** Re-point `cohort_registration` on the existing row, inside the
move action. Do not copy. `research_enrolment_bound_progress_lifecycle.md`'s verdict is explicit:
mitigation (a), rejecting both the deferred-comparison and the rebuild-Open-edX alternatives. A move
is a human act, so making the transfer part of that action is the deliberate decision the design
already trusts, made explicit at the one point where it currently isn't. `continued_from` stays
unused unless a hard per-cohort reporting boundary is later wanted.

**A learner registered twice for the same course.** The partial unique constraint already prevents a
second *active* pass, so let the database enforce it and let the educator interface render the
friendly error. Because the constraint is conditional on `is_active`, retakes stay representable the
day they are wanted, with no migration.

## Not addressed here

Unchanged from the idea file's non-goals: no attempt-history UI, no learner-facing organisation
switch, no validity/expiry/recertification window, no content snapshots pinned to a pass, no
`Learner` deletion path, no registration-level provenance. `RecommendedCourse` stays `User`-keyed.

Still owed by the spec and not in scope of this note: the deadline re-scoping to `Learner` grain
(seven `learner__user=` filters in `learner_management/deadline_utils.py`), the reports app's
"first attempt"/"latest attempt" conventions re-scoped to within one pass, and the migration —
wipe existing progress, add the new columns non-nullable, ship the migration in the same PR since
`freedom_ls/contrib/conformance/test_migrations.py:19-26` asserts none are pending.
