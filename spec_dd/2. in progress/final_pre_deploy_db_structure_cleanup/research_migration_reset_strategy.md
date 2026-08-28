# Research: migration reset strategy

## Executive summary

**Recommendation stands: option (c) — delete every app's migration files and regenerate a fresh
`0001_initial` per app — applied project-wide, in one dedicated pass, done exactly once, and done
*last*.** All four specs the previous cut of this idea was waiting on have landed and are rebased into
this branch: `learner-terminology-rename`, `learners-associated-with-organisations`,
`extract_forms_into_seperate_app`, `better_course_progress_tracking` (`spec_dd/3. done/` holds all
four). That gate is satisfied.

The migration inventory is smaller and differently shaped than it was: **47 migration files across 11
apps**, not 57 across 10. The four migrations that used to service a deleted `Student` model
(`0006_validate_no_duplicate_students.py`, `0008_populate_user_from_student.py`,
`0009_remove_student_fk_make_user_non_nullable.py`, `0010_delete_student.py`) no longer exist —
`learner_management` and `learner_progress` are each already a single `0001_initial.py`
(`freedom_ls/learner_management/migrations/0001_initial.py`,
`freedom_ls/learner_progress/migrations/0001_initial.py`), squashed as part of the specs that landed.
`content_engine`'s duplicate-`0010_` merge migration survives unchanged
(`freedom_ls/content_engine/migrations/0011_merge_20260604_1314.py`, still depending on both
`0010_course_difficulty_course_estimated_duration_and_more.py` and `0010_form_submit_on_exit.py`) — it
was never touched by any of the four landed specs, because none of them modified `content_engine`
before `extract_forms_into_seperate_app` added two more files on top of it.

The urgency argument changes. The previous cut of this research quoted a July 2026 idea document
(`spec_dd/3. done/2026-07-09_09:42_support-concrete-project-deployment-master-decomposed-into-specs/concrete_project_idea.md`)
describing `ConcreteFlsImplementation` as having "no deployment artifacts at all." That document now
sits in `spec_dd/3. done/` describing a state that predates real deployment work. `docs/product/deployment.md`
(dated 2026-08-27) says the build step is built — the template repo ships CI that builds and pushes a
per-commit, SHA-tagged image (`docs/product/deployment.md:9,33`) — and real Cloudflare R2 buckets were
configured for this project on 2026-08-27 (`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/`). Only
VPS provisioning and the step that pulls a tagged image onto a server remain unbuilt
(`docs/product/deployment.md:9,35`). The gap between "no deployment artifacts" and "a downstream
project has run `migrate` against a database it intends to keep" is now one unbuilt step, not three.
The window is still open — no evidence anywhere in `spec_dd/` says anyone has run `migrate` against a
production Postgres instance — but it is honestly narrower than the previous cut of this research
stated, and this repo has no way to see whether it has already closed (§3).

Option (b) — hand-rewriting label strings inside existing migration files — is rejected: it carries
all of option (c)'s downstream `django_migrations` risk with none of its safety benefit, and produces
a worse artifact than either alternative — a file that still looks historical after being silently
rewritten. `webhooks` will be given a `freedom_ls_webhooks` label this cut (`freedom_ls/webhooks/apps.py:1-6`
has no `label` today, so Django defaults it to plain `webhooks`) — its 10 migrations are the one
label change this cut makes, independent of whether or when the full reset runs.

## 1. The current migration inventory

47 migration files (excluding `__init__.py`) across 11 apps that carry any migrations at all:

| App | Files | Shape |
|---|---|---|
| `content_engine` | 18 | The one app worth cleaning. See below. |
| `webhooks` | 10 | No explicit label yet (`freedom_ls/webhooks/apps.py:4-5` — only `name`, no `label`); gets `freedom_ls_webhooks` this cut, touching migration `dependencies`/FK strings in 9 of the 10 files. |
| `accounts` | 5 | `0001_initial.py` through `0005_alter_legalconsent_options.py`. Ordinary incremental history, no dead weight found. |
| `organisations` | 4 | `0001_initial.py` through `0004_organisation_logo_on_dark_alter_organisation_logo_and_more.py`. |
| `form_engine` | 3 | New app, created whole by `extract_forms_into_seperate_app` on 2026-08-24. All three files (`0001_initial.py`, `0002_formprogress_questionanswer.py`, `0003_alter_formprogress_form.py`) are live iteration on a feature that landed once — not cruft. |
| `role_based_permissions` | 2 | `0001_initial.py`, `0002_alter_objectroleassignment_assigned_by_and_more.py`. |
| `course_applications` | 1 | `0001_initial.py` only. |
| `course_interest` | 1 | `0001_initial.py` only. |
| `reports` | 1 | `0001_initial.py` only. |
| `learner_management` | 1 | `0001_initial.py`, dated 2026-08-23 — see below. |
| `learner_progress` | 1 | `0001_initial.py`, dated 2026-08-25 — see below. |

**`content_engine` is the app worth cleaning**, and it carries two distinct kinds of cruft:

- A duplicate-`0010_` merge. `freedom_ls/content_engine/migrations/0010_course_difficulty_course_estimated_duration_and_more.py`
  and `freedom_ls/content_engine/migrations/0010_form_submit_on_exit.py` both exist, reconciled by
  `freedom_ls/content_engine/migrations/0011_merge_20260604_1314.py`. This predates every spec named in
  this idea's scope and none of them touched it.
- A vestigial delete pair. `freedom_ls/content_engine/migrations/0015_alter_form_unique_together_remove_form_site_and_more.py`
  and `0016_delete_form_delete_formcontent_delete_formpage_and_more.py` (dated 2026-08-24) exist purely
  to unwind `Form`/`FormPage`/`FormContent`/`FormQuestion`/`QuestionOption` — models
  `freedom_ls/form_engine/migrations/0001_initial.py` recreates from scratch in the same commit range.
  These two files do nothing a fresh `content_engine` `0001_initial` wouldn't simply omit.

**`learner_management` and `learner_progress` are already single-file, and got there by the same
mechanism this idea proposes project-wide — deletion and regeneration, not squashing with a `replaces`
list.** `learner_management/migrations/0001_initial.py:1` is dated 2026-08-23, the day
`learners-associated-with-organisations` landed (`spec_dd/3. done/2026-08-23_17:20_learners-associated-with-organisations/`);
it depends directly on `organisations`, meaning the `Learner` model and the `student_management` →
`learner_management` rename were both folded into one clean initial migration rather than left as a
rename-plus-add sequence. `learner_progress/migrations/0001_initial.py:1,13-15` is dated 2026-08-25,
*after* `extract_forms_into_seperate_app` landed — its `dependencies` name
`('freedom_ls_content_engine', '0016_delete_form_delete_formcontent_delete_formpage_and_more')` and
`('freedom_ls_form_engine', '0003_alter_formprogress_form')` directly, meaning `learner_progress` was
re-squashed to absorb `better_course_progress_tracking`'s model surgery rather than growing a second
migration on top of the first. **This establishes precedent already in this codebase**: two apps that
underwent major model surgery during in-flight development were each reset to a fresh `0001_initial`
by the spec that did the surgery, with no `django_migrations` continuity preserved, because there was
nothing to preserve continuity for. This idea's proposal is the same operation, done once, for the
apps that were not part of one of those four specs.

`content_base` has no `migrations/` directory at all, correctly — its three classes
(`freedom_ls/content_base/models.py:10,59,79`, `BaseContent`/`TitledContent`/`MarkdownContent`) are all
`abstract = True`; it owns no table. It is a real installed app with an explicit label
(`freedom_ls/content_base/apps.py:7`, `label = "freedom_ls_content_base"`), just one with nothing to
migrate. Nothing to do for it under any of the three options.

## 2. The three options, re-costed at 47 files across 11 apps

**(a) Leave history alone; every future change is an ordinary forward migration.** Carries all 47
files forever, including `content_engine`'s 18 (the duplicate-`0010`/`0011` merge and the vestigial
`0015`/`0016` delete pair, §1) and `webhooks`'s 10 (which need their `dependencies`/FK-target strings
rewritten to `freedom_ls_webhooks` regardless of this idea, per the settled label change — so "leave
everything alone" is not fully available even under option (a); webhooks needs *some* migration-level
handling no matter which option wins for everything else). Always safe. Never closes the door on
anything.

**(b) Rewrite app-label and reference strings inside existing migration files, in place.** Rejected:
it produces the same downstream `django_migrations` risk as option (c) (below) with a strictly higher
manual-error surface, and the resulting files — still numbered and named as if historical, silently
altered — are a worse artifact than either leaving history alone or replacing it outright.

**(c) Delete each app's migrations and regenerate a fresh `0001_initial` per app.** `rm
freedom_ls/<app>/migrations/0*.py` (keep `__init__.py`), then `uv run manage.py makemigrations <app>`,
across the 11 apps in §1's table. `content_base` needs no action. This makes `content_engine`'s
duplicate-`0010` merge and vestigial `0015`/`0016` delete pair vanish entirely rather than persist
under a new name — a fresh `content_engine` `0001_initial` simply never mentions `Form` at all, because
`form_engine` owns it.

**What happens to `django_migrations` rows keyed by `(app_label, name)` that no longer exist on
disk.** [Django's migration documentation](https://docs.djangoproject.com/en/6.0/topics/migrations/)
describes `django_migrations` as the table Django consults to know which migrations have run. Deleting
`content_engine/migrations/0001_initial.py` … `0017_*.py` and replacing them with one new
`content_engine/migrations/0001_initial.py` means any database that already has 18 rows recorded for
`freedom_ls_content_engine` sees a new `0001_initial` under a name (`0001_initial`) it already believes
is applied — `migrate` treats it as already-run and never executes its `CreateModel` operations, so any
field the *real* history added across 17 later files is silently missing from that specific database
unless something notices the drift. On an empty database — the only case this idea licenses — this is
a non-event: there is no `django_migrations` history to collide with, and no data to leave behind.

**What `--fake-initial` does and does not insure against.** For an initial migration that only creates
tables, [`migrate --fake-initial`](https://docs.djangoproject.com/en/6.0/ref/django-admin/#cmdoption-migrate-fake-initial)
checks whether those tables already exist in the target database and marks the migration applied
without re-running its SQL, instead of failing on "table already exists." This is the correct recovery
tool if the reset is ever executed *after* a downstream database already holds the old tables — it
does not insure against the regenerated `0001_initial` differing even slightly from what is actually
in that database: any drift (a manually-run data fix that never became a migration, a field the
regenerated snapshot names differently) fails loudly, not silently, the moment `--fake-initial` tries
to reconcile schemas that do not match exactly.

**What a downstream project that has already run `migrate` experiences, concretely.** It keeps
`django_migrations` rows for every one of the old numbered files. The new single `0001_initial` has a
different name for most apps (same name, different content, for apps whose old `0001_initial` also
existed) or a genuinely new label (for `webhooks`, once relabeled). Either way `migrate` either skips
the new file entirely (name already marked applied, content never executes) or, for the relabelled
`webhooks`, tries to create tables that already exist under the old label and fails outright unless
someone runs `--fake-initial` by hand, having first reconciled the label change in
`django_content_type`/`auth_permission` (owned by the sibling app-boundaries research, not repeated
here). This is not a graceful degradation — it is either silent data-missing-from-schema or a loud
migration failure, depending on which app.

## 3. The tripwire, re-derived

**The point of no return is the first `manage.py migrate` any downstream project runs against a
database it intends to keep.** After that, `django_migrations` continuity for every affected app
becomes a live production concern and only option (a) remains safe. This has not changed. What has
changed is how close the evidence says that point might be.

**What is now built, per `docs/product/deployment.md` (2026-08-27):**

- The build step is built: the template repo's CI "builds and pushes a per-commit, SHA-tagged image"
  (`docs/product/deployment.md:9,33`) — that image is the deploy/rollback unit.
- The template repo `freedom-ls-concrete-template` "carries the Caddy and Docker Compose scaffolding"
  (`docs/product/deployment.md:113`).
- Real Cloudflare R2 buckets exist for this project as of 2026-08-27
  (`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/`), split by sensitivity
  (`docs/product/deployment.md:56`). Bucket configuration is orthogonal to whether `migrate` has run —
  buckets can exist with zero database traffic — but it is evidence that real production credentials
  now exist in this ecosystem, not zero.

**What is still not built:** "VPS provisioning and the deploy step are not yet built"
(`docs/product/deployment.md:9`) — specifically "Ansible provisioning and OS hardening... and the step
that pulls a tagged image onto the VPS. No playbooks exist in this repository" (`docs/product/deployment.md:35`).

**The honest reading:** the gap between "nothing exists" and "a downstream project has deployed" used
to be three layers — no Dockerfile, no compose file, no CI. It is now one layer — a provisioned VPS and
the pull-and-run step. That is a materially smaller gap than the previous cut of this research argued,
even though the conclusion ("the window is still open") has not flipped. Nothing in `spec_dd/` states
that a VPS has been provisioned or that `migrate` has run against a database anyone intends to keep.

**What this repo cannot see, and must not pretend to infer:** whether `ConcreteFlsImplementation` (or
whatever the live downstream deploy repo is actually called) has since provisioned a VPS, run the
Ansible playbook, or executed `manage.py migrate` against a real Postgres instance is a fact about that
repository's own history, not this one's. This repo has no visibility into that tree at all — no
submodule pointer to inspect, no shared CI status, nothing. Silence in `spec_dd/` here is not evidence
either way about what has happened there.

**The re-check that must run immediately before executing the reset, stated as something a person can
actually do:** ask whoever owns the deploy repo (`freedom-ls-concrete-template` or its instantiation)
directly — has a VPS been provisioned, has the Ansible playbook run, and has `manage.py migrate` been
executed against a Postgres instance anyone intends to keep data in? If the answer is yes, or cannot be
obtained, fall back to option (a): it is always safe. Do not treat this repo's own passing tests, clean
migration state, or the fact that no spec here mentions a deploy as an answer to that question — it
isn't one.

**Why nothing in this repo's own history is evidence either way.** Every developer database in this
repo is disposable and rebuilt per git worktree/branch
(`claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md:15-17`, "Each worktree gets its own
PostgreSQL database... `install_dev.sh` creates it"). A migration reset that works cleanly against
every worktree's dev database proves nothing about downstream production continuity, because none of
those databases has ever had `django_migrations` history worth protecting in the first place. The
`test_migrations.py` conformance check (§4) is the same story: it never opens a database connection at
all.

## 4. Sequencing and safety rails

**What gated the reset before is now clear.** All four specs land and are rebased in:
`learner-terminology-rename`, `learners-associated-with-organisations`, `extract_forms_into_seperate_app`,
`better_course_progress_tracking` (all under `spec_dd/3. done/`). Each of them changed models in apps
the reset would otherwise have had to regenerate twice; that condition is met.

**`spec_dd/1. next/debt-simplify-course-progress-tracking/idea.md` does not gate the reset.** It is a
one-paragraph idea, not yet researched or spec'd, proposing to key the learner dashboard and course
player off `CourseRegistration` UUIDs directly and remove the "guess which registration" resolution
logic (`spec_dd/1. next/debt-simplify-course-progress-tracking/idea.md:1-11`). It has touched no
models. Waiting for it would mean waiting indefinitely for the "1. next" backlog to empty, which never
happens — the reset only needs to trail specs that have actually landed or are actively in flight
against the apps it touches, not every idea that might someday restructure those apps again. If this
idea starts implementation before the reset executes, land it first, the same way the other four were
sequenced; until then, it imposes no constraint.

**What `freedom_ls/contrib/conformance/test_migrations.py::test_migration_state_consistent` protects,
and what it misses.** It builds a `MigrationLoader` with no database connection
(`test_migrations.py:20`, `MigrationLoader(None, ...)`), diffs `ProjectState.from_apps(apps)` (the
current model definitions) against the migration graph on disk via `MigrationAutodetector`
(`test_migrations.py:21-25`), and fails if any drift is detected. Run immediately after the reset, it
proves the regenerated `0001_initial` files exactly reproduce the current model state — no field was
missed, no operation dropped, no leftover model definition without a matching migration. It proves
**nothing about any specific downstream database's `django_migrations` history**, because it never
queries one; it cannot know whether a downstream project's already-applied migration rows are
compatible with the new files, because that information does not exist anywhere this test can reach.
Passing it after the reset is necessary — a failure means the reset itself is broken — but it is not
sufficient evidence the reset was safe for anyone who has already deployed.

## 5. The declared exception

`CLAUDE.md` states: "Never edit existing migration files — create new migrations instead." The reset
is a declared, one-time exception to that rule, and the distinction is exact, not rhetorical.

Editing a migration file in place (option (b), and the general case the rule guards against) changes
what a file that some database's `django_migrations` row already vouches for having run actually
contains — a database that recorded `0006_validate_no_duplicate_students` as applied has no way to
know its logic was later rewritten, and would never re-run it to find out. That is the exact failure
mode the rule exists to prevent: quiet retroactive rewriting of a record something else already trusts.

Deleting a migration file and generating a new one from current model state does not touch any file a
database's history vouches for — it removes the old artifact and writes an unrelated one under (mostly)
the same name, on the explicit, verified precondition that no database anywhere has ever recorded that
old artifact as applied and intends to keep the data that implies (§3). Nothing is retroactively
altered; an old record is discarded before it was ever load-bearing.

**The boundary, so this is not read as general licence:** this exception applies exactly once, to this
idea's project-wide pass, executed after the re-check in §3 confirms the precondition still holds. It
does not authorize editing any migration file's contents afterward, for cleanup or any other reason,
and it does not authorize a second reset later under the same reasoning — once any downstream `migrate`
has run against a database meant to be kept, this door is closed permanently and only ordinary forward
migrations remain safe.

status: ok
