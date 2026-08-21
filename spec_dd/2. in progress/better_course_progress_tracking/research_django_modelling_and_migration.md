# Research: Django/PostgreSQL modelling and migration mechanics for registration-scoped progress

Scope: model/constraint/migration mechanics only, per brief. Current shapes read from
`freedom_ls/student_progress/models.py`, `freedom_ls/student_management/models.py`,
`freedom_ls/site_aware_models/models.py`.

## Current shapes (verified)

- `SiteAwareModel` (`site_aware_models/models.py:53-84`): abstract base, UUID PK
  (`models.UUIDField(primary_key=True, default=uuid.uuid4)`), a `site = ForeignKey(Site,
  on_delete=PROTECT)` on every subclass, and `SiteAwareManager.get_queryset()` auto-filters
  `.filter(site=site)` from a request-bound thread-local. `save()`/`full_clean()` auto-populate
  `site` from the request if unset.
- `TopicProgress` (`student_progress/models.py:542-563`): `user` FK + `topic` FK, CASCADE both,
  `unique_together = ["user", "topic"]`.
- `FormProgress` (`models.py:126-149`): `user` FK + `form` FK, CASCADE both, **no** uniqueness —
  many rows per (user, form), one per attempt, disambiguated by `start_time`/`completed_time`.
- `CourseProgress` (`models.py:566-611`): `user` FK + `course` FK, CASCADE both,
  `unique_together = ["user", "course"]`. Carries a `GenericForeignKey` `last_accessed_item`
  (`last_accessed_content_type` SET_NULL, `last_accessed_object_id` UUIDField) — nullable,
  best-effort resume pointer, explicitly documented in-code as "existing rows and freshly
  registered learners have none, falls back to item 1."
- `UserCourseRegistration` (`student_management/models.py:46-97`): `collection` (Course) FK CASCADE,
  `user` FK CASCADE, `is_active` BooleanField default True, `UniqueConstraint(fields=["site_id",
  "collection", "user"], name="unique_user_course_registration")` — **hard** unique constraint, no
  `condition`, so only one registration per (site, course, user) ever, active or not.
- `CohortCourseRegistration` (`models.py:100-123`): `collection` FK + `cohort` FK, CASCADE both,
  `is_active` BooleanField, `UniqueConstraint(fields=["site_id","collection","cohort"])` — one
  registration per (site, course, cohort). Access for a member is derived via `CohortMembership`
  (`models.py:30-43`, itself just `UniqueConstraint(fields=["user","cohort"])`) — there is
  **no existing per-(user, cohort_registration) row anywhere in the schema**.
- `CohortDeadline`/`StudentDeadline`/`UserCohortDeadlineOverride` already use a conditional
  `UniqueConstraint(..., condition=Q(content_type__isnull=False, object_id__isnull=False))` pattern
  to make a GFK-target-based uniqueness rule optional — direct, working precedent for the
  partial-unique-index technique used below.

---

## 1. Allowing repeat registrations

### A. Partial unique index — `condition=Q(is_active=True)` (recommended)

Django's `UniqueConstraint.condition` takes a `Q` object; when set, Django implements the
constraint as a **`CREATE UNIQUE INDEX ... WHERE <condition>`**, not a table-level `UNIQUE`
constraint (same restrictions as `Index.condition`: no subqueries, no references to other tables,
deterministic expressions only).
([Django 6.0 docs — Constraints reference](https://docs.djangoproject.com/en/6.0/ref/models/constraints/))

```python
class UserCourseRegistration(SiteAwareModel):
    collection = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="user_registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "collection", "user"],
                condition=models.Q(is_active=True),
                name="unique_active_user_course_registration",
            ),
        ]
```

Postgres semantics: `WHERE is_active` is not nullable in this schema (`BooleanField(default=True)`,
never `null=True`), so there's no NULL-in-the-condition gotcha here — the index simply omits rows
where `is_active = false`. Historical (inactive) rows are entirely unconstrained by uniqueness —
a user can accumulate arbitrarily many old, deactivated registrations for the same course, and at
most one active one at a time. This directly matches the existing `CohortDeadline`/`StudentDeadline`
conditional-uniqueness precedent already in this file, just with a boolean condition instead of a
"both GFK columns non-null" condition.

**NULL-handling gotcha that does matter in general** (not for this exact field, but worth stating
since the brief asks for it): a plain `UNIQUE (a, b)` constraint in Postgres treats `NULL`s as
*distinct from each other* by default — two rows with `b IS NULL` do **not** violate uniqueness.
If any field that participates in a future key here were nullable (e.g. a nullable `cohort_registration`
FK — see §2), you'd need to decide whether multiple NULLs should collide, which is exactly what
`nulls_distinct` (below) controls. It is irrelevant for `is_active`/`site_id`/`collection`/`user`
here because none of them are nullable.

### B. Explicit `attempt_number`/`run` in the unique key

```python
class UserCourseRegistration(SiteAwareModel):
    ...
    attempt_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "collection", "user", "attempt_number"],
                name="unique_user_course_registration_attempt",
            ),
        ]
```

Race-safe allocation options, from weakest to strongest guarantee:

- **`Max(attempt_number)+1` under `select_for_update`** — locks *existing* matching rows, not the
  as-yet-nonexistent next row, so two concurrent transactions can both compute `next = 3` if no row
  currently exists to lock (classic phantom-insert race). Only safe if you also serialize via a
  lock on something that *does* exist for every user/course pair (e.g. lock the `User` row itself,
  or a dedicated per-(user, course) sentinel row) before computing the max:
  ```python
  from django.db import transaction, IntegrityError

  def register_repeat(user: User, course: Course) -> UserCourseRegistration:
      with transaction.atomic():
          # lock a stable row so concurrent callers for the same user serialize
          User.objects.select_for_update().get(pk=user.pk)
          last = (
              UserCourseRegistration.objects.select_for_update()
              .filter(user=user, collection=course)
              .order_by("-attempt_number")
              .first()
          )
          return UserCourseRegistration.objects.create(
              user=user, collection=course,
              attempt_number=(last.attempt_number + 1) if last else 1,
          )
  ```
  `select_for_update()` requires an open transaction (`TransactionManagementError` otherwise) and is
  a no-op on SQLite — Postgres-only in practice.
  ([Alairjt — SELECT FOR UPDATE for race condition prevention](https://dev.to/alairjt/guarding-critical-operations-mastering-select-for-update-for-race-condition-prevention-in-django--32mg))
- **Unique-constraint + retry loop** — cheaper to reason about, no locking, just catch
  `IntegrityError` and retry with a fresh `Max()+1`:
  ```python
  for _ in range(5):
      try:
          with transaction.atomic():
              next_n = (UserCourseRegistration.objects.filter(user=user, collection=course)
                        .aggregate(models.Max("attempt_number"))["attempt_number__max"] or 0) + 1
              return UserCourseRegistration.objects.create(user=user, collection=course, attempt_number=next_n)
      except IntegrityError:
          continue
  ```
  Gives correctness (never two rows with the same number) but no gap-free/strictly-ordered
  guarantee under contention — acceptable since `attempt_number` here is a display/ordering aid,
  not a business-critical sequence.
- **A real Postgres sequence per group** is not natively expressible through Django's ORM without
  `RunSQL`/a custom sequence per `(user, course)` pair, which Postgres doesn't support cheaply
  (sequences are global objects, not per-key); this is the "textbook correct" answer for
  gap-free numbering but is unjustified ceremony here — skip it.

**For FLS specifically: option A (partial unique index) is the right primary constraint, and
`attempt_number` should not be added to any DB-enforced key at all.** The actual business
requirement is "at most one active registration"; anything used for *display* ordering ("attempt 1
of 2") can be derived at read time from `registered_at` ordering per user/course, with no DB
constraint and therefore none of the race-allocation problem above.

### C. `nulls_distinct` (Django 5.0+, PostgreSQL 15+)

`UniqueConstraint(nulls_distinct=False)` makes Postgres treat multiple `NULL`s in the constrained
columns as **not** distinct — i.e., at most one row may have `NULL` there, matching SQL:2023's `NULLS
NOT DISTINCT`. Default is `None` (defers to the DB default, which is "nulls distinct" i.e. `True`-like
behaviour, on Postgres). Only meaningful on PostgreSQL 15+; ignored elsewhere. **Known interaction
bug**: combining `condition` and `nulls_distinct` in the same `UniqueConstraint` generated invalid
SQL (`NULLS DISTINCT` clause ordered after `WHERE` instead of before) — fixed as a release blocker
for Django 5.0 (ticket #35329, backported to 5.0.x). If FLS pins an older Django 5.0.x patch level,
verify the fix is included before combining the two options.
([Django docs — Constraints, `nulls_distinct`](https://docs.djangoproject.com/en/5.1/ref/models/constraints/),
[Django ticket #34701 — Add NULLS [NOT] DISTINCT support](https://code.djangoproject.com/ticket/34701),
[Django ticket #35329 — bug: condition + nulls-distinct](https://code.djangoproject.com/ticket/35329))

Where it would matter here: **only if** a design puts a nullable FK inside a uniqueness key — e.g.
if progress carries a nullable `cohort_registration` FK (§2 option B/D) and you want "at most one
*course-level* (cohort_registration IS NULL) active registration row" enforced the same way multiple
non-null values are. FLS's recommended designs below don't end up needing this — flagged for
completeness per the brief, not because the recommended shape uses it.

### D. `Coalesce`-based expression index for a nullable FK in the key

If a nullable FK must participate in a uniqueness key (e.g. treating "no cohort" as a specific
sentinel rather than relying on `nulls_distinct`), Django supports expression-based unique
constraints (`UniqueConstraint` accepts positional expressions, same restrictions as
`Index.expressions`):

```python
from django.db.models.functions import Coalesce
import uuid

class CourseItemProgress(SiteAwareModel):
    ...
    class Meta:
        constraints = [
            models.UniqueConstraint(
                Coalesce("cohort_registration_id", models.Value(uuid.UUID(int=0))),
                "user", "topic",
                name="unique_progress_per_effective_scope_topic",
            ),
        ]
```
This forces every NULL `cohort_registration_id` to collapse to the same sentinel value for
uniqueness purposes — functionally similar to `nulls_distinct=False` but explicit and portable to
non-Postgres backends (`nulls_distinct` is Postgres-15+-only). Not needed for the recommended shape
in §2 (option D collapses the polymorphism before it reaches progress), included because the brief
asks for it.

---

## 2. Polymorphic "enrolment" parent

Progress must eventually resolve to "whose registration is this," where a learner reached the
course either via `UserCourseRegistration` directly or via `CohortMembership` +
`CohortCourseRegistration`. Four options, costed honestly:

### A. `GenericForeignKey` (existing FLS precedent: `CohortDeadline.content_item`,
`CourseProgress.last_accessed_item`)

```python
class TopicProgress(CourseItemProgress):
    enrolment_content_type = models.ForeignKey(DjangoContentType, on_delete=models.CASCADE)
    enrolment_object_id = models.UUIDField()
    enrolment = GenericForeignKey("enrolment_content_type", "enrolment_object_id")
```

- **No DB-level referential integrity.** Postgres cannot enforce that `enrolment_object_id` points
  at a real row — deleting a `UserCourseRegistration` leaves dangling GFK rows silently (this is
  exactly why `CourseProgress.last_accessed_item` uses `SET_NULL` and treats a dangling pointer as
  an acceptable, ignorable no-op — see the in-code comment at `models.py:590-592`). For a *primary*
  ownership relationship (not a best-effort display pointer), silent dangling references are a much
  worse failure mode: a progress row nobody can reach because its target no longer exists.
- **No `select_related`.** `select_related()` cannot traverse a GFK at all (it only works for
  FK/O2O forward relations); you must use `prefetch_related` with a `GenericPrefetch`/manual
  per-content-type prefetch, and Django's own `prefetch_related` + GFK + multiple target types is
  documented as *not* as efficient as a real join — historically issuing more queries than the
  naive expectation of "one query per content type" (Django ticket #22757).
  ([Django ticket #22757 — prefetch inefficiency with GFK](https://code.djangoproject.com/ticket/22757))
- **No cross-type aggregate filtering.** "All progress rows for cohort X's registration" cannot be
  expressed as a single `.filter(enrolment__cohort_course_registration=X)` — GFK has no join target,
  so you must first resolve the `ContentType` + id set for the relevant registrations, then filter
  `enrolment_content_type=ct, enrolment_object_id__in=ids`. This directly conflicts with the
  educator-matrix/cohort-PDF aggregate query shape in §5.
- **Admin** needs a custom `list_display`/`get_object` to resolve and link the target; no automatic
  admin inline/autocomplete across two unrelated tables.

**Verdict on precedent:** FLS's two existing GFK uses are both *nullable, best-effort, display-only*
pointers into a heterogeneous content catalog (`CohortDeadline`/`StudentDeadline` targeting "which
topic/form has a deadline, or none for course-level"; `CourseProgress.last_accessed_item` targeting
"whatever the learner last viewed, falls back to item 1 if unset/dangling"). Progress's relationship
to its *owning* registration is structurally different — non-optional, cascade-critical, and the
target of heavy aggregate querying. The precedent exists but should **not** be copied here; it was
designed for a different failure-tolerance profile.

### B. Two nullable FKs + `CheckConstraint` enforcing exactly-one

```python
class CourseItemProgress(SiteAwareModel):
    user_registration = models.ForeignKey(
        "student_management.UserCourseRegistration", null=True, blank=True,
        on_delete=models.CASCADE, related_name="%(class)s_records",
    )
    cohort_registration = models.ForeignKey(
        "student_management.CohortCourseRegistration", null=True, blank=True,
        on_delete=models.CASCADE, related_name="%(class)s_records",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # still needed: which cohort member

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user_registration__isnull=False, cohort_registration__isnull=True)
                    | models.Q(user_registration__isnull=True, cohort_registration__isnull=False)
                ),
                name="%(app_label)s_%(class)s_exactly_one_registration",
            ),
        ]
```
Pattern and Q-expression shape verified against a working "exactly one of two owner FKs" example.
([Abenezer Belachew — Avoiding GFKs with CheckConstraints](https://www.abenezer.ca/blog/generic-foreign-key-check-constraint),
[Django docs — CheckConstraint](https://docs.djangoproject.com/en/6.0/ref/models/constraints/))

- Real FK constraints, real referential integrity, real `on_delete` per branch, and — critically —
  `select_related("user_registration", "cohort_registration")` works in a single JOIN query. Cohort
  matrix filtering is a plain `.filter(cohort_registration=X)`.
- Cost: every consumer of "the" registration must branch (`progress.user_registration or
  progress.cohort_registration`, or a Python property wrapping that), scattered through templates,
  serializers, and aggregation code. Doubles the FK columns on every progress row. `CheckConstraint`
  with nullable fields needs the Oracle-NULL-handling caveat noted in Django's own docs (not
  relevant to Postgres, but worth knowing the docs call it out) — Postgres evaluates `CHECK` as
  "not proven false," so `NULL` operands in `Q(...isnull=True)` comparisons behave correctly here
  because `isnull=True` compiles to `IS NULL`, not `= NULL`.

### C. Multi-table inheritance with a concrete `Enrolment` parent

```python
class Enrolment(SiteAwareModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["site_id", "course", "user"], condition=models.Q(is_active=True),
            name="unique_active_enrolment")]

class UserCourseRegistration(Enrolment):
    registered_at = models.DateTimeField(auto_now_add=True)

class CohortDerivedRegistration(Enrolment):
    cohort_course_registration = models.ForeignKey(CohortCourseRegistration, on_delete=models.CASCADE)
```
Progress then carries a single, non-nullable `enrolment = ForeignKey(Enrolment, on_delete=CASCADE)`
— no branching anywhere in progress-consuming code, one `select_related("enrolment")`.

- Real cost: Django's concrete (multi-table) inheritance adds an **implicit JOIN back to the parent
  table on every query that touches child-specific fields**, and every insert/update/delete
  cascades across both tables. For a table queried as heavily as progress/registrations (every
  learner course view, every educator matrix render), this is a real, permanent tax, not a one-off
  migration cost.
  ([Jacob Kaplan-Moss — "Django gotcha: concrete inheritance"](https://jacobian.org/2010/nov/2/concrete-inheritance/))
- Downcast ambiguity survives, just one level up: "all Enrolments for cohort X" still needs to know
  which child type each row is (`hasattr(e, "cohortderivedregistration")` or two separate
  `select_related` calls unioned in Python) — the branching problem in option B doesn't disappear,
  it moves to whoever consumes `Enrolment` directly.
- FLS has **no existing precedent** for concrete-model inheritance anywhere in the codebase (grep
  shows only `SiteAwareModel`/`CourseItemProgress`-style **abstract** bases). Introducing MTI would
  be a genuinely new modelling primitive for this codebase, which is a real (if soft) cost given
  `CLAUDE.md`'s general "don't add new abstractions unless asked" bias — MTI is concrete, so it's
  not literally the forbidden "abstract base class," but it's the same category of new-primitive
  judgement call.
- Deeper issue specific to FLS: `CohortCourseRegistration` has no per-user row today at all — access
  is derived transitively via `CohortMembership`. An MTI child keyed one-per-cohort-registration
  (not one-per-member) still can't be what progress FKs to directly (progress is inherently
  per-learner), so MTI **also** ends up needing a new per-(user, cohort_registration) junction row —
  it doesn't avoid the modelling question raised in option D below, it just relocates it under an
  `Enrolment` umbrella.

### D. Single non-polymorphic target: auto-derive a per-user `UserCourseRegistration` for every cohort member (recommended)

Collapse the polymorphism *before* it reaches progress, by making `UserCourseRegistration` the only
thing progress ever points at, and giving it an optional provenance FK back to the cohort
registration that spawned it:

```python
class UserCourseRegistration(SiteAwareModel):
    collection = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="user_registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cohort_course_registration = models.ForeignKey(
        CohortCourseRegistration, null=True, blank=True, on_delete=models.CASCADE,
        related_name="derived_user_registrations",
    )
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "collection", "user"],
                condition=models.Q(is_active=True),
                name="unique_active_user_course_registration",
            ),
        ]

class TopicProgress(CourseItemProgress):
    registration = models.ForeignKey(
        UserCourseRegistration, on_delete=models.CASCADE, related_name="topic_progress",
    )
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="progress_records")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["registration", "topic"], name="unique_registration_topic")]
```

A service function (not a migration, not a DB constraint — application logic, mirroring how
`UserCourseRegistration.save()` already fires a webhook on creation at `student_management/models.py:66-94`)
creates/deactivates a `UserCourseRegistration(cohort_course_registration=...)` row whenever a
`CohortMembership` is added/removed for a cohort that has an active `CohortCourseRegistration`, and
whenever a `CohortCourseRegistration` is activated/deactivated.

- Progress models get a single, non-nullable, non-polymorphic FK — zero branching anywhere
  downstream, one `select_related("registration")`, ordinary FK/JOIN semantics throughout, and the
  cohort matrix query becomes a plain `.filter(registration__cohort_course_registration=X)`.
- The `unique_active_user_course_registration` partial index (§1A) now uniformly governs both
  self-registered and cohort-derived registrations — one constraint, one code path.
- Cost, stated plainly: this pushes real complexity into a **sync service**, not the schema —
  membership changes must reliably create/deactivate derived registrations, including backfilling
  when a `CohortCourseRegistration` is created *after* members already exist, and handling a member
  leaving a cohort (deactivate their derived registration, but only if it has no independent
  self-registration reason to stay active). This is a service-layer/business-logic design question
  belonging to the plan, not to this migration-mechanics research, but it is the direct trade-off
  against options B/C's "no sync needed, but branch everywhere" cost — flagged for the plan author.

**Recommendation:** option D for the schema shape (collapses the whole polymorphism question,
lowest downstream query/admin/N+1 cost, reuses the same partial-unique pattern once), with the
service-sync cost explicitly handed to the plan as a design item. If a sync service is judged too
much complexity for this iteration, option B (two nullable FKs + CheckConstraint) is the
second choice — it keeps real FK integrity and `select_related`-ability at the cost of branching in
consumer code, and needs no new sync mechanism. Option A (GFK) is not recommended despite the
existing precedent, and option C (MTI) doesn't actually solve the per-member modelling gap that
motivates this section, only relocates it.

---

## 3. Migration mechanics — no data to preserve

Given the product-owner fact that there is no production data anywhere (this repo's dev/demo DB and
every downstream install), the nullable-then-backfill-then-nonnull dance used for populated tables
(see the sibling `research_migration_and_rollout.md` for the *School* feature, which does have to
handle populated downstream data) is unnecessary machinery here. The only real question is whether
`migrate` should **fail loudly** on a database that still has old-shape progress rows, or **wipe
them automatically** so `migrate` always succeeds unattended.

### Option 1 — straight non-nullable `AddField`, document a manual pre-step

Write the FK as non-nullable directly in one migration:
```python
migrations.AddField(
    model_name="topicprogress",
    name="registration",
    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                             to="student_management.usercourseregistration"),
    preserve_default=False,
)
```
This is a normal Django `AddField`; whether it succeeds at `migrate` time depends purely on whether
the table has rows at that moment — a genuinely empty table accepts a `NOT NULL` column addition
with no default trivially (nothing to violate). `makemigrations` doesn't know at authoring time
whether the table will be empty when applied, so hand-author this operation rather than relying on
the interactive "provide a one-off default" prompt, which is an authoring-time UX safeguard, not a
runtime requirement.

Document in `upgrade_notes.md`: *"This migration fails if your database has existing
TopicProgress/FormProgress/CourseProgress/QuestionAnswer/UserCourseRegistration rows — old progress
data is not compatible with the new schema and is not migrated. Before running `migrate`, delete
those rows (or drop and recreate your dev database)."* Simple, but relies on every developer/CI job
remembering the manual step first — a real footgun for anyone who forgets and gets a raw
`IntegrityError`/`NotNullViolation` instead of a clear message.

### Option 2 — `RunPython` wipe, then non-nullable `AddField` (recommended)

```python
# freedom_ls/student_progress/migrations/00XX_wipe_progress_before_registration_fk.py
from django.db import migrations


def wipe_old_progress(apps, schema_editor):
    QuestionAnswer = apps.get_model("student_progress", "QuestionAnswer")
    FormProgress = apps.get_model("student_progress", "FormProgress")
    TopicProgress = apps.get_model("student_progress", "TopicProgress")
    CourseProgress = apps.get_model("student_progress", "CourseProgress")
    QuestionAnswer.objects.all().delete()
    FormProgress.objects.all().delete()
    TopicProgress.objects.all().delete()
    CourseProgress.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("student_progress", "000X_previous")]
    operations = [migrations.RunPython(wipe_old_progress, migrations.RunPython.noop)]
```
Followed, in the next migration(s), by the non-nullable `AddField`s from Option 1 — now guaranteed
to apply cleanly against every database, because within one `manage.py migrate` invocation Django
applies migrations strictly in dependency order, so the wipe has already run by the time `AddField`
executes. `apps.get_model` (historical models) is used, per this repo's own established convention
(`content_engine/migrations/0009_backfill_course_accent_slot.py`,
`student_management/migrations/0008_populate_user_from_student.py`) — never the real imported model,
since `SiteAwareModelBase.save()` reads a request-bound thread-local that doesn't exist during
`migrate` (irrelevant here anyway since this migration only deletes, but keep the convention for any
future edit to this file).
([Django 6.0 docs — Data Migrations / historical models](https://docs.djangoproject.com/en/6.0/topics/migrations/))

`reverse_code=migrations.RunPython.noop` — there is no meaningful "undo" for a delete, matching the
existing no-op-reverse precedent in `0009_backfill_course_accent_slot.py`.

**Recommended: Option 2.** It makes `manage.py migrate` succeed unattended on every dev machine, CI
job, and `demo_content` reseed run without requiring a remembered manual step, at the cost of one
small, well-precedented extra migration file. This is also the more honest artifact of the
product-owner's stated intent ("old progress data does not need to be migrated or preserved") — the
migration *itself* enacts that decision rather than merely documenting it as someone else's problem.

### `UserCourseRegistration`/`CohortCourseRegistration` constraint changes

The `UniqueConstraint(fields=["site_id","collection","user"])` → partial (`condition=Q(is_active=True)`)
change follows the existing remove-then-add sequencing precedent in this repo
(`student_management/migrations/0009_remove_student_fk_make_user_non_nullable.py:33-55`): issue
`RemoveConstraint` for the old constraint, then `AddConstraint` for the new one, as separate
operations (can be the same migration file, since no field types are changing — only when field
*types* change does that precedent split them across migrations). No wipe is needed for this step:
narrowing a plain unique constraint into a conditional one can never fail against existing data (a
condition can only make a constraint *more* permissive, never less, so no existing row can newly
violate it).

### `demo_content` and dev databases

`demo_content` is loaded via a management command/fixture, not via migrations, so it is unaffected
by the schema change directly — but any demo/seed script that pre-populates progress rows to make
the demo look "lived-in" will need updating in lockstep with this change (create demo
`UserCourseRegistration`s first, then demo progress against them) — flagged for the plan/implementer
since it wasn't in scope to audit `demo_content`'s seeding code in this research pass.

### `upgrade_notes.md`

No dedicated convention for *destructive* migrations exists yet in this repo — the closest
precedent, `spec_dd/3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/upgrade_notes.md`,
warns that a **new** constraint might fail against **existing** duplicate rows and tells operators to
dedupe first; this feature is the inverse case (existing rows are deliberately destroyed, not
merely constrained), so the existing schema (`requires_migrations` flag + `## Breaking changes` +
`## Manual steps`, per `claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-46`) is
sufficient to carry it, but the wording needs to be unambiguous and is the first of its kind in this
repo. Recommended `upgrade_notes.md` content for this feature:

```yaml
requires_migrations: true
```
> **Breaking changes** — `TopicProgress`, `FormProgress`, `CourseProgress`, and `QuestionAnswer` are
> repointed from `(user, content item)` to hang off a course registration. **This migration deletes
> all existing progress data** (`TopicProgress`, `FormProgress`, `CourseProgress`,
> `QuestionAnswer` rows) — there is no data-preserving upgrade path. `UserCourseRegistration` now
> allows repeat/inactive registrations (constraint narrowed to "at most one *active* registration per
> user per course"). Downstream projects with real learner progress must accept that progress is
> reset by this upgrade; there is no opt-out.
>
> **Manual steps** — run `manage.py migrate`. No pre-migration dedupe or backfill step is required
> or possible; the migration wipes affected tables itself.

---

## 4. Cascade and integrity

| FK | Recommended `on_delete` | Rationale |
|---|---|---|
| `TopicProgress.registration → UserCourseRegistration` | `CASCADE` | A progress row has no meaning without its registration; matches the existing `user`/`topic` `CASCADE` pattern already on every progress model in this file. |
| `FormProgress.registration`, `CourseProgress.registration` | `CASCADE` | Same reasoning. |
| `UserCourseRegistration.collection → Course`, `.user → User` | `CASCADE` (unchanged) | Already the existing behaviour; out of scope to change. |
| `UserCourseRegistration.cohort_course_registration → CohortCourseRegistration` (if option D adopted) | `CASCADE` | A derived registration has no purpose once its parent cohort registration is gone. |

**Deactivate over delete.** The whole point of the partial unique index (§1A) is that a
registration can be deactivated (`is_active=False`) without deleting it, preserving progress
history. Hard-deleting a `UserCourseRegistration` cascades and destroys that learner's entire
progress history for the course — almost never the intended operation. Recommend:

- Do not expose a raw "delete registration" action anywhere in educator/admin UI; only expose
  "deactivate" (`is_active=False`), matching the field that already exists on both registration
  models today.
- Enforcement is **not** a DB constraint (Postgres has no "soft-delete-only" primitive without
  triggers, and raw SQL/triggers are excluded by the ORM-only convention) — it is a service-layer
  rule: the delete path simply isn't wired up to any view/serializer/admin action. If stronger
  enforcement is wanted, `Meta.default_manager_name`/overriding `QuerySet.delete()` to raise, or a
  `pre_delete` signal that raises `django.db.models.deletion.ProtectedError`-style, are the only
  ORM-only options — flagged as an implementation choice for the plan, not required by this
  research.

---

## 5. Query and performance shape

Target query: "all progress for all learners in a cohort registration" (educator matrix, cohort PDF
report), assuming option D's schema (progress → `UserCourseRegistration`, one row per member,
optionally `cohort_course_registration`-tagged):

```python
from django.db.models import Prefetch

registrations = (
    UserCourseRegistration.objects
    .filter(cohort_course_registration=cohort_registration, is_active=True)
    .select_related("user", "collection")
    .prefetch_related(
        Prefetch(
            "topic_progress",
            queryset=TopicProgress.objects.select_related("topic").only(
                "id", "registration_id", "topic_id", "complete_time"
            ),
        ),
        Prefetch(
            "form_progress",
            queryset=FormProgress.objects.select_related("form").only(
                "id", "registration_id", "form_id", "completed_time", "scores"
            ),
        ),
    )
)
```
This is 3 queries total for the whole cohort (registrations, topic progress, form progress) instead
of one pair per learner.

**Indexes.** Django auto-indexes every `ForeignKey` column, so `registration_id`,
`cohort_course_registration_id`, `topic_id`, and `form_id` already get plain btree indexes for free
— no extra `db_index=True` needed for the basic FK-equality lookups above. Two additions worth
making explicitly:
- `UniqueConstraint(fields=["registration", "topic"])` on `TopicProgress` (replaces
  `unique_together = ["user", "topic"]`) — this constraint's implied index is also exactly the index
  the matrix query needs to look up "this registration's progress on this topic," so no separate
  index is required beyond it.
- If the matrix/PDF report aggregates completion counts (`Count(..., filter=Q(complete_time__isnull=False))`)
  per registration at scale, consider `models.Index(fields=["registration", "complete_time"])` on
  `TopicProgress`/`FormProgress` to keep that aggregate an index-only scan rather than a full table
  scan per registration — a call for the implementer once the actual report query is written, not a
  hard requirement now.

**N+1 traps the new indirection introduces.** Before this change, "get all TopicProgress for user X
in course Y" was a single-hop `TopicProgress.objects.filter(user=X, topic__course=Y)`. After, it's
two-hop: resolve the *registration* first (which one — active? most recent?), then filter by
`registration`. The trap: any code that resolves "the registration for this learner" **inside a
per-learner loop** (e.g. `for member in cohort.members: reg =
UserCourseRegistration.objects.get(user=member, ...); progress =
reg.topic_progress.all()`) reintroduces exactly the N+1 pattern the single bulk query above avoids.
Every consumer that currently does `TopicProgress.objects.filter(user=..., topic=...)` in a loop
must be rewritten to bulk-fetch registrations first (the `Prefetch` shape above), not just have
`user=` swapped for `registration=` in place.

---

## 6. Denormalised `site` field

Every `SiteAwareModel` (including the new/changed progress and registration models) carries its own
`site` FK, and `SiteAwareManager.get_queryset()` (`site_aware_models/models.py:44-50`) filters
directly on that column: `queryset.filter(site=site)`. Once progress carries a `registration` FK,
`registration.site` is always derivable — `progress.site` becomes a **functionally redundant**
column (site is fully determined by `registration_id`).

Removing it is **not** recommended:

- `SiteAwareManager`'s auto-filter is a single generic implementation shared by every
  `SiteAwareModel` subclass in the codebase — it filters on `self.model`'s own `site` column
  uniformly. Making progress models the one exception (needing `filter(registration__site=site)`
  instead) means either forking the shared manager behaviour per-model or teaching the generic
  manager about per-model join paths — a real architecture change to a base class used everywhere,
  disproportionate to this feature and outside its stated scope.
- It would add a **mandatory join** to the single hottest, most-executed query path in the app
  (every automatically site-scoped queryset against a progress table, on every learner-facing and
  educator-facing view) purely to remove one small denormalised column. Keeping the column trades a
  few extra indexed bytes per row for avoiding that join on every request.
- Postgres `CHECK` constraints cannot reference other tables, so DB-level enforcement that
  `progress.site_id == progress.registration.site_id` isn't possible without a trigger (excluded by
  the ORM-only convention). Consistency instead falls out naturally: `SiteAwareModelBase.save()`
  independently resolves `site` from the same request thread-local on every model, so
  `progress.site` and `registration.site` will match as long as they're created within the same
  request (already true in practice). If stronger guarantees are wanted, add a `clean()` check
  mirroring the pattern already used in `CohortDeadline.clean()`/`StudentDeadline.clean()`:
  ```python
  def clean(self) -> None:
      super().clean()
      if self.registration_id and self.site_id != self.registration.site_id:
          raise ValidationError("Progress site must match its registration's site.")
  ```

**Recommendation: keep the denormalised `site` field on progress models unchanged.** Removing it is
a separate, larger, cross-cutting change to `SiteAwareModel`/`SiteAwareManager` itself and should
not be folded into this feature.

---

## Implications for FLS

- **Constraint design:** replace `UserCourseRegistration`'s hard `UniqueConstraint(site_id,
  collection, user)` with a partial unique index, `condition=Q(is_active=True)`, name
  `unique_active_user_course_registration` — enforces "at most one active registration" while
  allowing unlimited historical/inactive rows. Do **not** add an `attempt_number` to any DB-enforced
  key; derive display ordering from `registered_at` instead, avoiding the whole race-safe-allocation
  problem.
- **Enrolment-parent shape:** adopt option D — collapse cohort-derived access into ordinary
  `UserCourseRegistration` rows (one per member, tagged with a nullable
  `cohort_course_registration` provenance FK, auto-created/deactivated by a membership-sync service)
  — so every progress model gets a single, non-nullable, non-polymorphic `registration` FK. This
  avoids GFK's lost referential integrity and `select_related` gap, avoids MTI's permanent join tax
  and lack of FLS precedent, and avoids the two-nullable-FK branching cost everywhere progress is
  consumed. The sync-service cost this pushes onto the plan is the honest trade-off.
- **Migration sequence:** a small `RunPython` migration that wipes `QuestionAnswer` → `FormProgress`
  → `TopicProgress` → `CourseProgress` (via `apps.get_model`, `reverse_code=RunPython.noop`),
  immediately followed by non-nullable `AddField`s for the new `registration` FKs — no
  nullable-then-backfill dance is needed since there's nothing to preserve. Update
  `upgrade_notes.md` with `requires_migrations: true` and an explicit "this migration deletes all
  existing progress data, there is no data-preserving path" breaking-change note — the first of its
  kind in this repo's `upgrade_notes.md` history.

status: ok
