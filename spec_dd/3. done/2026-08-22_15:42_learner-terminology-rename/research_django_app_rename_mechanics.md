# Research: Django-level mechanics of renaming an app package AND its app_label

## Summary (act on this without reading further)

- **The dev DB is rebuilt from scratch (per `idea.md`), which sidesteps almost the entire hard
  problem.** With no data to preserve, the whole "how do I rename a label without losing rows"
  literature below (`AlterModelTable`, `SeparateDatabaseAndState`, `RunPython` on
  `django_content_type`/`auth_permission`/`django_migrations`) is **irrelevant to execution** — you
  edit the app package, `apps.py`, `INSTALLED_APPS`, and the migration file contents, drop the DB,
  and `migrate` from zero. Read section 3 first; it is the one that applies.
- **Every in-app cross-model `ForeignKey` string in the existing migrations is a literal
  `"freedom_ls_student_management.<model>"` / `"freedom_ls_student_progress.<model>"` string**
  (verified: `freedom_ls/student_management/migrations/0001_initial.py:59,168,182,208,222`) — these
  must be rewritten alongside the label in `apps.py`, or `manage.py check` / `makemigrations
  --check` will fail immediately with "model doesn't declare an explicit app_label and isn't in an
  application in INSTALLED_APPS" or a dangling reference.
- **No `db_table` is set anywhere in the three apps** (verified: repo-wide grep for `db_table`
  returns nothing under `freedom_ls/`) — so **every table in all three apps is renamed automatically**
  the moment the label changes and migrations are regenerated/edited, because Django's default table
  name is `<app_label>_<model_name_lowercased>`. This is exactly what `idea.md` is counting on.
- **No app outside the three depends on their labels** (verified: the string
  `freedom_ls_student_management`/`_student_progress`/`_student_interface` appears in migration files
  only inside `student_management/migrations/` and `student_progress/migrations/` themselves — 20
  files total, all self-contained). The dependency graph rewrite is local, confirming `idea.md`'s claim.
- **`freedom_ls/student_management/migrations/0011_rename_models.py` is a pure `RenameModel`
  precedent** for renaming *models within an app* (`StudentCourseRegistration` →
  `UserCourseRegistration`, `StudentCohortDeadlineOverride` → `UserCohortDeadlineOverride`) — it does
  **not** touch the app label, `db_table`, or content types explicitly. It relies on Django's
  automatic behaviour (see §2) to rename the table and update the model's `ContentType.model` in
  place. It is **not** precedent for an app-*label* rename, which Django does not automate at all.
- **`freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py:59-94`
  (`_ensure_permissions_exist`) is the concrete, in-repo mechanism that turns a label rename into
  duplicated permissions if `django_content_type.app_label` isn't fixed up first**: it looks up
  `Permission` by `content_type__app_label=<label>, codename=<codename>`, and if not found, **creates
  a new `Permission` row** pointed at whatever `ContentType` it can find for the new label. Same risk
  applies to `role_based_permissions/utils.py`'s repeated `ContentType.objects.get_for_model(cohort)`
  calls, which back `ObjectRoleAssignment` — if the `Cohort` model's `ContentType` row isn't updated
  in place, `get_for_model` will silently create a **new** `ContentType` row once `Cohort._meta.app_label`
  becomes `freedom_ls_learner_management`, orphaning any existing `ObjectRoleAssignment.content_type_id`
  references. On a rebuilt-from-scratch DB this class of bug can't manifest — but it's exactly the
  kind of thing that would bite a downstream install doing this rename against live data, so it
  belongs in the upgrade notes (`idea.md` §9) even though it's out of scope for execution here.
- **Django's official position, verified against `docs.djangoproject.com`:** `AppConfig.label` is
  explicitly documented as breaking to change once migrations have been applied
  (`ref/applications/`), and Django ships **no** operation that renames an app label — only
  `RenameModel` (renames a model within a label, auto-updates `ContentType.model`, since Django 1.10 /
  ticket #24067) and `AlterModelTable` (renames just the DB table). A label rename with data has to be
  hand-rolled with `RunPython`/`RunSQL` against `django_content_type` (and, transitively,
  `auth_permission` via its `content_type_id` FK) — this is **community practice**, not documented
  Django API.
- **Verification recipe that actually proves this repo's rename is clean, from zero:**
  `uv run manage.py makemigrations --check --dry-run`, `uv run manage.py check`, `uv run manage.py
  migrate`, then `uv run manage.py shell -c "from django.contrib.contenttypes.models import
  ContentType; print(sorted(ContentType.objects.filter(app_label__startswith='freedom_ls_learner').values_list('app_label','model')))"`
  to confirm no `freedom_ls_student_*` rows exist and no duplicates were created, plus
  `uv run manage.py sqlmigrate freedom_ls_learner_management 0001` spot-checked for `CREATE TABLE
  freedom_ls_learner_management_...` names.

---

## 1. What Django derives from the app label / app package path

| Django artifact | Derivation rule | Verified in this repo |
|---|---|---|
| Default `db_table` | `<app_label>_<model_name.lower()>` unless `Meta.db_table` is set | No `db_table` override anywhere under `freedom_ls/` (repo-wide grep, zero hits) — so **all** tables in the three apps rename with the label. Example current names from migrations: `freedom_ls_student_management_cohort`, `freedom_ls_student_management_studentdeadline`, `freedom_ls_student_progress_*` (derived from `migrations/0001_initial.py` `CreateModel` operations, which don't set `options={"db_table": ...}`). |
| `django_content_type.app_label` | Set from `model._meta.app_label` the first time `ContentType.objects.get_for_model()` (or the `post_migrate` `create_contenttypes` signal handler) sees the model | Confirmed live usage in this repo: `role_based_permissions/utils.py:69,93,168,204,240` and `role_based_permissions/tests/test_management_commands.py` all call `ContentType.objects.get_for_model(cohort)` — i.e. `Cohort`'s `ContentType` row is looked up (and, if missing, created) by the model's *current* `app_label`. |
| `auth_permission.codename` + FK | `codename` is static per model (`view_<model>`, `add_<model>`, …); the **app label is not stored on `Permission` at all** — it is read off `Permission.content_type.app_label` at query/check time via the FK join. `has_perm()` strings are computed as `f"{content_type.app_label}.{codename}"`. | `role_based_permissions/registry.py:53-89` hardcodes `"freedom_ls_student_management.view_cohort"` etc. as dict keys — these strings are **not** stored anywhere in `auth_permission`; they are reconstructed at runtime from the FK'd `ContentType.app_label`. This means: fix `django_content_type.app_label` in place → all existing `Permission` rows automatically answer to the new string, no `Permission` row edits needed. Fail to fix it → `sync_role_permissions.py:64-94` (`_ensure_permissions_exist`) will not find a `Permission` matching the new label string and will **create a duplicate** `Permission` row against a **new** `ContentType` row. |
| Migration `dependencies` tuples | `(app_label, migration_name)` string pairs | Verified: `0011_rename_models.py:6` — `("freedom_ls_student_management", "0010_delete_student")`; `0005_courseprogress_last_accessed_content_type_and_more.py:11` — `('freedom_ls_student_progress', '0004_alter_questionanswer_text_answer')`. |
| `ForeignKey("app_label.Model")` lazy strings | Resolved via the app registry against `app_label` at first use | Verified **within-app** cross-model refs use the label explicitly even for same-app FKs, e.g. `0001_initial.py:59` `to="freedom_ls_student_management.cohort"`, `:168` `to="freedom_ls_student_management.cohort"`, `:182` `to="freedom_ls_student_management.student"`, `:208` `to="freedom_ls_content_engine.course"` (cross-app, content_engine, untouched by this rename), `:222` `to="freedom_ls_student_management.student"`. In `models.py` itself these same-app FKs are written as bare Python class references (`Cohort`, `UserCourseRegistration`, etc.), so **only the migration files carry the label string** — `models.py` source needs no `"app_label.Model"` string edits for in-app FKs, but every migration file that has one does. |
| `related_name` / `related_query_name` | Independent of app label; only clashes if two apps define the same `related_name` on FKs to the same target model | No clash risk identified: `related_name` values (`user_registrations`, `cohort_registrations`, `deadlines`, `deadline_overrides`, `recommended_courses`, `recommendations`) are unique per target model in this repo. |
| `settings.AUTH_USER_MODEL`-style swappable strings | `"<app_label>.<ModelName>"`, resolved via `apps.get_model()` | `config/settings_base.py:264` — `AUTH_USER_MODEL = "freedom_ls_accounts.User"`. Untouched by this rename (accounts app isn't renamed), but the *pattern* is what would break if `learner_management` ever became swappable — noted for completeness. |
| `apps.get_model()` call sites | Any code calling `apps.get_model("freedom_ls_student_management", "Cohort")` | None found via grep for `apps.get_model` combined with the three labels in application code (only ORM-level FK strings inside migrations, covered above). |
| `INSTALLED_APPS` | Full dotted `name`, not `label` | `config/settings_base.py:109-110,122` — `"freedom_ls.student_management"`, `"freedom_ls.student_progress"`, `"freedom_ls.student_interface"`. These are the **package name**, changed by the directory rename + `apps.py` `name =` attribute; independent of the `label` fix. |
| Template/static app-directories loaders | Django's `app_directories` template/static finders walk `INSTALLED_APPS` entries and look for a `templates/` / `static/` subdirectory *inside the app package* — keyed off the **filesystem path**, not the `label` | `student_interface/templates/student_interface/...` — the inner directory is a *namespacing convention* (avoids collisions across apps), not something Django enforces from `label`. Renaming the outer package to `learner_interface/` and matching the inner namespace dir is a filesystem-only change; every `{% include %}`/`{% extends %}`/`render()` template-path string that hardcodes `"student_interface/..."` must be edited by hand (this is idea.md §4, not a rename-mechanics footgun). |
| `default_auto_field` | Set per-`AppConfig`, or falls back to `settings.DEFAULT_AUTO_FIELD` | All three `apps.py` files explicitly set `default_auto_field = "django.db.models.BigAutoField"` (matches `settings_base.py:262`), so no behaviour change here regardless of rename. |
| Fixtures / `dumpdata`/`loaddata` natural keys | Django fixture JSON embeds `"model": "<app_label>.<model_name>"` per object | No `*.json` fixture files exist anywhere under `freedom_ls/` (verified via glob) and no `dumpdata`/`loaddata` calls were found outside of unrelated `pytest` "fixtures" (test fixtures, a different concept) and documentation prose. **Not a concern for this rename.** |

---

## 2. Canonical Django-supported way to rename an app_label with existing data

Django ships **no single operation that renames an app label**. The building blocks it does provide,
per the official docs:

- **`RenameModel(old_name, new_name)`** — *"Renames the model from an old name to a new one."*
  (`docs.djangoproject.com/en/6.0/ref/migration-operations/#renamemodel`). Since Django 1.10
  (Trac ticket #24067, resolved 2016), applying `RenameModel` also **auto-updates the matching
  `ContentType.model`** and its `Permission` rows in place via the `post_migrate` signal's migration
  plan — no interactive "delete stale content type?" prompt, no manual `ContentType`/`Permission` SQL
  needed for *model* renames. This is what `0011_rename_models.py` relies on implicitly — it issues
  bare `RenameModel` ops and nothing else, and that is sufficient because it only renames models, not
  the app label they live under.
  **Caveat documented on the same page:** if you change a model's name *and* a substantial fraction of
  its fields in one migration, the autodetector may see it as delete-old/create-new instead of a
  rename, "and the migration it creates will lose any data in the old table" — you must hand-author the
  `RenameModel` op in that case.
- **`AlterModelTable(name, table)`** — *"Changes the model's table name (the `db_table` option on the
  `Meta` subclass)."* (`ref/migration-operations/#altermodeltable`). This changes only the physical
  table name; it does nothing to `django_content_type` or `auth_permission`.
- **`SeparateDatabaseAndState(database_operations=None, state_operations=None)`** — *"A highly
  specialized operation that lets you mix and match the database (schema-changing) and state
  (autodetector-powering) aspects of operations… If the actual state of the database and Django's view
  of the state get out of sync, this can break the migration framework, even leading to data loss."*
  (`ref/migration-operations/#separatedatabaseandstate`). This is the tool of last resort for anything
  the built-in operations can't express directly (e.g. Django's own docs example uses it to convert an
  implicit M2M table to an explicit through-model while renaming the underlying table via `RunSQL`).
- **`migrate --fake` / `--fake-initial`** — marks migrations as applied without running their SQL.
  `--fake-initial` is specifically documented for converting a *pre-existing, un-migrated* app to
  migrations by checking the tables it would create already exist (`topics/migrations/`). It is not a
  label-rename tool by itself, but it's the mechanism you'd reach for if you'd already renamed tables
  by hand and just need Django's migration bookkeeping to match.
- **`AppConfig.label` warning, verbatim from `ref/applications/`:**
  > "Changing this attribute after migrations have been applied for an application will result in
  > breaking changes to a project or, in the case of a reusable app, any existing installs of that
  > app. This is because `AppConfig.label` is used in database tables and migration files when
  > referencing an app in the dependencies list."

**What Django does *not* automate, and what the community pattern fills the gap with (anecdotal,
not official Django API):** renaming the `app_label` itself. The recurring recipe across the sources
found (a widely-shared gist, a PyPI package, and a how-to article — none of them `docs.djangoproject.com`)
is:

1. `UPDATE django_content_type SET app_label = '<new_label>' WHERE app_label = '<old_label>';`
   (this is the load-bearing step — because `Permission` has no `app_label` column of its own and
   resolves it via the `content_type` FK at runtime, fixing `ContentType.app_label` in place is what
   makes existing `Permission` rows answer to the new permission strings without any `auth_permission`
   edit at all).
2. Rename the physical tables — either `AlterModelTable` per model (if you want Django to know about
   it going forward) or a raw `ALTER TABLE old_app_model RENAME TO new_app_model;` per table, matched
   to Django's default naming pattern.
3. `UPDATE django_migrations SET app = '<new_label>' WHERE app = '<old_label>';` so `migrate` doesn't
   try to re-run history under a name it no longer recognises.
4. Update `INSTALLED_APPS`, the app package/`apps.py`, and every `"<old_label>.Model"` string in
   migration files and any `apps.get_model()` call sites.

None of steps 1–3 are `docs.djangoproject.com`-documented Django operations; they are direct SQL/ORM
manipulation of Django's internal bookkeeping tables, sourced from community write-ups. Treat them as
"this is what people do," not "this is Django's supported migration path" — there isn't one for
label renames.

---

## 3. The no-data shortcut (what this rename actually needs)

`idea.md` states the dev DB is rebuilt from scratch rather than migrated forward. Under that
constraint, essentially **all of §2's data-preservation machinery becomes a no-op**:

| §2 step | Needed when rebuilding from zero? |
|---|---|
| `UPDATE django_content_type SET app_label = ...` | **No.** `django_content_type` doesn't exist yet until `migrate` runs against the fresh DB; `create_contenttypes` (the `post_migrate` handler) populates it correctly under the *new* labels the first time, because it reads `app_config.label` off the (already-renamed) `AppConfig`. |
| Physical `ALTER TABLE ... RENAME TO ...` | **No.** `migrate` from zero runs `CreateModel` (or whatever the rewritten/squashed migrations say) and creates tables with the new default names directly — nothing to rename. |
| `UPDATE django_migrations SET app = ...` | **No.** `django_migrations` is empty on a fresh DB; it gets populated with rows keyed to whatever `dependencies`/app labels the (rewritten) migration files declare. |
| `migrate --fake` / `--fake-initial` | **No.** These exist to reconcile a live DB's actual schema with migration history; irrelevant when both start empty together. |
| Fix up `Permission`/`ContentType` FK integrity for existing role assignments | **No** in *this* rebuild (no `ObjectRoleAssignment`/`SystemRoleAssignment` rows survive the rebuild) — **but this is exactly the class of problem a downstream install *with* data would hit**, which is why `idea.md` §9 correctly flags upgrade notes as necessary even though execution here skips it. |

**What is still required for a clean `manage.py migrate` from zero**, regardless of the no-data
shortcut:

1. **Every migration file's `dependencies` and `to=`/`model_name=` label strings must be internally
   consistent with whatever the new `AppConfig.label` is** — Django resolves these purely from the
   file contents at migration-graph-build time, before it ever touches a database. Get one label
   string wrong and `manage.py migrate`/`makemigrations` fails with `ValueError:
   Dependency on app with no migrations: freedom_ls_student_management` (or similar) even on an empty
   DB — this is a pure Python/state-graph error, not a DB error.
2. **`apps.py`'s `name=` must match the actual renamed package's import path** exactly, or Django's
   app registry raises `ImproperlyConfigured` at startup, before migrations even run.
3. **`INSTALLED_APPS` entries must match the renamed package path.**
4. **If squashing to a fresh `0001_initial` per app (idea.md's open question):** the new initial
   migration's `CreateModel` operations must be re-derived (by hand or via `makemigrations`) from the
   *current* model state, not carried over verbatim from old files — this is a clean-slate write, not
   a rename-in-place, so §1/§2 label-string mechanics apply once, to the new file, rather than to 15 +
   5 old ones.
5. **Cross-app dependencies must still resolve**: `student_management`'s migrations depend on
   `freedom_ls_content_engine` and `sites` (verified `0001_initial.py:13-15`); `student_progress`
   depends on `contenttypes` (verified `0005_...:10`) and, per idea.md, is otherwise self-contained.
   These dependency *targets* don't change, only the dependent app's own label string does.

---

## 4. Known footguns (community/anecdotal, cross-checked against this repo's shape)

- **Stale `__pycache__`/`.pyc` after a package directory rename** — a `git mv`-style rename that
  leaves old compiled bytecode or an old empty package directory around can cause Python to import a
  stale module or Django to see two `AppConfig`s with colliding attributes. Standard mitigation:
  ensure the old directory is fully removed (not just emptied) and caches are cleared before the first
  post-rename `migrate`/`check`. General Python/Django packaging folklore, not specific to any single
  source.
- **Stale `django_migrations` rows** pointing at an app name that no longer has any migration files —
  irrelevant here per §3 (fresh DB has no rows to go stale), but is the #1 reported issue in every
  community write-up found for live-data renames.
- **`django_content_type` orphans breaking `GenericForeignKey` lookups** — this repo has three models
  with `GenericForeignKey` (`CohortDeadline`, `StudentDeadline`→`LearnerDeadline`,
  `UserCohortDeadlineOverride`, all in `student_management/models.py`) plus `CourseProgress` in
  `student_progress/models.py` (verified `migrations/0005_...`). Their `content_type` FKs point at
  arbitrary `content_engine` models (`Topic`, `Form`, `Course`), so this rename doesn't touch *those*
  `ContentType` rows — but the `ContentType` rows *for* `CohortDeadline`/`StudentDeadline`/etc.
  themselves (i.e. their own app_label) would be exactly the orphan risk in a live-data version of
  this rename, since nothing in Django auto-updates `ContentType.app_label` on an app-label rename
  (only `RenameModel` gets auto-update treatment, per §2). Not a risk in the from-zero rebuild.
- **Permissions duplicated rather than renamed** — grounded concretely in this repo:
  `role_based_permissions/management/commands/sync_role_permissions.py:59-94`
  (`_ensure_permissions_exist`) looks up `Permission.objects.filter(content_type__app_label=app_label,
  codename=codename)`; on a miss it *creates* a new `Permission` (and, via its `ContentType` lookup
  fallback logic at lines 77-89, potentially a confusing match against the wrong model if the
  heuristic `codename.split("_", 1)[1]` doesn't cleanly match a model name — the code's own comment at
  lines 73-76 flags this: *"this heuristic fails for multi-word model names"*). On a live DB where
  `django_content_type.app_label` wasn't fixed up first, running this command post-rename would
  duplicate every permission under the new label rather than pointing existing ones at it. On a
  from-zero rebuild, this is fine: there's nothing to duplicate, `_ensure_permissions_exist` just
  creates the (single, correct) set fresh.
- **`related_name` clashes during a transitional state** — not a risk here because the rename is
  atomic (package + label + migrations rewritten together, no partial/dual-running state), but is a
  commonly reported issue when apps are renamed incrementally while both old and new labels briefly
  coexist in `INSTALLED_APPS`.
- **`makemigrations` generating a delete+create pair instead of a rename** — this is why `0011_rename_models.py`
  hand-writes `RenameModel` rather than trusting the autodetector; the same discipline applies to the
  planned `StudentDeadline` → `LearnerDeadline` model rename in this spec (idea.md §5) — it must be
  authored as an explicit `RenameModel` operation (or, if squashing, simply not exist as a rename at
  all — the new `0001_initial` just creates `LearnerDeadline` directly).
- **`migrate --fake-initial` traps** — the community write-ups warn that if you rename tables by hand
  first and then try to reconcile history with `--fake-initial`, Django's check ("do all the tables
  this migration would create already exist?") can pass or fail unpredictably depending on partial
  renames. Irrelevant to the from-zero path (§3), flagged here only because it's the #1 gotcha in
  every live-rename source found — worth a line in the upgrade notes for downstream installs.

---

## 5. Verification recipe

Commands to run (from repo root, using the project's `uv run` convention per `CLAUDE.md`), to prove
the rename is complete and clean, **in this order**:

1. **Static/state-graph correctness, before touching a DB:**
   `uv run manage.py check` — catches `ImproperlyConfigured` (app name/label mismatches), unresolved
   `"app_label.Model"` strings in migrations, and any lingering `apps.get_model()` failures.
2. **Migration-state vs. model-state parity:**
   `uv run manage.py makemigrations --check --dry-run` — must exit 0 with no output. Any drift here
   means either a model changed without a matching migration edit, or a migration's `CreateModel`/
   `RenameModel` operations don't match the renamed model definitions (e.g. `StudentDeadline` still
   referenced somewhere the model itself no longer is).
3. **Fresh migrate from zero** (matches idea.md's actual deployment story):
   drop/recreate the dev DB, then `uv run manage.py migrate`. A clean exit with no errors is the
   primary signal — table-creation order will surface any dependency-graph mistake immediately
   (`ValueError`/`NodeNotFoundError` from the migration executor if a `dependencies` tuple points at a
   label that no longer exists).
4. **Spot-check generated SQL for the new labels:**
   `uv run manage.py sqlmigrate freedom_ls_learner_management 0001` (or whatever the renamed label +
   surviving/squashed initial migration is called) and confirm the `CREATE TABLE` statements say
   `freedom_ls_learner_management_cohort`, `freedom_ls_learner_management_learnerdeadline`, etc. —
   the concrete evidence that the no-`db_table`-override assumption in §1 held.
5. **Content type / permission sanity, post-migrate:**
   `uv run manage.py shell -c "from django.contrib.contenttypes.models import ContentType; \
   print(sorted(ContentType.objects.filter(app_label__contains='student').values_list('app_label','model')))"`
   must print an empty list — proves no `freedom_ls_student_*` content types exist (either as leftovers
   or as newly-created duplicates from a botched rename).
6. **Grep sweep matching idea.md's own verification bullet:**
   `grep -rin "student" freedom_ls/ config/ docs/ claude_plugins/` — should return nothing but
   intentional historical references (this research's own citations, if any test/migration filenames
   survive by design per idea.md §2's decision).
7. **Full test suite green**, per idea.md's verification section:
   `uv run pytest` (including the Playwright suite), which will exercise
   `role_based_permissions/tests/test_roles.py:57` (asserts the renamed `display_name="Learner"`),
   `role_based_permissions/tests/test_management_commands.py` (exercises the exact
   `_ensure_permissions_exist` code path flagged as a footgun above), and
   `student_management/tests/test_deadline_utils_bulk.py` (currently exercises `ContentType.objects.get_for_model`
   against content items, unaffected by this app's own rename but a good sentinel for content-type
   plumbing generally).

---

## Reference URLs

- Official Django documentation (verified against Django 6.0 docs tree, matching this repo's pinned
  Django 6.x / confirmed `# Generated by Django 6.0.4` header in
  `student_progress/migrations/0005_courseprogress_last_accessed_content_type_and_more.py`):
  - [Migration Operations reference — RenameModel, AlterModelTable, SeparateDatabaseAndState](https://docs.djangoproject.com/en/6.0/ref/migration-operations/)
  - [Application configuration reference — AppConfig.label warning](https://docs.djangoproject.com/en/6.0/ref/applications/)
  - [How to create database migrations — SeparateDatabaseAndState example, `migrate --fake-initial`](https://docs.djangoproject.com/en/6.0/howto/writing-migrations/)
  - [Migrations topic guide — dependencies, `migrate --prune`, squashing](https://docs.djangoproject.com/en/6.0/topics/migrations/)
  - [django-admin reference — `remove_stale_contenttypes`](https://docs.djangoproject.com/en/6.0/ref/django-admin/#remove-stale-contenttypes)
  - [contenttypes framework reference — ContentType.app_label/model fields, get_for_model caching](https://docs.djangoproject.com/en/6.0/ref/contrib/contenttypes/)
  - [Using the Django authentication system — Permission model, `"<app label>.<codename>"` string format, default permissions](https://docs.djangoproject.com/en/6.0/topics/auth/default/)
- Django ticket tracker (official but not docs-site):
  - [Trac #24067 — Renaming models prompts for content type deletions (resolved: RenameModel auto-updates ContentType since 1.10)](https://code.djangoproject.com/ticket/24067)
  - [Trac #29556 — remove_stale_contenttypes --noinput should delete stale content types](https://code.djangoproject.com/ticket/29556)
  - [Trac #24865 — Add a management command to remove stale content types](https://code.djangoproject.com/ticket/24865)
  - [django-developers mailing list — remove_stale_contenttypes doesn't remove entries for renamed apps](https://groups.google.com/g/django-developers/c/0WrbU_Kc2Z0)
- Community/anecdotal (not docs.djangoproject.com — cited as "community practice," not authoritative API):
  - [Gist — renaming a Django app while preserving migration history and content types (South-era, but the SQL pattern against `django_content_type`/migration-history tables is still the pattern echoed by newer write-ups)](https://gist.github.com/jamesmfriedman/6168003)
  - [Coderbook — How to Change Name of Django Application (step-by-step checklist: content_type app_label UPDATE, table rename, django_migrations UPDATE)](https://coderbook.com/@marcus/how-to-change-name-of-django-application/)
  - [PyPI — django-rename-app package (`rename_app` management command automating this)](https://pypi.org/project/django-rename-app/)
  - [Medium — Rename a Django application walkthrough](https://medium.com/@achraf.ben130/rename-a-django-application-cb0d688a11a1)

## Repo files inspected (verified in this repo)

- `spec_dd/2. in progress/learner-terminology-rename/idea.md`
- `freedom_ls/student_management/migrations/0001_initial.py`, `0011_rename_models.py`
- `freedom_ls/student_progress/migrations/0005_courseprogress_last_accessed_content_type_and_more.py`
- `freedom_ls/student_management/apps.py`, `freedom_ls/student_progress/apps.py`, `freedom_ls/student_interface/apps.py`
- `freedom_ls/student_management/models.py`
- `freedom_ls/site_aware_models/models.py`
- `freedom_ls/role_based_permissions/registry.py`, `roles.py`, `management/commands/sync_role_permissions.py`
- `config/settings_base.py`, `config/urls.py`
- Repo-wide greps for `db_table`, `apps.get_model`, `ContentType.objects`, `dumpdata`/`loaddata`/`fixtures`, and the three app-label strings across `freedom_ls/**/migrations/*.py`

status: ok
