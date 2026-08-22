# Research: migration reset strategy

## Executive summary

**Recommendation: option (c) — delete every app's migration files and regenerate a fresh
`0001_initial` per app — applied project-wide, in one dedicated pass, done exactly once, and done
*last*: after `learner-terminology-rename`, `learners-associated-with-organisations` and
`better_course_progress_tracking` have all landed, and before any downstream project's first real
`manage.py migrate`.** The "no production data" window this idea is named for is real but narrower
than it sounds: FLS itself is never deployed standalone
(`docs/product/deployment.md:110-116` — "FLS is never deployed standalone. A production deployment
is a **concrete project**"), so the shutting point is not FLS's own deploy, it is **the first
`migrate` any downstream project runs against a database it intends to keep**. Concretely, that
downstream project already exists in spec form — `ConcreteFlsImplementation`, described in
`spec_dd/2. in progress/support-concrete-project-deployment/concrete_project_idea.md` — and as of
that document it has **no deployment artifacts at all**: "no Dockerfile, no production compose file,
no Caddyfile, no Ansible, no CI/CD workflows" (`concrete_project_idea.md:25-27`). No downstream
project has run `migrate` against a persisted production database yet, so option (c) is still on the
table, but it will not stay on the table indefinitely — every dev database in this repo is
disposable and rebuilt per branch (`claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md:15-17`),
which is exactly why nothing in *this* repo's own history is evidence either way; only downstream
deploy status is. Doing the reset once, late, project-wide (not per-spec, not per-app opportunistically)
avoids the worst outcome of all three options: a downstream project that has already run `migrate`
against one version of the schema hitting a squashed/regenerated history it cannot reconcile
(`django_migrations` rows keyed by `(app_label, name)` that no longer exist on disk — see §3). Option
(a) (leave history alone, only add forward migrations) is the fallback if there is any doubt the
window has already closed by the time this idea is implemented — it is always safe, at the cost of
carrying 57 migration files project-wide forever, including the four migrations that only exist to
service a deleted `Student` model and a duplicate-`0010_`-caused merge migration in `content_engine`.
Option (b) (hand-rewrite app-label/reference strings inside existing files) is **not recommended in
any scenario**: it does not restore `django_migrations` continuity for apps whose label is changing
(see §3), it is strictly more manual and error-prone than deleting and regenerating, and it produces
a worse artifact than either alternative — files that still look historical but no longer are.

## 1. The three options, stated precisely

**(a) Leave history alone; every future change is an ordinary forward migration.** No existing
migration file is touched, ever, for any reason. `content_engine`'s `0011_merge_20260604_1314.py`
(caused by a duplicate `0010_` — `freedom_ls/content_engine/migrations/0010_course_difficulty_course_estimated_duration_and_more.py`
and `freedom_ls/content_engine/migrations/0010_form_submit_on_exit.py` both exist) stays forever, as
do `student_management`'s four dead `Student`-model migrations
(`0006_validate_no_duplicate_students.py`, `0008_populate_user_from_student.py`,
`0009_remove_student_fk_make_user_non_nullable.py`, `0010_delete_student.py`, all cited in
`spec_dd/2. in progress/learner-terminology-rename/idea.md:56-59`). **Costs:** nothing upfront, but
every app-label rename this idea or its siblings makes still needs *some* migration-level handling —
Django's migration graph is keyed by app label, so renaming `student_management` to
`learner_management` cannot be a no-op under this option either; it becomes a `SeparateDatabaseAndState`-style
forward migration or an explicit new-app-adopts-old-tables dance, which is materially harder to get
right than either of the other two options for exactly the apps this idea most wants to clean up.
**Risks:** low — it is always safe regardless of what any downstream project has already run.
**Buys:** total safety, zero risk of breaking a `migrate` anyone has already run. **Forecloses:**
a clean single-file-per-app history; the dead `Student` migrations and the duplicate-`0010_` merge
become permanent scar tissue.

**(b) Rewrite app-label and reference strings inside existing migration files, in place.** Keep the
same 57 files project-wide, but hand-edit the `dependencies` tuples (`("student_management",
"0004_studentcohortdeadlineoverride")` style keys), any `RenameModel`/`AlterModelTable`/FK-reference
strings, and the app label the migration executes under, so the files "become" the new app's history.
This is what `spec_dd/2. in progress/learner-terminology-rename/idea.md:53-60` poses as its own
open question for its three apps only; this idea's job is to answer it once, project-wide.
**Costs:** as much manual auditing as option (c) (every one of the 15 `content_engine` files and 15
`student_management` files has to be read and reasoned about) but with a materially higher error
surface, because Django infers app identity from *which package the migration module lives in* as
well as from string literals inside it — missing one reference silently breaks the dependency graph
rather than failing loudly. **Risks:** highest of the three. A hand-edited migration that "looks"
historical but was retroactively altered is also a direct tension with CLAUDE.md's "Never edit
existing migration files — create new migrations instead" — see §5's discussion of whether this idea
is a deliberate exception to that rule. **Buys:** nothing option (c) doesn't also buy — see §3: an
app-label rename invalidates `django_migrations` continuity regardless of whether the migration
*files themselves* are edited in place or deleted and regenerated, because Django's post-`migrate`
bookkeeping is keyed by the label, not by file content. **Forecloses:** an honest history — a file
still named `0006_validate_no_duplicate_students.py` sitting inside `learner_management/migrations/`
after being silently rewritten to reference `Learner` is actively misleading to a future reader in a
way a fresh `0001_initial` is not.

**(c) Delete each app's migrations and regenerate a fresh `0001_initial` per app.** `rm
freedom_ls/<app>/migrations/0*.py` (keep `__init__.py`), then `uv run manage.py makemigrations
<app>`. **Costs:** one clean pass across every app with migrations (10 apps: `content_engine`,
`student_management`, `webhooks`, `accounts`, `student_progress`, `organisations`,
`role_based_permissions`, `reports`, `course_applications`, `course_interest`), done after every
in-flight model-changing spec has merged so it captures final shape, not an intermediate one.
**Risks:** the same downstream-`migrate`-already-ran risk as option (b), but with a much smaller
error surface — deleting files and re-running `makemigrations` cannot silently miss a reference the
way hand-editing 15 files can. Requires touching `ContentType`/permission rows deliberately (§4), but
on an empty database that is a non-event. **Buys:** the cleanest possible artifact for the deploy
that actually matters — one `0001_initial.py` per app reflecting the schema as of the pre-deploy
cleanup, with the dead `Student` scaffolding and the duplicate-`0010_` merge gone entirely, not
merely renamed. **Forecloses:** any downstream project's existing `django_migrations` continuity —
which is exactly why §2 and §5's timing question is load-bearing.

## 2. What "no production data" buys, and precisely when the window shuts

This is not "the first FLS deploy" — **FLS is never deployed standalone.** `docs/product/deployment.md:110-116`,
"Deploying a Concrete Project": *"FLS is never deployed standalone. A production deployment is a
**concrete project** — a downstream repository that installs `freedom_ls` as a git submodule and
supplies its own settings, content, and deployment scaffolding."* There is no "FLS production
database" to protect independently of a downstream project's database.

**Does a downstream project already exist?** Yes, in spec form: `ConcreteFlsImplementation` (a
placeholder name — see `spec_dd/2. in progress/support-concrete-project-deployment/idea.md:8-14`
for why it's not named after a theme). Its own deployment idea,
`spec_dd/2. in progress/support-concrete-project-deployment/concrete_project_idea.md`, states
plainly: *"this repo has no deployment artifacts at all — no Dockerfile, no production compose file,
no Caddyfile, no Ansible, no CI/CD workflows (only `.github/dependabot.yml`)"*
(`concrete_project_idea.md:25-27`), and the whole idea is about **authoring** those artifacts for the
first time (`concrete_project_idea.md:41`, "So `ConcreteFlsImplementation` must author its own
deployment artifacts at the project root"). Both `support-concrete-project-deployment/idea.md` and
`concrete_project_idea.md` describe VPS provisioning, CI/CD, and Ansible hardening as **not yet
built** — consistent with `docs/product/deployment.md:9`, *"VPS provisioning and the deploy step are
**not yet built**."* There is no evidence anywhere in `spec_dd/` that `manage.py migrate` has ever
been run against a database any project intends to keep.

**The load-bearing conclusion:** the window is still open as of this research, but it is not open
because FLS hasn't shipped — it is open only because the one downstream project that exists hasn't
deployed yet either. That is a fact about `ConcreteFlsImplementation`'s own timeline, not a permanent
property of FLS. **If someone has already run `migrate` for real by the time this idea is
implemented, option (c) — and (b) — are off the table; only option (a) remains safe.** Confirm this
is still true immediately before executing the reset, not at spec-write time.

## 3. Django mechanics

Primary source: [Django migrations documentation](https://docs.djangoproject.com/en/6.0/topics/migrations/),
and the [`django-admin` reference](https://docs.djangoproject.com/en/6.0/ref/django-admin/#squashmigrations).

- **`squashmigrations`** replays an app's migration operations and produces a smaller set of
  migrations with the same net effect, tagged with a `replaces` attribute listing every migration it
  subsumes. Per the docs: *"These files are marked to say they replace the previously-squashed
  migrations, so they can coexist with the old migration files, and Django will intelligently switch
  between them depending on where you are in the history."* A database that already applied the old
  history keeps working — Django detects the old rows in `django_migrations` and treats the squashed
  migration as already-applied; a fresh database applies only the squashed file. This is Django's own
  built-in tool for exactly the "some databases have the old history, some don't" problem — and it is
  **not what option (c) does**. Option (c) is a hand-rolled fresh `0001_initial`, generated by
  deleting the files and re-running `makemigrations`, with **no `replaces` attribute and no
  `django_migrations` awareness at all**. This is a deliberate choice for this idea, not an oversight:
  `squashmigrations` is the *correct* tool if a downstream project has already run `migrate`, but it
  is unnecessary machinery if no one has — plain deletion is strictly simpler and produces a cleaner
  file when there is nothing to reconcile. If §2's timing assumption turns out to be wrong by
  implementation time, reach for `squashmigrations` (or option (a)), not a manual `0001_initial`.
- **`run_before`** lets a migration declare it must run before another app's specific migration, used
  to break ordering deadlocks between apps that don't otherwise depend on each other. Not currently
  used anywhere in this codebase (not found via search) and not directly relevant to the reset itself,
  but worth checking for after regenerating `0001_initial` files if `makemigrations` introduces any
  unexpected cross-app ordering need.
- **`--fake-initial`** (a `migrate` flag): for an initial migration that only creates tables, Django
  checks whether those tables already exist in the target database and, if so, marks the migration as
  applied without re-running its SQL, rather than failing on "table already exists." This is the
  **exact tool needed if the reset happens *after* a downstream database already has the tables** —
  point a fresh `0001_initial` at a database whose tables already match, run `migrate --fake-initial`,
  and Django accepts the existing schema as the starting point instead of trying to recreate it. This
  is the safety net for late execution of option (c), not a reason to skip planning around §2's
  timing question — `--fake-initial` only works if the existing tables **exactly** match what the new
  `0001_initial` would create; any drift between the last-applied real migration and the regenerated
  one fails loudly (a duplicate-column or type-mismatch error), not silently.
- **`MIGRATION_MODULES`** lets a project override which package holds an app's migrations, per app —
  documented as useful "when converting existing applications to use Django's migration framework or
  when dealing with legacy databases." Not needed here (this project already uses Django's migration
  framework everywhere), but it is the mechanism that would let a downstream project **defer** picking
  up FLS's new `0001_initial` files temporarily if a coordination problem ever arose — worth knowing
  it exists, not worth building around.
- **The concrete failure mode for a downstream project that already ran `migrate` against the old
  history, if option (c) is executed anyway:** `django_migrations` rows are keyed by `(app,
  name)`. Deleting `student_management/migrations/0001_initial.py` … `0015_*.py` and replacing them
  with a single new `student_management/migrations/0001_initial.py` means the downstream database's
  `django_migrations` table still has 15 rows recorded for an app/name combination that **matches by
  app label but not by content** — `migrate` sees `0001_initial` "already applied" (same name, same
  app) and skips it, but the new `0001_initial`'s actual `CreateModel` operations were never run, so
  any model field added in migrations `0002`-`0015` that isn't captured by the *new* `0001_initial`'s
  single snapshot is silently missing from that database until Django's autodetector notices drift
  (which is exactly what `freedom_ls/contrib/conformance/test_migrations.py` checks for — see §1's
  reasoning that this only catches the *symptom*, on a database it can query, not the underlying
  history mismatch on a *specific* downstream database it has never seen). This is the mechanism
  behind "reset after a real deploy breaks things," made concrete.

## 4. `ContentType` and permission rows

Six `GenericForeignKey`/`GenericRelation` fields exist in this codebase today, every one of them
keyed on a `ContentType` row plus an `object_id`:

- `freedom_ls/role_based_permissions/models.py:93` — `ObjectRoleAssignment.target`
- `freedom_ls/student_management/models.py:150,197,245` — `content_item` on three deadline/override
  models
- `freedom_ls/student_progress/models.py:562` — `CourseProgress.last_accessed_item`
- `freedom_ls/content_engine/models.py:393,404` — `ContentCollectionItem.collection` and
  `ContentCollectionItem.child`; `:232,353` carry the matching `GenericRelation("items")` on the
  collection-owning side

Plus `django-guardian`'s own `UserObjectPermission`/`GroupObjectPermission` tables (used for
`CohortAdmin` and the `sync_user_object_permissions` role machinery, per
`spec_dd/3. done/2026-08-21_09:09_organisations/research_codebase_impact.md:127`), which also FK to
`ContentType`.

**What changing an app label does to these, automatically:** almost nothing, and that is the risk.
Django's `contenttypes` app runs `create_contenttypes` on the `post_migrate` signal, which creates a
`ContentType` row for every model it finds and knows about — matched by `(app_label, model)`. Django
*does* have a narrow, built-in rename-detection path (`RenameContentType`, wired to the same signal)
that recognises a `RenameModel` migration operation **within the same app label** and updates the
existing `ContentType` row's `model` field in place rather than creating a new one. **It does not
recognise a whole-app-label rename at all** — `student_management` becoming `learner_management` is
not a tracked migration operation, it is a change to which package (and therefore which `AppConfig.label`,
`freedom_ls/student_management/apps.py:7`, `label = "freedom_ls_student_management"`) a migration
module lives under. So on the next `migrate`, Django creates **brand-new** `ContentType` rows for
`(freedom_ls_learner_management, cohort)` etc., leaving the old `(freedom_ls_student_management,
cohort)` rows orphaned in `django_content_type`. `auth_permission`'s `create_permissions` (also
`post_migrate`-driven) does the same for permission codenames — new rows for the new content type,
old rows orphaned. **Neither cleanup nor remap is automatic under any of the three options.** Any
existing `ObjectRoleAssignment`, `UserObjectPermission`, or `GroupObjectPermission` row that stored
the *old* content type's numeric id becomes silently wrong — it still resolves to *a* `ContentType`
row, just the orphaned one, so `target` lookups start returning `None`/stale data rather than raising.
This is exactly the class of bug that is a complete non-event on an empty database (nothing to orphan)
and a real, hand-written data migration on a populated one (`ContentType.objects.filter(app_label=old).update(app_label=new)`
plus reassigning any `object_id`s that changed shape, done **before** relying on `post_migrate` to
create the new rows, is the standard fix — but it is manual, per app-label rename, and untested in
this codebase). This is a second, independent reason the reset should happen once, pre-deploy, rather
than piecemeal: doing it while every `ContentType`/permission/guardian table is empty means there is
nothing to remap at all.

## 5. Recommendation and sequencing

**Project-wide: option (c).** Delete and regenerate. Not per-app opportunism, not squashing, not
in-place rewriting.

**Is a deliberate one-off reset an exception to CLAUDE.md's "Never edit existing migration files —
create new migrations instead," or a violation of it?** State it plainly: **this is a declared,
one-time exception, and it should be recorded as one** — the rule's evident purpose is to stop
someone from quietly rewriting a migration that has already executed against a database with rows in
it, which is precisely the failure mode this idea exists to avoid *while the window is open*. Deleting
migration files and regenerating them from current model state is categorically different from
editing a migration's logic in place (option (b), which *is* the thing the rule guards against, and
is not recommended here either). Treat the reset as a single, explicitly-scoped, once-only action
taken by this idea — not a precedent that migration files are generally editable, and not something
any future spec should repeat without re-deriving the same "has anyone deployed yet" check in §2.

**Sequencing:** the reset must happen **after** `learner-terminology-rename`,
`learners-associated-with-organisations`, and `better_course_progress_tracking` all land, because
every one of them changes models in the apps this idea would otherwise regenerate migrations for
twice. Doing the reset first would mean regenerating `0001_initial` files that are immediately stale
the moment the next sibling spec merges — wasted work, and a second pass carries all the same risks
as the first with none of the benefit. This idea's own plan should schedule the migration reset as
its **last** implementation step, immediately before this idea is marked done, re-verifying §2's
"has anyone deployed yet" question at that point rather than trusting this research's snapshot.

## 6. Tripwire

**The point of no return is the first `manage.py migrate` any downstream project runs against a
database it intends to keep — after that, `django_migrations` continuity for every affected app
becomes a live production concern, and only ordinary forward migrations (option (a)) remain safe.**

## Risks and gotchas

Ranked by how likely each is to actually bite:

1. **The window closes on someone else's timeline, not this idea's.** `ConcreteFlsImplementation`'s
   own deployment work (`spec_dd/2. in progress/support-concrete-project-deployment/`) is
   in-progress, in parallel with this idea. If it ships a real `migrate` before this idea executes its
   reset step, option (c) silently becomes wrong. Re-check §2 immediately before running the reset,
   not at spec-write time — this is the single highest-risk item.
2. **Option (b) looks like the "safe middle ground" and isn't.** It has all of option (c)'s downstream
   risk (§3) with none of its safety benefit (a whole-app-label rename invalidates `django_migrations`
   continuity regardless of whether the old files are edited or deleted — §4) and a strictly higher
   manual-error surface. Do not let "less disruptive-looking" stand in for "actually lower risk."
3. **`ContentType`/permission/guardian rows are the part every option under-delivers on if the
   database isn't actually empty at execution time.** None of the three options remap these
   automatically for an app-label rename (§4); the only thing that makes this a non-issue is genuinely
   executing the reset while `django_content_type`, `auth_permission`, `guardian_userobjectpermission`,
   and every `GenericForeignKey`-backed table (`ObjectRoleAssignment`, the three `content_item` fields,
   `CourseProgress.last_accessed_item`, `ContentCollectionItem`) are empty. Verify this, don't assume it.
4. **The conformance suite's migration check (`freedom_ls/contrib/conformance/test_migrations.py`)
   only proves the final state is internally consistent — models match migrations — from disk, with
   no database connection (`test_migrations.py:1-7`). It cannot and does not prove a specific
   downstream database's `django_migrations` history is compatible with a regenerated `0001_initial`.
   Passing this suite after the reset is necessary but not sufficient evidence the reset was safe for
   any already-deployed consumer.**
5. **A `--fake-initial` recovery path exists (§3) but depends on exact schema match.** If the reset is
   ever executed after a downstream database already has the old tables, `--fake-initial` is the
   correct recovery tool, but it fails loudly (not silently) the moment the regenerated `0001_initial`
   diverges even slightly from what actually got applied historically (e.g. a manually-run data fix
   that never got captured in a migration). Don't treat `--fake-initial` as a blanket insurance policy.

status: ok
