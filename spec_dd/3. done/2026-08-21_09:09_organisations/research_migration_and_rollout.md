# Research: migration and rollout for a mandatory school FK

## Executive summary

FLS is distributed as a git submodule into downstream ("concrete") Django projects that run their
own `migrate` against their own live PostgreSQL data (`docs/product/deployment.md:108-115`,
`docs/product/configuration-and-extension.md:77-93`). That means the School migration ships once,
in this repo, and is then applied unmodified against an unknown number of downstream databases of
unknown size and shape (verified fact — this is FLS's whole distribution model).

The repo already has working precedent for every piece of this problem individually:
a per-site backfill loop (`freedom_ls/content_engine/migrations/0009_backfill_course_accent_slot.py`),
raw-SQL multi-table backfills (`freedom_ls/student_management/migrations/0008_populate_user_from_student.py`),
constraint replace-in-migration sequencing (`freedom_ls/student_management/migrations/0009_remove_student_fk_make_user_non_nullable.py`),
a `Site.objects.get_or_create` pattern for bootstrapping site-scoped rows outside a request
(`freedom_ls/site_aware_models/management/commands/create_site.py:16-19`), and a structured
`upgrade_notes.md` convention that already has a `requires_migrations` flag and a breaking-changes
section built for exactly this kind of change
(`claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-46`). There is, however, **no existing
precedent in this repo for a mandatory FK addition on a populated, site-aware table with a per-site
derived default** — the closest (`0009_remove_student_fk_make_user_non_nullable`) makes an
*already-nullable* field non-nullable after a same-migration-set backfill, not a brand-new FK.

External research confirms the standard three-migration dance (nullable → backfill → not-null) is
still the right shape in Django + PostgreSQL 17, and that PostgreSQL 12+'s `NOT VALID` CHECK
constraint trick lets the final `SET NOT NULL` skip the full-table scan that would otherwise hold an
`ACCESS EXCLUSIVE` lock for the scan's duration. Given FLS's own stated scale (~1,000–10,000
students per install, single-VPS Postgres — `docs/product/deployment.md:79-81`), the lock durations
involved are very likely sub-second even without the optimisation, but the optimisation costs
nothing extra to apply and removes the risk for any downstream that is larger than FLS's own
reference numbers.

The sharpest hazard is not locking — it's **constraint correctness**: `Cohort`'s
`unique_cohort_name_per_site` constraint and three other uniqueness constraints in
`freedom_ls/student_management/models.py` change meaning once `school` exists, and the migration
that adds/removes them can fail outright on a downstream database that already has duplicate rows
under the new, narrower constraint scope — the same failure mode the existing
`0006_validate_no_duplicate_students.py` migration was written to catch pre-emptively for a
different field. That validate-before-constrain pattern should be reused here.

Flagged as **inference** throughout are: exact downstream table sizes (unknown — no telemetry
exists), and the "no ordering guarantee that `django.contrib.sites`' default Site row exists before
another app's data migration runs" claim, which is well-documented externally but not something I
could verify by running code in this environment.

---

## Part A — what this repo already does

### Install / upgrade documentation

- `docs/install.md` **exists but is empty** (verified — `Read` returned "the file exists but the
  contents are empty"). There is no working `install.md` to read for upgrade mechanics.
- `docs/product/configuration-and-extension.md:77-93` documents the extension model instead: FLS is
  installed as a git submodule into a host Django project; the host keeps app-priority,
  template-priority, and content-widget-registration override points. Nothing there is
  migration-specific.
- `docs/product/deployment.md:108-115` ("Deploying a Concrete Project") confirms: "FLS is never
  deployed standalone... installs `freedom_ls` as a git submodule and supplies its own settings,
  content, and deployment scaffolding" — i.e. the downstream project's own `manage.py migrate` run
  is what actually applies any migration this feature ships. FLS has no control over when that
  happens, what data is already in the table, or what size the table is.
- `docs/product/deployment.md:73-83` gives the only sizing signal available: Phase 1 (single VPS)
  is estimated at "~50–200 concurrent users, ~1,000 registered students," Phase 2 "~5,000–10,000
  students," explicitly **not load-tested**. `Cohort`, `UserCourseRegistration`, and
  `CohortCourseRegistration` row counts scale with registrations, not raw student count, but are
  very unlikely to be enormous (tens of thousands, not millions) for any current or near-term FLS
  install. This is directly relevant to Part B's lock-duration discussion: for tables at this
  scale, even an unoptimised `ACCESS EXCLUSIVE` `SET NOT NULL` scan is very likely sub-second — the
  PG12+ optimisation described below is cheap insurance, not a hard requirement, at FLS's current
  scale, but should still be used since it costs nothing.
- `docs/product/configuration-and-extension.md:87-102` (Conformance Suite) confirms one relevant
  downstream-facing safety net already exists: "The database schema and the code's data model are
  in step, with no model change left un-migrated" (line 100) is one of the things the opt-in
  conformance suite checks for a downstream project. This does **not** check that a migration is
  *safe to run*, only that model state and migration state agree — it would not catch a duplicate-row
  constraint failure at migrate time.

### The `upgrade_notes.md` convention

`claude_plugins/fls-dev/commands/update_upgrade_notes.md` is the skill/command that authors
`upgrade_notes.md` for downstream projects. Verified structure (lines 14-46):

```yaml
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
```
followed by a `# Upgrade notes: <spec-name>` markdown body with `## Breaking changes` and
`## Manual steps` sections. `requires_migrations` (line 39) is defined only as "the feature adds or
alters models; downstream must run `migrate`" — it is a boolean flag with **no dedicated field for
migration risk, expected downtime, or pre-migration data checks**. Real precedent for how
migration-risk prose is actually written when it matters exists in
`spec_dd/3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/upgrade_notes.md:30-33`,
which under "Breaking changes" warns: "New unique constraint on `WebhookDelivery(event, endpoint)`.
The constraint migration... fails to apply if your database already holds historical rows that
duplicate `(event, endpoint)`. Fresh/dev databases are fine; a live database with duplicates needs a
one-off dedupe **before** running the migration." This is exactly the shape of warning the School
migration's `upgrade_notes.md` needs to reuse for the `unique_cohort_name_per_site` constraint
change (see Part C).

The command's own rules (`claude_plugins/fls-dev/commands/update_upgrade_notes.md:88-95`): "Facts
only. Base every statement on the spec, the plan, and the actual diff. Do not speculate," and list
concrete manual steps such as "run `manage.py migrate`." Nothing in the skill currently prompts the
author to mention expected lock duration or table-size thresholds — that has to be added by hand,
following the `WebhookDelivery` precedent above.

### Precedent data migrations that backfill a new/changed required field

Four `RunPython` data migrations exist in the whole repo (per the existing internal research at
`spec_dd/2. in progress/more-testing-skills/research_testing_migrations.md:210-239`, itself a
good source to reuse rather than re-derive):

1. **`freedom_ls/content_engine/migrations/0009_backfill_course_accent_slot.py:8-16`** — the closest
   precedent to "backfill a value derived per Site." Loops `site_id` values and assigns
   `accent_slot` per site via `apps.get_model(...)` + per-row `.save(update_fields=[...])`. Correct
   `apps.get_model` usage, but line 5 (`from freedom_ls.content_engine.course_accent import
   PALETTE`) imports **live app code** into a migration — a documented anti-pattern (see Part B) —
   because if `PALETTE`'s length changes later, replaying this migration from scratch computes
   different values than production originally got. `reverse_code=migrations.RunPython.noop`
   (line 26) — a deliberate no-op reverse since there's no meaningful inverse for a slot assignment.
2. **`freedom_ls/student_management/migrations/0008_populate_user_from_student.py:6-17`** —
   backfills `user_id` on three tables via raw `schema_editor.execute(f"UPDATE ... FROM ...")` SQL
   rather than the ORM, with hardcoded table names (`# nosec B608` comments because bandit flags
   f-string SQL even though the interpolated values are fixed literals, not user input). Has a
   working, symmetric `reverse()` (lines 19-27) that nulls the column back out.
3. **`freedom_ls/student_management/migrations/0006_validate_no_duplicate_students.py:6-19`** — a
   **validation-only** data migration: raises an exception during migrate if any `user_id` has more
   than one `Student` row, *before* a later migration tries to rely on that uniqueness. This is the
   direct precedent for the constraint-hazard problem described below: FLS has already needed, once
   before, to fail a migration loudly on a downstream database with data that violates an
   about-to-be-enforced invariant, rather than let a silent constraint-creation failure happen.
4. **`freedom_ls/content_engine/migrations/0003_rename_collection_contentcollectionitem_collection_old_and_more.py:10-12,88`**
   — mixed schema+data migration; uses `apps.get_model` correctly for three historical models and
   has a real, working `reverse_migration` (not a noop), migrating a FK-shaped relationship into a
   GenericForeignKey and back.

### Constraint sequencing precedent

**`freedom_ls/student_management/migrations/0009_remove_student_fk_make_user_non_nullable.py:33-55`**
is the direct precedent for "how FLS restructures a `UniqueConstraint` whose field set changes":
it issues `migrations.RemoveConstraint` for the old constraint **before** `RemoveField`/`AlterField`
touch the underlying columns, then issues `migrations.AddConstraint` for the new constraint
**after** the field change. This ordering (remove old constraint → change fields → add new
constraint) is the pattern the School rollout should reuse for every constraint below, in a
migration set that follows *after* the school column already exists and is backfilled (never in the
same migration as the backfill itself, and never touching the constraint before the column that
constraint will reference is populated).

Note this precedent is a **same-repo-history, single-deploy** change — it does not by itself
demonstrate what to do when the *new* constraint can fail against a live downstream database with
duplicate rows (that risk didn't exist here because `user_id` had just been populated 1:1 from
`student.user_id`, which was already unique per `0006`). The School case is different: a downstream
operator could have two `Cohort` rows already named `"Cohort A"` on the same site that are about to
become two different Schools' cohorts — those are *fine* under a `(site_id, school_id, name)`
constraint, but a downstream operator could equally have relied on the site-level name being
globally unique within the site for some external integration; that's a data-shape assumption this
research cannot verify from the codebase and should be called out to the idea author.

### `CLAUDE.md` migration conventions

Verified from the project's own `CLAUDE.md` (already known to me, restated for the citation record):
"Always run `uv run manage.py makemigrations` after model changes, then `uv run manage.py migrate`"
and "Never edit existing migration files — create new migrations instead." Both are directly
relevant: the three-step dance below must be three (or more) *separate, sequentially-numbered*
migration files, never hand-edited after being merged, and any correction to an already-shipped
step must itself be a new migration.

### Every constraint in `freedom_ls/student_management/models.py` a `school` FK touches

Enumerated from `freedom_ls/student_management/models.py`:

| Model | Constraint | Location | School changes its meaning? | Migration hazard |
|---|---|---|---|---|
| `Cohort` | `unique_cohort_name_per_site` on `(site_id, name)` | `models.py:19-24` | **Yes** — the idea implies multiple Schools per Site, and a cohort belongs to one School, so the natural new scope is `(site_id, school_id, name)`. | **Real hazard.** If two existing cohorts on the same site already share a name (currently impossible — the existing constraint forbids it), no duplicate-row risk exists *today*. But once `school_id` exists, the useful invariant arguably becomes "unique per school," which is a **narrower** constraint than the current site-wide one, so widening the *set of allowed combinations* introduces no duplicate-row risk on migrate. The real hazard is the reverse: if the eventual product decision is "cohort names still must be unique per site regardless of school" (unclear from `idea.md`), then the constraint stays `(site_id, name)` and adding `school_id` to the model at all creates no constraint hazard — this needs an explicit product decision, not just a migration mechanics one (see Part C). |
| `CohortMembership` | `unique_user_cohort_membership` on `(user, cohort)` | `models.py:34-40` | No — a membership's school is implied transitively via `cohort.school`; this constraint doesn't need `school_id` added to it. | None from School directly. |
| `UserCourseRegistration` | `unique_user_course_registration` on `(site_id, collection, user)` | `models.py:58-64` | **Yes** — the idea says "course registrations of any kind have school" (`idea.md:6`). If a user can be registered for the same course through two different Schools on the same Site simultaneously (e.g. a multi-school deployment where a learner belongs to two schools offering the same course), the constraint must become `(site_id, school_id, collection, user)` — a **narrowing**, so no duplicate-row risk on migrate, but changes what future double-registration attempts are rejected vs accepted. If a user must never be double-registered for a course *regardless* of school, the constraint stays as-is and `school_id` is just an extra column. Needs the same explicit product decision as `Cohort`. | Narrowing is migration-safe (existing rows can't already violate a wider constraint by becoming eligible under a narrower one — the reverse, widening, is where duplicate-row failures happen). No hazard if narrowing; a product-decision blocker either way. |
| `CohortCourseRegistration` | `unique_cohort_course_registration` on `(site_id, collection, cohort)` | `models.py:114-120` | No direct change needed — a cohort already belongs to (at most) one school transitively via the FK the idea proposes, so a `(cohort, collection)` pair is already school-scoped through `cohort_id`. Adding `school_id` directly to this constraint would be redundant, not incorrect. | None from School directly, unless the idea author wants `school_id` added here too for query/index reasons rather than correctness reasons — a decision, not a hazard. |
| `CohortDeadline` | `unique_cohort_deadline_per_item` on `(cohort_course_registration, content_type, object_id)`, conditional | `models.py:145-152` | No — scoped through `cohort_course_registration`, which is transitively school-scoped via its `cohort`. | None. |
| `StudentDeadline` | `unique_student_deadline_per_item` on `(student_course_registration, content_type, object_id)`, conditional | `models.py:192-199` | No — same reasoning, transitively scoped via `student_course_registration` (i.e. `UserCourseRegistration`). | None. |
| `UserCohortDeadlineOverride` | `unique_user_cohort_override_per_item` on `(cohort_course_registration, user, content_type, object_id)`, conditional | `models.py:240-252` | No — transitively scoped. | None. |
| `RecommendedCourse` | no `UniqueConstraint`, only `ordering`/`verbose_name_plural` | `models.py:305-310` | Not in scope — `idea.md` doesn't mention `RecommendedCourse` needing `school`; flagging only because it's a `SiteAwareModel` sibling in the same file with a `collection` FK, in case the idea author intends recommendations to be school-scoped too. | N/A unless scope is extended. |

**Bottom line for Part A:** the two constraints that genuinely need a product decision (not just a
migration-mechanics decision) are `unique_cohort_name_per_site` and
`unique_user_course_registration`. Both changes, if made, are *narrowing* the set of rows the unique
constraint permits (adding a column to the constraint key), which is migration-safe by construction —
existing rows can't retroactively violate a narrower key. The dangerous direction (existing
duplicate rows blocking a new, *narrower-in-a-different-dimension* constraint) doesn't arise here
because no existing rows are being merged or reinterpreted; they're being partitioned by an
additional key that was previously implicit (one default School per Site). This is a meaningfully
different, safer situation than the `WebhookDelivery` precedent
(`spec_dd/.../support-concrete-project-deployment-3-background-tasks/upgrade_notes.md:30-33`), where
a *new* constraint on *existing, non-partitioned* data could genuinely already be violated — worth
saying explicitly in the upgrade note so downstream operators aren't scared by a false analogy to
that warning.

---

## Part B — external research

### 1. The canonical safe pattern: nullable → backfill → not-null

Verified via Django/PostgreSQL sources: adding a `NOT NULL` foreign key to a populated table in one
step fails outright in Django/Postgres because existing rows have no value to satisfy the
constraint. The standard three-step pattern:

1. **Add the column nullable** (`AddField(..., null=True)`), no default requiring backfill logic.
2. **Data migration** to backfill every existing row with a computed value (`RunPython`, using
   `apps.get_model`, never the real imported model — see §3).
3. **Alter the field to non-nullable** (`AlterField(..., null=False)`) once step 2 is confirmed
   complete for every row.
   ([jaketrent.com — nullable FK migration walkthrough](https://jaketrent.com/post/add-migration-nonnull-foreignkey-field-django/),
   [coderbook.com — same pattern](https://coderbook.com/@marcus/add-new-non-null-foreign-key-to-existing-django-model/),
   [PostHog engineering handbook — Safe Django Migrations](https://posthog.com/handbook/engineering/safe-django-migrations))

**Locking specifics (verified via PostgreSQL docs and reputable write-ups):**

- `ALTER TABLE ... ALTER COLUMN ... SET NOT NULL` normally triggers a full table scan to verify no
  existing row is `NULL`, and this scan runs while holding an **`ACCESS EXCLUSIVE`** lock — the
  strongest PostgreSQL lock, which blocks *all* access to the table, including plain `SELECT`, for
  its entire duration. Duration scales with table size.
  ([dev.to/andrewpsy — "The SET NOT NULL downtime trap"](https://dev.to/andrewpsy/the-set-not-null-downtime-trap-in-postgresql-1o71))
- **PostgreSQL 12+ optimisation** (verified via PostgreSQL's own `ALTER TABLE` documentation and the
  write-up above): if a `NOT VALID` `CHECK (col IS NOT NULL)` constraint is added first and then
  separately validated, `SET NOT NULL` can skip its own table scan because Postgres can already
  prove the invariant from the validated constraint. The three-statement pattern:
  ```sql
  ALTER TABLE cohort ADD CONSTRAINT school_not_null_chk CHECK (school_id IS NOT NULL) NOT VALID;  -- instant, ACCESS EXCLUSIVE but no scan
  ALTER TABLE cohort VALIDATE CONSTRAINT school_not_null_chk;                                      -- SHARE UPDATE EXCLUSIVE, scans but doesn't block writes/reads
  ALTER TABLE cohort ALTER COLUMN school_id SET NOT NULL;                                          -- fast, no scan, because the validated CHECK proves it
  ALTER TABLE cohort DROP CONSTRAINT school_not_null_chk;                                          -- constraint now redundant with the column-level NOT NULL
  ```
  **Critical warning from the same source:** these must be **separate statements/transactions** —
  combining `VALIDATE CONSTRAINT` and `SET NOT NULL` in one transaction, or dropping the CHECK
  constraint before/in the same statement as `SET NOT NULL`, causes Postgres to lose the proof and
  fall back to the full scan.
  ([dev.to/andrewpsy](https://dev.to/andrewpsy/the-set-not-null-downtime-trap-in-postgresql-1o71),
  [PostgreSQL 18 docs — ALTER TABLE, "Adding a Column"](https://www.postgresql.org/docs/current/ddl-alter.html))
- **`ADD COLUMN ... REFERENCES`** (adding the FK constraint itself, not `SET NOT NULL`): adding a
  foreign-key constraint also normally requires validating existing rows and takes `ACCESS
  EXCLUSIVE` for that validation unless split into `ADD CONSTRAINT ... NOT VALID` +
  `VALIDATE CONSTRAINT` the same way. Since a **new** FK column with no rows referencing anything yet
  (it's `NULL` for all existing rows in step 1 above) has nothing to validate, this is only a
  practical concern for the constraint-adding step, not the column-adding step, in this specific
  rollout — the FK constraint on a nullable, all-`NULL` column validates instantly regardless.
- **`ADD COLUMN` with a non-volatile default** (PostgreSQL 11+, verified): adding a column with a
  constant, non-volatile default no longer rewrites every row — Postgres stores the default in
  `pg_attribute.attmissingval` and applies it lazily on read, making the `ALTER TABLE` itself
  effectively instant regardless of table size. This **does not directly apply** to this rollout,
  because the correct default (the Site's default School) varies per row by `site_id`, not a single
  constant — so `AddField(default=<single value>)` cannot be used for the real backfill; the column
  must be added nullable with no default, then backfilled per-site in a separate `RunPython`/SQL
  step (matching `0009_backfill_course_accent_slot.py`'s per-site loop precedent).
  ([depesz.com — "Fast ALTER TABLE ADD COLUMN with a non-NULL default"](https://www.depesz.com/2018/04/04/waiting-for-postgresql-11-fast-alter-table-add-column-with-a-non-null-default/),
  [brandur.org — "A Missing Link in Postgres 11"](https://brandur.org/postgres-default))

### 2. Zero-downtime considerations — do they apply here?

Given FLS's own stated scale (`docs/product/deployment.md:79-81`, Phase 1 ~1,000 students, Phase 2
~5,000–10,000), `Cohort`/`UserCourseRegistration`/`CohortCourseRegistration` row counts are very
unlikely to be large enough (tens of thousands of rows at most for a large Phase-2 install) for an
unoptimised `SET NOT NULL` full scan to take more than low-single-digit seconds — this is
**inference**, not measured, since no FLS install has been load-tested
(`docs/product/deployment.md:75`). A brief (sub-second to low-seconds) `ACCESS EXCLUSIVE` lock
during a scheduled migrate is very likely acceptable for FLS's actual deployment shape: single VPS,
Gunicorn behind Caddy, no documented zero-downtime/blue-green deploy mechanism exists yet
(`docs/product/deployment.md:31-39` — provisioning/deploy automation is explicitly "not yet built").
Since FLS has no rolling-deploy story at all currently, a brief full-table lock during a downtime
migration window is consistent with how FLS deployments already work, not a new constraint the
rollout introduces.

That said, because FLS is a **package distributed to unknown downstream installs** — some of which
could be larger than FLS's own reference numbers, or running the migration at a busier time than
ideal — using the PG12+ `NOT VALID` + `VALIDATE CONSTRAINT` trick from §1 costs nothing and removes
the tail risk entirely. The upgrade note should tell operators: expect the migration to run in
seconds even on their largest tables (cohorts/registrations, not full user data), recommend running
it during a maintenance window or low-traffic period as routine caution (not because it's expected
to be slow), and flag that if any table has grown into the hundreds of thousands of rows the
operator should test the migration against a production-sized copy first — a number worth stating
explicitly in the upgrade note as the threshold past which "just run it" advice stops being safe
enough to give blindly.

### 3. Data migrations in a reusable/distributable app

- **Historical models via `apps.get_model`** (verified, Django docs): historical models used inside
  `RunPython` "will not have any custom methods that you have defined... They will, however, have
  the same fields, relationships, managers (limited to those with `use_in_migrations = True`) and
  `Meta` options." Concretely for FLS: **`SiteAwareModelBase.save()`**
  (`freedom_ls/site_aware_models/models.py:61-63`) and its `_set_site_from_request()` helper
  (`freedom_ls/site_aware_models/models.py:69-76`) will **not** be present on the historical
  `School`/`Cohort`/etc. models obtained via `apps.get_model(...)` inside the migration. This is
  actually the *safe* outcome, not a hazard, for a migration that explicitly sets `school_id`/`site_id`
  on every row it creates or updates: the historical model's plain `save()` just writes the columns
  given to it. The **real** hazard is the opposite mistake: if a future contributor imports the real
  `School`/`Cohort` model into a migration (`from freedom_ls.student_management.models import
  Cohort`) instead of using `apps.get_model`, that real model's `save()` **would** run
  `_set_site_from_request()`, which reads `_thread_locals.request` — a thread-local that is never
  populated during `manage.py migrate` (no request exists). Since `_set_site_from_request` only
  assigns `self.site` when `self.site_id` is falsy (`models.py:71`), a migration that always passes
  an explicit `site_id`/`school_id` would still work by accident even with the real model imported —
  but this is exactly the kind of accidental safety net that breaks the moment someone forgets to
  set `site_id` explicitly, so the rule stands regardless: **always use `apps.get_model`, never the
  real import**, matching the "do this" example already in the repo at
  `freedom_ls/content_engine/migrations/0003_....py:10-12` and the "don't do this" counter-example
  already flagged in `spec_dd/2. in progress/more-testing-skills/research_testing_migrations.md:230-237`
  (the `PALETTE` live import in `0009_backfill_course_accent_slot.py:5`).
  ([Django 6.0 docs — "Data Migrations" / "Historical models"](https://docs.djangoproject.com/en/6.0/topics/migrations/))
- **`django.contrib.sites` ordering** (external, treated as **inference/unverified-in-this-repo**
  because I could not execute code to confirm it against Django 6's current source): the default
  `Site` row (`example.com`, `pk=SITE_ID`) is created by a `post_migrate` **signal handler** in
  `django.contrib.sites`, not by a data migration inside the `sites` app itself. Because
  `post_migrate` fires only after *all* apps' migrations have run, a School data migration that does
  `Site.objects.get(pk=1)` (or any other lookup assuming a Site row already exists) on a **fresh,
  from-scratch** database has no guarantee that row exists yet at the point the School migration
  runs. The documented mitigation is to iterate `Site.objects.all()` for whatever Sites *do* already
  exist rather than assuming any particular one does, and to be defensive about the zero-Sites case
  on a from-scratch install (in which case there is nothing to backfill yet — the School creation
  should instead happen lazily, e.g. via `create_site.py`-style `get_or_create` the first time a
  Site is created, for any Sites created *after* this migration has already run). This matters more
  for FLS than for a typical single-tenant app, because FLS explicitly supports "many Sites" as a
  normal topology (`freedom_ls/site_aware_models/management/commands/create_site.py` exists
  specifically to create additional Sites on demand) — so a School-backfill migration cannot assume
  either "exactly one Site" or "all Sites that will ever exist already exist" at migrate time.
  ([aidenbell.me — "Django's Sites app initial data migration"](https://aidenbell.me/django-sites-data-migration/))
- **Consequence for FLS specifically:** the School-backfill migration should query
  `Site.objects.all()` (via `apps.get_model("sites", "Site")`) for whatever Sites exist *at the time
  the migration runs*, create one default School per Site found, and backfill rows scoped to that
  Site — exactly mirroring the per-site loop already used in
  `0009_backfill_course_accent_slot.py:8-16`. Any Site created **after** this migration ships (via
  `create_site.py` or otherwise) will not automatically get a default School from this migration —
  that gap has to be closed by product decision, not migration mechanics (see Part C: either
  `create_site.py` is extended to also create a default School, or School creation becomes a
  required manual step documented for operators who add Sites later).

### 4. Idempotency and re-runnability

- Each of the three migration steps is a normal Django migration and is inherently idempotent in the
  sense Django migrations always are: once a migration is recorded as applied in `django_migrations`,
  Django will not re-run it. The genuine idempotency risk is narrower: **what if the backfill
  migration is re-run from scratch on a database that already has Schools** (e.g. a downstream
  project that manually created Schools before upgrading, or a partially-applied migrate that was
  interrupted and retried). Recommended pattern, following the existing `Site.objects.get_or_create`
  precedent in `freedom_ls/site_aware_models/management/commands/create_site.py:16-19`: the backfill
  should `School.objects.get_or_create(site=site, name=<default-name>, defaults={...})` rather than
  unconditionally `.create(...)`, so re-running the forward function (e.g. after a failed partial
  apply gets retried, which Django will do if the transaction rolled back and the migration wasn't
  recorded as applied) does not create duplicate default Schools. Row-level backfill (`UPDATE ...
  WHERE school_id IS NULL`) is naturally idempotent — re-running it only touches rows still `NULL`.
- **Downstream that already created its own Schools before upgrading:** not possible under this
  specific rollout, since `School` is a brand-new model this migration also creates — no downstream
  project can have `School` rows before this migration's `CreateModel` step runs for the first time.
  This scenario *would* matter if a future FLS version adds a second, different default-creation
  mechanism (e.g. a management command) that could race with the migration — out of scope for this
  research but worth a one-line note in Part C's testing guarantee.

### 5. Rollback

- A reverse migration for `CreateModel` (the School model itself) is trivially generated by Django
  (`DeleteModel`) and safe as long as nothing has come to depend on School rows existing by the time
  a rollback would run.
- A reverse migration for the **backfill** step genuinely cannot "undo" in any meaningful sense —
  there is no prior state to restore to, since `school_id` did not exist before this feature. Per
  the internal research's own guidance
  (`spec_dd/2. in progress/more-testing-skills/research_testing_migrations.md:159-164`, restating
  Django's own docs), the correct `reverse_code` here is `migrations.RunPython.noop` — this keeps
  the migration **graph**-reversible (so `migrate student_management <earlier>` doesn't hard-fail)
  without pretending there's a meaningful "put the data back" operation, exactly mirroring
  `0009_backfill_course_accent_slot.py:26`'s existing use of the same idiom for the same reason
  (an assigned value with no prior value to restore).
- The **`AlterField(null=False)`** step's own auto-reverse (`AlterField(null=True)`) is safe and
  automatic — Django schema migrations are reversible by construction unless hand-written SQL says
  otherwise.
- **What reverse cannot do:** un-delete Schools once downstream code has started writing
  `school_id` on new rows created after the forward migration ran but before any rollback — a
  rollback that runs `RemoveField`/`DeleteModel` will destroy that FK data with no way back short of
  a database restore. This should be stated plainly in the upgrade note's manual-steps section: this
  migration is **not intended to be rolled back after go-live**; rollback is only realistically safe
  in the window before any new registrations/cohorts have been created referencing a School.

### 6. django-guardian interaction

FLS uses `django-guardian>=3.3.0` (`pyproject.toml:12`) as the object-permission enforcement layer
underneath its own `role_based_permissions` app
(`freedom_ls/role_based_permissions/README.md:1-15`). Two separate questions:

- **Does adding `School` as a new model require a migration for guardian/permission machinery?**
  No new migration is needed purely to make `School` permission-checkable: Django's own
  `post_migrate` signal (via `django.contrib.auth`) automatically creates the standard `add_`/
  `change_`/`delete_`/`view_school` `Permission` rows for any new model the moment `migrate`
  finishes, with no migration file required for that part — this is stock Django behaviour, not
  something FLS or guardian has to do. django-guardian's own permission rows
  (`UserObjectPermission`/`GroupObjectPermission`) come from its own already-shipped migrations
  (external dependency, no new migration needed in FLS for guardian's own tables). ([django-guardian
  docs — Object Permissions](https://django-guardian.readthedocs.io/en/stable/userguide/assign/))
- **Does making `School` an object-permission target require a sync step?** Yes, but it's a
  **management command run after migrate, not a migration itself** — FLS already has exactly this
  mechanism: `freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py`. Its
  `_ensure_permissions_exist` (lines 59-94) creates any `Permission` rows referenced by role configs
  but not yet present, and `_sync_object_assignments`/`_sync_site_assignments`
  (lines 97-161) resync guardian permissions from `ObjectRoleAssignment`/`SiteRoleAssignment` rows.
  If the idea author later wants roles like "school admin" scoped to a School object (not specified
  in `idea.md`, which only mentions School for cohorts/registrations/branding — no explicit
  School-scoped role is described), that would mean: (a) adding new permission strings to
  `freedom_ls/role_based_permissions/registry.py` (verified pattern from the README,
  `role_based_permissions/README.md:128-141`), (b) adding a role in `roles.py` or a site's custom
  role module, and (c) running `sync_role_permissions` post-deploy — **not** a data migration. This
  is out of scope for the current `idea.md`, which does not mention School-level roles, but worth
  flagging to the idea author as a natural follow-up decision (see Part C).

### 7. Testing a data migration in pytest-django

The repo already has a dedicated internal research document on exactly this,
`spec_dd/2. in progress/more-testing-skills/research_testing_migrations.md`, which this research
defers to rather than re-deriving. Key points restated for this file's self-containedness:

- **`django_test_migrations` (`Migrator`/`migrator` fixture)** is the recommended third-party
  library approach: `migrator.apply_initial_migration(("app_label", "migration_before"))` builds the
  DB to the pre-change state (seed test rows against the historical model there),
  `migrator.apply_tested_migration(("app_label", "migration_under_test"))` runs the migration and
  returns the new historical state for assertions, `migrator.reset()` restores the DB to head
  afterwards. ([GitHub —
  wemake-services/django-test-migrations](https://github.com/wemake-services/django-test-migrations))
- The internal research (`research_testing_migrations.md:280-285`) explicitly recommends **not**
  adding this as a dependency yet, given only 4 `RunPython` migrations exist project-wide, and
  instead hand-rolling a small `MigrationExecutor`-based `TransactionTestCase` helper
  (`research_testing_migrations.md:53-93`). **This research's recommendation for the School rollout
  specifically diverges slightly**: the School backfill is exactly the kind of migration the
  existing research calls out as having "real behavioural risk (backfills, ... migrations that must
  survive partially-applied production data)" (`research_testing_migrations.md:91-93`) that
  justifies a dedicated test — whether via the hand-rolled `MigrationExecutor` pattern or by finally
  adding `django-test-migrations` is a call for whoever implements this spec, not something this
  research needs to force; either satisfies the minimum guarantee in Part C.
- **Concrete minimum test**, adapting the pattern already demonstrated for
  `0009_backfill_course_accent_slot` in the internal research
  (`research_testing_migrations.md:311-314`): seed ≥2 `Site` rows and ≥2 `Cohort`/registration rows
  per site via `apps.get_model` against the pre-migration historical state, run the migration
  forward, and assert (a) exactly one default `School` exists per `Site`, (b) every pre-existing
  `Cohort`/`UserCourseRegistration`/`CohortCourseRegistration` row now has `school_id` set to its
  site's default School, and (c) rows from different sites are not cross-assigned to the wrong
  site's School (multi-tenant isolation, per the same pitfall the internal research already flags at
  `research_testing_migrations.md:315-318`).

---

## Part C — recommendation

### Recommended rollout for FLS

Ordered as separate, sequentially-numbered migrations per app (never combined, never hand-edited
after merge, per `CLAUDE.md`'s migration conventions). Names below are illustrative — the real
numbers depend on migration state at implementation time.

1. **`freedom_ls_schools/0001_initial`** (new app, or wherever `School` is decided to live) —
   `CreateModel` for `School` as a `SiteAwareModel` (name, logo, `site` FK inherited from
   `SiteAwareModel`). No hazard: brand-new table, no backfill needed for the model's own creation.

2. **`freedom_ls_student_management/000X_cohort_add_school_nullable`** — `AddField("cohort",
   "school", models.ForeignKey(to="freedom_ls_schools.School", null=True, on_delete=models.PROTECT))`,
   and the equivalent `AddField` for `UserCourseRegistration` and `CohortCourseRegistration` (and any
   other model `idea.md` scopes in). Nullable, no default. Fast on any table size (new nullable
   column, no rewrite needed at this scale; PG11+'s non-volatile-default fast path doesn't even
   apply here since there's no default at all).

3. **`freedom_ls_student_management/000X_backfill_default_school`** — a `RunPython` data migration,
   modelled directly on `0009_backfill_course_accent_slot.py`'s per-site loop:
   - Uses `apps.get_model` for `Site`, `School`, `Cohort`, `UserCourseRegistration`,
     `CohortCourseRegistration` — never a real import (Part B §3).
   - Iterates `Site.objects.all()` (not a hardcoded `SITE_ID`), and for each Site,
     `School.objects.get_or_create(site=site, name=<default-name-rule>, defaults={...})` (idempotent
     per Part B §4, mirroring `create_site.py:16-19`'s `get_or_create` pattern).
   - Bulk-updates (`UPDATE ... WHERE site_id = %s AND school_id IS NULL`, following
     `0008_populate_user_from_student.py`'s raw-SQL precedent, or a chunked `.update(school=...)`
     per site if ORM-level is preferred) every existing `Cohort`/`UserCourseRegistration`/
     `CohortCourseRegistration` row for that Site to point at that Site's default School.
   - `reverse_code=migrations.RunPython.noop` (Part B §5 — there is no meaningful inverse).
   - Consider `atomic = False` on this migration class if any downstream table could plausibly be
     large enough that holding one long transaction open for the whole per-site loop is
     undesirable (Part B §1's transaction-scoping point) — at FLS's current documented scale this
     is precautionary, not required.

4. **`freedom_ls_student_management/000X_validate_school_backfilled`** *(optional but recommended,
   mirroring `0006_validate_no_duplicate_students.py`'s pattern)* — a small validation-only
   `RunPython` that raises loudly if any row still has `school_id IS NULL` after step 3, before step
   5 tries to enforce it as a hard constraint. This turns a possible confusing `IntegrityError` deep
   in Postgres into a clear, FLS-authored error message if step 3's assumptions were ever violated
   (e.g. a Site with zero rows to backfill but somehow a row got inserted between steps — belt and
   braces, cheap to include).

5. **`freedom_ls_student_management/000X_cohort_school_not_null`** — the not-null enforcement, using
   the PG12+-safe sequence from Part B §1 (`NOT VALID` CHECK → `VALIDATE CONSTRAINT` →
   `SET NOT NULL` → `DROP CONSTRAINT`) via `migrations.RunSQL` (or `AlterField(null=False)` if the
   project decides FLS's own scale doesn't warrant the extra ceremony — flagged as a call for the
   implementer, not a hard requirement, given the honest scale numbers in Part B §2).

6. **`freedom_ls_student_management/000X_constraint_changes`** — **only if** the idea author decides
   `unique_cohort_name_per_site` and/or `unique_user_course_registration` should be narrowed to
   include `school_id` (Part A's flagged product decision). Follow the exact
   `RemoveConstraint` → (field changes already done above) → `AddConstraint` sequencing already
   proven in `0009_remove_student_fk_make_user_non_nullable.py:33-55`. As established in Part A,
   narrowing a unique constraint by adding a column cannot fail against existing data (no row can
   retroactively violate a constraint that only gets *more* permissive), so this step carries no
   duplicate-row migration hazard **regardless of** which way the product decision goes — the
   product decision affects correctness of future behaviour, not migration safety.

### Constraint changes and hazards (summary)

| Constraint | Change | Migration hazard |
|---|---|---|
| `unique_cohort_name_per_site` (`models.py:19-24`) | Possibly `(site_id, name)` → `(site_id, school_id, name)` | None on migrate (narrowing). **Product decision required**: does cohort-name uniqueness stay site-wide or become per-school? |
| `unique_user_course_registration` (`models.py:58-64`) | Possibly `(site_id, collection, user)` → `(site_id, school_id, collection, user)` | None on migrate (narrowing). **Product decision required**: can a user be registered for the same course via two different Schools on one Site? |
| `unique_cohort_course_registration`, `unique_cohort_deadline_per_item`, `unique_student_deadline_per_item`, `unique_user_cohort_override_per_item` | No change needed — school-scoping is already implied transitively through the FK chain | None |
| `unique_user_cohort_membership` | No change needed | None |

### What the upgrade note must warn downstream operators about

Following the `WebhookDelivery` precedent
(`spec_dd/.../support-concrete-project-deployment-3-background-tasks/upgrade_notes.md:24-33`) and the
`update_upgrade_notes.md` schema (`claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-46`),
the finished `upgrade_notes.md` should set `requires_migrations: true` and its **Breaking changes**
section must state, in plain prose:

- A new mandatory `school` field is added to `Cohort`, `UserCourseRegistration`, and
  `CohortCourseRegistration` (name the exact models the implementation actually touches). Every
  existing row is automatically assigned to a default School created per Site — **no manual data
  entry is required**, but operators should know a School now exists per Site and rename/re-logo it
  if the auto-generated default name/branding isn't what they want live-facing (this depends on
  Part C's naming-rule decision below).
- If (and only if) the constraint-narrowing decision in step 6 is taken: state explicitly that
  `unique_cohort_name_per_site` and/or `unique_user_course_registration` are changing scope, and —
  unlike the `WebhookDelivery` precedent — reassure operators this narrowing **cannot fail against
  existing data** (no pre-migration dedupe step is required), which is the opposite of that
  precedent's warning and should say so explicitly to avoid operators assuming they need to check
  for duplicates first.
- Expect the migration to run in well under a few seconds on any FLS install at documented current
  scale (`docs/product/deployment.md:79-81`); running it during routine low-traffic maintenance is
  good practice, not because it's expected to be slow.
- **This migration should not be rolled back after go-live** once any new Cohort/registration rows
  referencing a School have been created (Part B §5) — rollback is only safe in the window
  immediately after upgrade, before new data has accumulated against the new FK.
- If a downstream project creates additional Sites via `create_site.py` (or otherwise) **after**
  upgrading, note whether that command has been extended to also create a default School for the new
  Site, or whether that remains a manual step — this is an implementation decision this research
  cannot make for the idea author (Part B §3's "Site created after this migration ships" gap).

### Minimum test guarantee

At minimum (Part B §7): one migration-level test (hand-rolled `MigrationExecutor`/
`TransactionTestCase`, or `django-test-migrations`' `Migrator` — either satisfies this) that seeds
≥2 Sites with ≥2 pre-existing Cohort/registration rows each against the pre-migration historical
state, runs the backfill migration forward, and asserts: (a) exactly one default School per Site,
(b) every pre-existing row now has the correct site-scoped `school_id`, (c) no cross-site
contamination. This directly follows the pattern already recommended (but not yet implemented) for
`0009_backfill_course_accent_slot` in `research_testing_migrations.md:311-314`, extended to a second
model family.

### Naming rule for the auto-created default School — flagged as a decision for the idea author

`idea.md` does not specify this at all — it only says "A school has a name and a logo" (`idea.md:5`)
with no default-naming guidance. Two reasonable options observed from repo conventions elsewhere:

- **Name it after the Site**: e.g. `site.name` verbatim, or `f"{site.name} — Default School"`. This
  is the more discoverable option for an operator looking at the admin — it's immediately obvious
  which Site a School belongs to, and mirrors how `create_site.py` already treats `site.name` as the
  human-facing identity (`create_site.py:16-19` uses `site_name` as the primary lookup key, not
  `domain`).
- **A generic literal, e.g. `"Default School"`**: simpler, but on a multi-site install with several
  Sites this produces several identically-named Schools distinguishable only by `site_id`, which is
  worse for the operator working across sites in the admin.

This research recommends the Site-derived name (option 1) on the grounds above, but explicitly flags
it as **genuinely ambiguous and a product decision, not a migration-mechanics one** — the idea author
should confirm before implementation, since renaming a School after the fact is a trivial follow-up
edit but the choice affects what every downstream operator sees immediately post-upgrade without any
action on their part.

---

status: ok
