# Research: Testing Django migrations & data migrations

Scope: schema migrations, data migrations (`RunPython`), and migration hygiene/safety in CI, for
Python 3.13 / Django 6.x / PostgreSQL 17 / pytest + pytest-django, on a multi-tenant (Sites),
"never edit an existing migration" codebase.

---

## PART A — External best practices

### 1. The "missing migrations" guard

`python manage.py makemigrations --check --dry-run` exits non-zero if the current models don't
match the migration graph — i.e. someone changed a model and forgot to generate a migration.

- `--check`: don't write anything, just report whether migrations are missing (exit code 1 if so).
- `--dry-run`: needed together with `--check` on Django versions before 4.2.9 to guarantee no file
  is written even if `--check` is somehow bypassed; harmless to keep on newer Django too.
- Typical CI invocation:
  ```bash
  python manage.py makemigrations --check --dry-run --settings=myproj.settings.test
  ```
  A non-zero exit fails the build.
  ([Johnny Metz](https://johnnymetz.com/posts/check-django-migrations/),
  [dev.to/chris48s](https://dev.to/chris48s/failing-the-ci-build-if-django-migrations-are-out-of-date-16ei),
  [gist: missing-migrations command](https://gist.github.com/nealtodd/a8f87b0d95e73eb482c5))

- **Turning it into a test, not a separate CI step**: Adam Johnson describes writing this check as
  a plain test function that calls `call_command("makemigrations", "--check", "--dry-run", ...)`
  and asserts it doesn't raise `SystemExit`/return non-zero, so it runs wherever the test suite
  runs (locally, pre-commit, CI) rather than needing a bespoke pipeline step.
  ([Adam Johnson, "Test for pending migrations"](https://adamj.eu/tech/2024/06/23/django-test-pending-migrations/))

- A lower-level equivalent (used without touching a database or running `manage.py` as a
  subprocess) is to drive Django's own autodetector directly:
  ```python
  from django.apps import apps
  from django.db.migrations.autodetector import MigrationAutodetector
  from django.db.migrations.loader import MigrationLoader
  from django.db.migrations.state import ProjectState

  def test_no_missing_migrations():
      loader = MigrationLoader(None, ignore_no_migrations=True)  # None = no DB connection
      autodetector = MigrationAutodetector(
          loader.project_state(), ProjectState.from_apps(apps)
      )
      changes = autodetector.changes(graph=loader.graph)
      assert not changes, f"Models have drifted from migrations: {sorted(changes)}"
  ```
  This is exactly what `makemigrations --check` does internally, but as an importable, DB-less
  pytest test. This pattern already exists in FLS — see Part B.

### 2. Testing data migrations: `MigrationExecutor` mechanics

The canonical hand-rolled pattern (Caktus Group, Tom Carrick, and Django's own ticket history):

1. Subclass `django.test.TransactionTestCase` (not `TestCase`) — schema/data migrations run DDL
   and need to commit outside of the outer `TestCase` transaction wrapper; `TransactionTestCase`
   truncates tables between tests instead of relying on a rolled-back transaction.
2. Define `migrate_from` (the state *before* the migration under test) and `migrate_to` (the state
   *after* it) as `[(app_label, migration_name), ...]` tuples.
3. In `setUp`:
   ```python
   from django.db.migrations.executor import MigrationExecutor
   from django.db import connection

   executor = MigrationExecutor(connection)
   executor.migrate(self.migrate_from)          # roll DB schema back to "before"
   old_apps = executor.loader.project_state(self.migrate_from).apps

   # ... create rows using old_apps.get_model(app_label, ModelName), NOT the real import ...

   executor = MigrationExecutor(connection)      # loader state is stale, rebuild
   executor.migrate(self.migrate_to)             # run the migration under test forward

   new_apps = executor.loader.project_state(self.migrate_to).apps
   # ... assert against new_apps.get_model(...) ...
   ```
4. Because you migrate the *real* test database schema up and down, this exercises the actual SQL
   Django will run in production, not a mock.
   ([Caktus Group](https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/),
   [Tom Carrick](https://carrick.eu/blog/testing-django-data-migrations/),
   [gist: blueyed migration test base class](https://gist.github.com/blueyed/4fb0a807104551f103e6))

- **Gotcha**: data seeded by data migrations may not reappear between `TransactionTestCase`s
  because truncation removes it; Django's `serialized_rollback = True` reloads migration-created
  data per test but slows the suite — usually not worth it for a project that instead tests
  migrations directly rather than relying on migration-seeded fixtures.
  ([Django ticket #25251](https://code.djangoproject.com/ticket/25251),
  [Django ticket #28400](https://code.djangoproject.com/ticket/28400))
- Cost: `MigrationExecutor`-based tests are slow (they run real schema DDL) and verbose. Reserve
  them for migrations with real behavioural risk (backfills, irreversible transforms, migrations
  that must survive partially-applied production data) — not for every trivial `AddField`.

### 3. `django-test-migrations` library

A third-party package (`wemake-services/django-test-migrations`) that wraps the
`MigrationExecutor` dance above in an ergonomic API, plus a `--check`-style CLI and pytest plugin.

- **`Migrator`** (or its pytest fixture, typically `migrator_factory`/`migrator`): the core object.
  - `migrator.apply_initial_migration(("app_label", "migration_name"))` — migrates the DB to the
    state *just before* the change under test and returns the historical `ProjectState`; use
    `state.apps.get_model(...)` to create fixture rows against the *old* schema.
  - `migrator.apply_tested_migration(("app_label", "migration_name"))` — runs the migration(s) up
    to and including the one under test, returns the new `ProjectState` for assertions.
  - `migrator.reset()` — restores the DB to the latest migration state afterwards so later tests
    aren't left on a stale schema (call in a fixture finalizer / `addfinalizer`).
- **`MigratorTestCase`**: a `TestCase` subclass wrapper with `migrate_from` / `migrate_to` class
  attributes that does the apply/reset lifecycle automatically, closer to the hand-rolled pattern
  above but batteries-included.
- **Consistency / best-practice checks** it ships as pytest fixtures/plugins:
  - a "non-atomic" / ordering checker that fails if migrations in the same app are not applied in
    a linear, non-branching order (catches unintended merge-migration divergence),
  - a check that flags **irreversible** `RunPython` (missing `reverse_code`) so it's a conscious
    choice rather than an oversight,
  - `mute_migrations`: a decorator/context manager used inside a migration test to temporarily
    silence noisy "applying migration" console output while a test executor runs many migrations.
- **When it's worth adding as a dependency**: if the project accumulates enough data migrations
  that the boilerplate of building `MigrationExecutor` + tracking `migrate_from`/`migrate_to`
  pairs by hand becomes repetitive, or if the "flag irreversible RunPython" / ordering checks add
  value the team wants for free. If a project only occasionally writes a data migration (as is
  currently the case for FLS — 4 `RunPython` migrations, one of which is a validation-only no-op
  data migration), hand-rolling a single small test helper around `MigrationExecutor` costs little
  and avoids adding a new runtime dependency purely for test infrastructure.
  ([GitHub repo & README](https://github.com/wemake-services/django-test-migrations),
  [migrator.py source](https://github.com/wemake-services/django-test-migrations/blob/master/django_test_migrations/migrator.py),
  [PyPI](https://libraries.io/pypi/django-test-migrations))

### 4. pytest-django migration behaviour

- By default, pytest-django applies all migrations when it builds the test database — this is why
  a normal `pytest` run already exercises every migration's forward SQL (including data
  migrations) once per test-database build; a broken migration will fail the whole suite at
  collection/setup time, before any test runs.
- `--no-migrations` (alias `--nomigrations`): skips the migration graph entirely and creates
  tables by introspecting current model state (`syncdb`-style). Faster for large migration
  histories, but it means **data migrations never run** in that mode, and any bug that only
  manifests via running actual migrations (e.g. an irreversible/broken `RunPython`, a migration
  that depends on now-removed intermediate state) will not be caught. Don't combine
  `--no-migrations` with the migration tests described above — they need `apps.get_model` against
  real migration state.
- `--create-db`: forces the test DB to be rebuilt (re-running all migrations) instead of reusing a
  cached one; use after altering migrations or schema and when diagnosing a suspicious cached test
  DB.
- `django_db_setup` is the session-scoped fixture that actually builds/migrates the test database;
  its default implementation just honours the `--migrations`/`--no-migrations` and
  `--create-db`/`--reuse-db` CLI flags. Projects can override it (e.g. to load a custom fixture
  after migrating) but doing so bypasses the standard migrate-then-test flow, so overrides should
  still call through to migrate unless intentionally testing with `--no-migrations`.
  ([pytest-django docs — Database access](https://pytest-django.readthedocs.io/en/latest/database.html))

### 5. Reversibility & the historical-model rule

- Every `RunPython` should get a `reverse_code`. Options, in order of preference:
  1. A real inverse function (as FLS's `0008_populate_user_from_student` and
     `0003_rename_collection_...` migrations do).
  2. `migrations.RunPython.noop` when forward is a pure backfill with no meaningful inverse (as in
     FLS's `0009_backfill_course_accent_slot`) — this makes the migration reversible at the
     Django-graph level (so `migrate <app> <earlier>` doesn't hard-fail) even though the backfilled
     data isn't actually restored.
  3. `elidable=True` on `RunPython`/`RunSQL` ops (or the whole `Migration.operations` entry) marks
     an operation as safe to *squash away* — when Django squashes migrations, elidable operations
     are dropped from the squashed result. Useful for one-off backfills that only matter for
     databases migrating through that exact history and add no value once squashed.
- **Never import the current/"real" model inside a migration** (`from myapp.models import Foo`).
  Always use `apps.get_model("app_label", "ModelName")` inside the `RunPython` callable — this
  gives you the *historical* model as it existed at that point in the migration graph (correct
  fields, no fields added/removed later, no custom methods/managers that may not exist yet). The
  same rule applies inside a *test* for that migration: build/assert against
  `executor.loader.project_state(...).apps.get_model(...)` (or `Migrator`'s equivalent), not the
  real app's `models.py` import — otherwise the test silently exercises a schema that doesn't
  match what actually ran in production at that revision.
  ([Django docs pattern reiterated across the sources above], see also Caktus Group and Tom
  Carrick posts cited in §2.)

### 6. Pitfalls checklist (from the above sources, generalised)

- Importing the real model (or a helper module that imports the real model, or that could change
  shape/size over time — e.g. a constant list used to compute an index) inside a `RunPython`
  function. Even non-model imports are risky if their *value* can change later, because the
  migration's behaviour would silently change retroactively for anyone re-running history from
  scratch.
- Slow/irreversible data migrations that lock large tables — prefer batched/chunked updates or
  raw SQL (`schema_editor.execute(...)`) over looping+`save()` per row for large tables; if
  looping+`save()` is used, be aware it triggers per-row signals/`save()` overhead against the
  *historical* model (fine functionally, slow at scale).
- Data migrations that silently assume single-tenant data in a multi-tenant (Sites) schema —
  always scope backfills per `site_id` where the model is site-aware, mirroring
  `0009_backfill_course_accent_slot`'s per-site loop.
- Testing Django's own auto-generated schema migrations (`AddField`, `CreateModel`, etc. with no
  `RunPython`) is generally *not* worth hand-writing tests for — they're generated and exercised
  by Django's own test suite and by the fact that the test DB build itself runs them. Focus test
  effort on `RunPython`/`RunSQL` data migrations and hand-authored schema edits (constraints,
  raw SQL) with real correctness or reversibility risk.
- Irreversible migrations with no `reverse_code` at all (not even `.noop`) block any
  `migrate <app> <earlier-target>` — including the reverse migrate a `MigrationExecutor`-based
  test performs in its own teardown/reset — so an untested, non-noop-marked irreversible
  `RunPython` can break migration *tests* elsewhere in the suite, not just production rollbacks.

---

## PART B — Current FLS state & gaps

### Migration inventory

~59 migration files across 9 apps (`accounts`, `content_engine`, `student_management`,
`student_progress`, `role_based_permissions`, `webhooks`, `course_applications`,
`course_interest`, `qa_helpers` has none yet, `educator_interface` has none yet).

`grep -rln "RunPython" freedom_ls --include="*.py"` under `*/migrations/` found exactly **4** data
migrations:

1. `freedom_ls/content_engine/migrations/0003_rename_collection_contentcollectionitem_collection_old_and_more.py`
   — mixed schema+data migration: renames a field, adds GenericFK columns, creates `CoursePart`,
   then backfills `collection_type`/`collection_id` from the old FK via `apps.get_model(...)`
   (correct pattern) with a real, working `reverse_code`.
2. `freedom_ls/student_management/migrations/0006_validate_no_duplicate_students.py` — a
   validation-only "data migration": raises an exception if duplicate `Student` rows exist for a
   `user_id`; `reverse` is a no-op `pass` (not `RunPython.noop`, but has same effect since it's a
   plain function that does nothing — acceptable but `RunPython.noop` would be more idiomatic and
   self-documenting). Uses raw SQL via `django.db.connection`, not `apps.get_model` — acceptable
   here since it does no ORM writes, but note it bypasses the "always get historical models"
   guidance because it needs no model at all.
3. `freedom_ls/student_management/migrations/0008_populate_user_from_student.py` — genuine data
   backfill via `schema_editor.execute(f"UPDATE {table} ...")` raw SQL for 3 hardcoded tables, with
   a working reverse that sets `user_id = NULL`. Uses raw SQL rather than `apps.get_model`+ORM
   (fine — it's simple column copies, and raw SQL avoids per-row model overhead — but it means the
   `# nosec B608` comments exist because f-string SQL with hardcoded (non-user) table names trips
   bandit).
4. `freedom_ls/content_engine/migrations/0009_backfill_course_accent_slot.py` — genuine data
   backfill, uses `apps.get_model("freedom_ls_content_engine", "Course")` correctly, loops
   per-`site_id` (multi-tenant-aware — good example to point to), but:
   - imports `from freedom_ls.content_engine.course_accent import PALETTE` — a **live import from
     the current app code**, violating the "don't import current app state into a migration"
     principle for non-model values: if `PALETTE`'s length changes later, replaying this migration
     from scratch on a fresh DB computes different `accent_slot` values than production got when
     it first ran. Worth flagging as the concrete example of pitfall #1 above.
   - `reverse_code=migrations.RunPython.noop` — correctly marked irreversible-but-graph-reversible,
     a good example of the "no meaningful inverse" case from §5.

### Existing missing-migrations guard — already implemented, differently from the "obvious" way

`freedom_ls/contrib/conformance/test_migrations.py` already implements the DB-less
`MigrationAutodetector`-based check described in Part A §1 as a plain pytest test
(`test_migration_state_consistent`), not as a `manage.py makemigrations --check` CI step. It's
part of the `freedom_ls/contrib/conformance/` suite (alongside `test_theme.py`, `test_urls.py`,
`test_settings.py`), which per its own docstring is designed to run against **downstream concrete
projects**, not just FLS itself — a downstream that forgets a migration for a model change will
fail this test. This is a strong existing pattern the skill should document and point future data
migrations at, rather than reinventing `makemigrations --check --dry-run` as a shell step.

Nothing else in the repo runs `makemigrations --check` — no CI workflow step
(`.github/workflows/tests.yml` runs `ruff`, `mypy`, `pytest -m "not playwright"`, Playwright, but
never shells out to `manage.py makemigrations`), no pre-commit hook (`.pre-commit-config.yaml` has
no such hook), and the `manage.py`/`makemigrations` mentions found (`fls-claude-plugin/...`,
`CLAUDE.md`, `demo_content/...`) are unrelated (they're about running `makemigrations` normally as
a dev command, not the `--check` guard). So the *only* guard against "model changed, migration
forgotten" is the conformance test above — good that it exists, but its coverage/robustness isn't
independently verified by any other mechanism (e.g. it's not clear it runs for FLS's own app suite
in CI the same way it would for a downstream — confirm it's actually collected by `testpaths`).

`testpaths = ["freedom_ls", "tests", "fls-content-plugin"]` in `pyproject.toml` includes
`freedom_ls`, so `freedom_ls/contrib/conformance/test_migrations.py` should already be collected
and run on every `pytest` invocation in FLS's own CI (`unit-tests` job in `tests.yml`) — worth
confirming with a quick `pytest --collect-only` rather than assuming, since conformance-suite tests
are sometimes deliberately excluded/opt-in for downstream-only use. No opt-out marker was found
referencing it.

### No `MigrationExecutor`/data-migration tests exist

`grep`-ing the repo for `MigrationExecutor`, `migrate_from`, `migrate_to`,
`django-test-migrations`/`django_test_migrations` found **zero** matches anywhere in
`freedom_ls/` or `tests/`. None of the 4 `RunPython` data migrations above have a dedicated test
exercising their forward (or reverse, where meaningful) behaviour against historical models. This
is the main gap: FLS has good migration-authoring hygiene (correct `apps.get_model` usage in 3/4
migrations, working reverses in 2/4, multi-tenant-aware backfill in 1/4) but zero automated
regression coverage that these migrations actually do what they claim, or that a *future* rewrite
of e.g. `0009`'s backfill logic wouldn't quietly break it.

### No `django-test-migrations` dependency

Not present in `pyproject.toml` `[project.dependencies]`, `[project.optional-dependencies].dev`, or
`[dependency-groups].dev`. Given only 4 data migrations exist project-wide, adding this dependency
is not obviously justified yet (see Part A §3) — a lightweight hand-rolled `MigrationExecutor`
helper is proportionate for now; revisit if data migrations become frequent.

### Gaps to codify in the skill

1. **Point to the existing DB-less missing-migrations test** (`test_migration_state_consistent`)
   as the canonical pattern — don't tell people to add a separate `makemigrations --check` CI step
   when an equivalent, faster, socket-free pytest test already exists and is presumably already
   running in CI. Skill should show how to write an *app-specific* or ad hoc version of this
   pattern for a downstream project too.
2. **Rule: never import live app code (models or otherwise-mutable values) inside a `RunPython`
   function** — cite `0009_backfill_course_accent_slot`'s `PALETTE` import as the concrete
   "don't do this" example to fix or at least flag with a comment, and the correct
   `apps.get_model(...)` usage in the same file as the "do this" example.
3. **Rule: always give `RunPython` a `reverse_code`**, minimally `migrations.RunPython.noop`, not
   a hand-written no-op function — flag `0006_validate_no_duplicate_students`'s `def reverse(...):
   pass` as a candidate cleanup (functionally fine, but `RunPython.noop` is clearer intent and is
   what tooling like django-test-migrations checks for).
4. **Recommend a small hand-rolled `MigrationExecutor` test helper** (a base
   `TransactionTestCase` with `migrate_from`/`migrate_to`, per Part A §2) rather than adding
   `django-test-migrations` as a dependency now, given the current low volume of data migrations —
   but document the library as the recommended upgrade path if/when data migrations become
   frequent enough that the boilerplate stops paying for itself.
5. **Document `pytest-django`'s default migrate-on-setup behaviour** and explicitly warn against
   using `--no-migrations` for this project (it isn't currently used, and should stay that way,
   since it would silently stop exercising the 4 existing — and any future — data migrations).
6. **Concrete worked example for the skill**: write (or point to) a `MigrationExecutor`-based test
   for `0009_backfill_course_accent_slot` — seed 3 `Course` rows pre-migration via
   `apps.get_model`, run the migration, assert `accent_slot` values cycle `0, 1, 2, ...` modulo
   `len(PALETTE)` per site — since it's multi-tenant-aware, small, and self-contained, it's the
   best existing candidate to demonstrate the pattern against real FLS code.
7. **Multi-tenant reminder**: any new data migration touching a site-aware model must scope by
   `site_id` (per `0009`'s pattern) — call this out explicitly since it's easy to silently write a
   single-tenant-assuming backfill in a multi-tenant codebase, and the skill's example migration
   test should assert isolation across ≥2 sites, not just correctness for one.

---

status: ok
