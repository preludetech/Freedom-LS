# Research: migration and auto-creation for an explicit Learner model

## Executive summary

This is two genuinely different-risk problems, and the repo's own recent history is the sharpest
evidence for both.

Half A (backfill) is easier than it looks, and easier than the Organisation rollout it follows.
Learner is a brand-new table with no prior rows, so there is no "add a mandatory FK to a populated
table" retrofit problem at all - that was the hazard the whole nullable-then-backfill-then-non-nullable
dance in research_migration_and_rollout.md (from the Organisation spec) existed to manage. In fact,
when the Organisation feature actually shipped, it did not do that dance - it sidestepped the
populated-table problem entirely by shipping organisation as non-nullable with no backfill at all,
and telling downstream operators in upgrade_notes.md "your Cohort and UserCourseRegistration
tables must be empty... If you already have cohorts or registrations you care about, do not run this
upgrade" (quoted in full below). So the Learner backfill is actually the first migration in this repo
that has to face the populated-table backfill problem for real - it just doesn't face it as a
retrofit; it faces it as a straightforward "derive and insert rows into a new, empty table," which is
a much safer shape and has direct, workable precedent already in the repo
(freedom_ls/content_engine/migrations/0009_backfill_course_accent_slot.py,
freedom_ls/organisations/signals.py's _ensure_default_organisation).

Half B (keeping it in sync) is the harder, more consequential half, and the repo's own distribution
model changes the standard "prefer explicit calls over signals" advice. FLS ships as a git submodule
into downstream Django projects that write their own views, commands and integrations against FLS's
models (CLAUDE.md: "designed to be installed into other Django projects... designed to be extended and
customized"). That means the "sender and receiver are both in your own codebase, so use an explicit
call" reasoning behind Django's own signals guidance does not fully hold here: a downstream project can
create a CohortMembership or UserCourseRegistration through code FLS has never seen, and an
explicit-call-only mechanism will never run for it. Recommendation below is a named combination:
post_save signals as the default-safe mechanism (living in student_management, not organisations -
see the layering pitfall in B0), delegating immediately to one explicit ensure_learner() helper, plus
a rebuild_learners management command (precedent: recalculate_progress_percentages.py) as the
mandatory, non-optional escape hatch for every gap signals cannot close (bulk_create, update(),
fixture loads).

---

## Half A - the backfill migration

### A0. What already exists to copy from

- apps.get_model, never a real import - freedom_ls/content_engine/migrations/0009_backfill_course_accent_slot.py:5,10.
  Line 5 imports live app code (PALETTE), the repo's own counter-example: a documented anti-pattern
  in-tree, worth naming so this migration doesn't repeat it. Line 10, apps.get_model on the
  content_engine app label, is the correct pattern.
- Per-site RunPython loop, same file, lines 8-16: iterates site_id values found in the data (not a
  hardcoded Site), assigns per row via .save(update_fields=[...]), reverse_code is
  migrations.RunPython.noop (line 26).
- Idempotent get_or_create for a derived per-site row - freedom_ls/organisations/signals.py:15-42,
  _ensure_default_organisation. Keys the lookup on (site, is_default), not on the seeded name,
  specifically because the name is user-editable after creation and keying on it would produce a
  duplicate. Uses Organisation._base_manager throughout, not the site-aware manager, because the site
  being handled is frequently not the ambient request's site - directly relevant, since a migration has
  no request at all.
- Validation-only migration, fails loudly before a constraint would -
  freedom_ls/student_management/migrations/0006_validate_no_duplicate_students.py:6-19. Raises a custom
  Exception with the offending IDs rather than letting a bare IntegrityError surface later.
- Raw-SQL multi-table backfill with a real, non-noop reverse -
  freedom_ls/student_management/migrations/0008_populate_user_from_student.py:6-27. Reverse nulls the
  column back out - possible only because the column being populated already existed with a prior NULL
  state to restore. Not the right model for Learner's reverse (A6): Learner has no prior state, so its
  reverse must be noop, matching 0009's reasoning, not 0008's.
- Management command as a from-scratch rebuild/escape hatch -
  freedom_ls/student_progress/management/commands/recalculate_progress_percentages.py:1-54. djclick
  command, explicit docstring: "Useful for backfilling after progress_percentage was added, or after
  data migrations that may have left stale values." Uses .iterator() at line 41. Direct precedent for
  B5's rebuild_learners.
- The Organisation rollout ducking the populated-table problem -
  spec_dd/3. done/2026-08-21_09:09_organisations/upgrade_notes.md:31-33,144-150. States plainly there is
  no backfill: organisation is added to Cohort and UserCourseRegistration as non-nullable in one step,
  which a database can only accept while both tables are empty, and operators with existing cohorts or
  registrations are told not to run the upgrade without writing their own backfill first. This is the
  single most important piece of context for this research: FLS has no working precedent for backfilling
  a mandatory relationship into data that already exists - the nearest neighbour explicitly opted out.

### A1. Why Learner's backfill is structurally not the Organisation problem

The Organisation rollout's hazard was a retrofit: adding a NOT NULL FK column to Cohort and
UserCourseRegistration, tables that already had rows with no value for the new column - the classic
nullable-then-backfill-then-non-nullable dance, PostgreSQL ACCESS EXCLUSIVE lock concerns, NOT VALID
CHECK tricks, all documented at length in research_migration_and_rollout.md. None of that applies to
Learner:

- Learner is a brand-new table. Every field (site, user, organisation, whatever else the plan phase
  adds) can be NOT NULL from CreateModel onward - no existing row anywhere needs a value retrofitted,
  because no Learner row exists until this migration creates the table.
- The backfill step is a pure INSERT, not an ALTER COLUMN ... SET NOT NULL against a live table. There
  is no full-table-scan-under-ACCESS-EXCLUSIVE-lock risk on Cohort or UserCourseRegistration, because
  neither table is being altered.
- So the correct shape is two migrations, not the Organisation rollout's five or six: (1) CreateModel
  for Learner with all fields required from the start, including a UniqueConstraint on
  (site, user, organisation); (2) a RunPython data migration that derives and inserts the rows. No
  nullable-field detour, no separate not-null-enforcement migration, no constraint
  RemoveConstraint/AddConstraint dance - nothing pre-existing is being narrowed or widened.

Worth stating explicitly in the idea/spec: a reader who has just read the Organisation research will
reasonably expect the same five-step dance here. It does not apply, and saying so plainly avoids
over-engineering the Learner migration to match a pattern designed for a different problem.

### A2. The exact derivation query

Two source relations, unioned and deduplicated on (site, user, organisation):

1. UserCourseRegistration(user, organisation) - direct, one FK hop. Already-visible precedent:
   freedom_ls/student_management/queries.py:184, inside users_visible_to.
2. CohortMembership.user joined through Cohort.organisation - one hop via cohort_id. Precedent:
   freedom_ls/student_management/queries.py:180, inside the same function.

Both shapes already exist and are already relied on in student_management/queries.py
(organisations_accessible_to, cohorts_visible_to, users_visible_to, lines 105-186) - the derivation
this backfill needs is not a new idea, it is the existing "who counts as associated with this
organisation" logic that today gets recomputed on every request. Learner is this same computation,
cached as a table.

is_active=False registrations - argue both ways. For including them: CohortMembership has no
is_active concept at all (freedom_ls/student_management/models.py:35-48) - once a member, always
counted, with no soft-delete field. If Learner includes every CohortMembership regardless of status but
excludes inactive UserCourseRegistration rows, the two source relations get inconsistent treatment for
what is meant to be one concept. Treating Learner as a pure historical/existence marker keeps it a
simple derived index rather than a second place where status can drift from the registration's own
is_active. Against including them: the idea's other stated goal is a cleanup - "only shows learners
explicitly associated with an organisation." A cancelled registration with no cohort membership
producing a permanent Learner row could look like exactly the leak the cleanup was meant to close.
Recommendation, flagged as a product decision, not a migration-mechanics one: back the backfill with all
registrations regardless of is_active, on the CohortMembership-parity argument, and keep Learner a pure
existence marker with no status field of its own; a "currently active" view is a filtered query joining
back to the live is_active status on the source rows, not a second field on Learner that can drift.

### A3. Cross-site contamination

Both sides of the join are site-aware: User (freedom_ls/accounts/models.py:67, SiteAwareModelBase) and
Organisation (freedom_ls/organisations/models.py:28, SiteAwareModel). There is no model-level clean() or
constraint anywhere in student_management asserting that a Cohort's or UserCourseRegistration's
organisation belongs to the same Site as the row itself - confirmed by reading
freedom_ls/student_management/models.py in full; the only clean() methods present (lines 163, 210, 263)
validate deadline/override uniqueness, not site consistency. Nothing in the schema prevents it.

In practice every ordinary creation path makes this hard to produce by accident: SiteAwareManager
(freedom_ls/site_aware_models/models.py:43-50) filters every queryset by the ambient request's site;
UserCourseRegistrationAdmin/CohortAdmin (freedom_ls/student_management/admin.py:44,74) use
autocomplete_fields for organisation, whose search results are filtered by that same ambient manager;
SiteAwareFactory (freedom_ls/site_aware_models/factories.py:33) defaults every factory's site to the
ambient test site, and the organisations test suite treats passing a different site= explicitly as "the
deliberate exception to the usual rule" (freedom_ls/organisations/tests/test_models.py:74-83).

Conclusion: reachable in principle, not organically produced by any current codepath. The derivation
query does not manufacture a cross-site pairing - if one exists in the derived data it was already a
pre-existing anomaly in Cohort/UserCourseRegistration, not something this backfill introduces. The right
response mirrors A0's 0006 precedent: assert, don't silently propagate. Count rows where a registration's
organisation site does not match the registration's own site (and the Cohort equivalent) and fail loudly
with a custom message naming the offending IDs, rather than quietly creating a cross-site Learner row.

### A4. Scale

At FLS's own documented scale, UserCourseRegistration and CohortMembership row counts are bounded by
registrations, not raw user count, and are very unlikely to exceed tens of thousands of rows even at a
large install - comfortably inside "do it in one migration, in memory" territory. Pull both source
relations with .values_list(...).distinct().iterator() (.iterator() has direct precedent at
recalculate_progress_percentages.py:41); merge into a Python set of (site_id, user_id, organisation_id)
tuples, doing the union-and-dedupe in Python rather than raw SQL, consistent with CLAUDE.md's "ORM only"
convention; bulk_create the resulting Learner instances with ignore_conflicts=True and a modest
batch_size - bulk_create has no existing precedent in this repo (grepped, none found), so name it as a
genuinely new pattern in the plan; then a validation step asserting the derived count matches the
deduplicated set's size, belt-and-braces given ignore_conflicts=True hides partial failures.

### A5. Idempotency and retry-after-partial-apply

Django migrations are atomic by default on a transactional-DDL backend, so a crash mid-RunPython rolls
the whole migration back and it is not recorded as applied - retrying migrate replays it from a clean
slate, and bulk_create(ignore_conflicts=True) plus the unique constraint make a second full run a no-op
even if the migration were manually re-run after being marked applied by hand. Do not --fake this
migration, for the same reason the Organisation upgrade notes already warn against faking theirs
(spec_dd/3. done/2026-08-21_09:09_organisations/2. plan.md:1698). No batching-across-transactions is
needed at this scale.

### A6. Reversibility

reverse_code=migrations.RunPython.noop for the backfill, matching
0009_backfill_course_accent_slot.py:26's reasoning: no meaningful undo for a derived table with no prior
state. CreateModel's own reverse (DeleteModel) is Django's automatic, safe default. Upgrade notes should
say plainly: do not roll back after go-live, once Half B's sync mechanism has created new Learner rows -
the same wording pattern already used for Organisation
(spec_dd/3. done/2026-08-21_09:09_organisations/upgrade_notes.md:151-152).

### A7. Does the unique constraint risk failing against unknown downstream data?

No - a cleaner answer than for Organisation. There, the reasoning was about narrowing an existing
constraint on a table that already had rows. Here there is no existing constraint to narrow: Learner
does not exist until this migration's CreateModel step, so a UniqueConstraint declared at creation time
cannot fail against downstream data that doesn't exist yet. This constraint matters only after go-live,
as the concurrency safety net for Half B's ongoing sync mechanism.

---

## Half B - keeping Learner rows in sync

### B0. Where this logic should live - a layering pitfall worth naming up front

freedom_ls/organisations/signals.py is the obvious place to look for "the file that keeps a
derived-from-elsewhere row in sync with Organisation" - it already does this job for Site to
Organisation. But putting Learner-sync receivers there would be a mistake: to receive post_save for
CohortMembership/UserCourseRegistration, organisations/signals.py would need those models as sender=,
meaning an import from student_management - inverting the dependency direction the Organisation spec
deliberately established (Decision 2, spec_dd/3. done/2026-08-21_09:09_organisations/idea.md:272-278:
the new app depends on site_aware_models only, with student_management depending on organisations, and
these edges declared up front for /fls-dev:plan_structure_review). student_management already depends
on organisations for the organisation FK on Cohort/UserCourseRegistration
(freedom_ls/student_management/models.py:17-20,54-57); the reverse edge does not exist and should not be
introduced by this feature.

The existing precedent for "code that reasons about users, organisations and registrations together" is
freedom_ls/student_management/queries.py, which already imports Organisation locally inside function
bodies and implements organisations_accessible_to, cohorts_visible_to, users_visible_to (lines 105-186) -
the exact cross-cutting shape Learner needs. Recommendation: put the Learner model and its sync logic in
student_management, not organisations, following this precedent and keeping the dependency edge pointed
the same direction it already points. This is a lean, not a hard requirement - the app boundary is a
plan-phase decision for /fls-dev:plan_structure_review - but the specific trap (signals in organisations
reaching "up" into student_management) is worth flagging explicitly.

### B1. post_save signals

Precedent: exactly one signals.py exists in freedom_ls/, freedom_ls/organisations/signals.py, and it is
instructive precisely because of how much machinery one signal ends up needing. A receiver on post_save
with sender=Site (signals.py:45-55) is wired via OrganisationsConfig.ready()
(freedom_ls/organisations/apps.py:9-18) - the standard pattern. A second, separate hook is needed for
the same underlying goal: post_migrate (ensure_default_organisations_after_migrate, signals.py:58-73),
because Django's own sites app creates its default Site row from the historical model during migration,
whose post_save sender is not the real Site class, so the ordinary receiver never fires for it
(documented at signals.py:64-71). This is the clearest evidence in the repo that a signal-based "create Y
when X is created" strategy is rarely just one receiver - Site creation is about as simple and
low-frequency a trigger as exists in FLS, and it already needed two separate wiring points to be reliably
correct. Scaling the same strategy to UserCourseRegistration and CohortMembership - both high-frequency,
user-facing creation paths, and both plausible future targets for a bulk-import feature - multiplies this
complexity.

Known problems, verified against this repo's own code:

- The bulk_create/update() blind spot: bulk_create()'s model save() is not called and pre_save/post_save
  are not sent (Django's own QuerySet reference, cited in B6). No creation site in this repo currently
  uses bulk_create for CohortMembership or UserCourseRegistration (grepped; only get_or_create/create
  sites exist: freedom_ls/student_interface/views.py:547,
  freedom_ls/qa_helpers/management/commands/qa_create_application_docs_scenario.py:243,
  freedom_ls/student_management/management/commands/create_demo_data.py:162) - but nothing stops a future
  bulk-enrolment feature from reaching for bulk_create precisely because it is the performance-correct
  choice, silently breaking Learner sync the moment it lands.
- Fires in every factory call whether wanted or not: SiteAwareFactory._create
  (freedom_ls/site_aware_models/factories.py:38-48) calls obj.save() directly, so a post_save receiver on
  CohortMembership/UserCourseRegistration would fire on every factory call across the test suite - an
  extra DB write and query per call in tests that have no interest in Learner at all. The Organisation
  research counted roughly 366 call sites across 45 files for the four affected factories
  (spec_dd/3. done/2026-08-21_09:09_organisations/idea.md:248-252) - a comparable number here.
- Invisible at the call site: a maintainer reading CohortMembership.objects.create(...) in a view has no
  way to know a Learner row is also produced unless they already know to check signals.py.

### B2. Overriding save()

Precedent: UserCourseRegistration.save() (freedom_ls/student_management/models.py:75-103) already does
this for a webhook - it checks self._state.adding before calling super().save(), and if the row was new,
fires a webhook event via freedom_ls.webhooks.events.fire_webhook_event, with local imports to avoid a
module-load import cycle. Applying the same shape to Learner sync means adding this to
UserCourseRegistration.save() and newly adding an equivalent override to CohortMembership (which has
none today, freedom_ls/student_management/models.py:35-48) - two places to keep the same rule applied,
doubling the surface a future third creation path would need to remember to replicate. It shares the
bulk_create/update() blind spot with signals. Its advantage is textual locality: the call is visible
right in the model file next to the class it affects.

### B3. An explicit service/helper - ensure_learner(user, organisation)

Repo convention: query/service helpers already live in per-app queries.py files -
freedom_ls/student_management/queries.py, freedom_ls/course_applications/queries.py,
freedom_ls/course_interest/queries.py - and CLAUDE.md states the rule directly: "Avoid repeating code...
favor extracting it into a new function/class and calling it as needed." ensure_learner(), an idempotent
get_or_create keyed on site, user and organisation, is exactly this shape, and per B0 belongs in
student_management/queries.py alongside organisations_accessible_to/users_visible_to.

Its specific weakness, sharpened by FLS's distribution model: an explicit call only fires where someone
remembers to write it, in code FLS controls. FLS is shipped as a submodule into projects explicitly meant
to extend it (CLAUDE.md). A downstream project's own view or command that creates a
CohortMembership/UserCourseRegistration directly via the ORM - which nothing prevents - will silently
produce a row with no ensure_learner() call and no Learner row, and FLS has no way to detect it. This is
the mirror image of the signals problem: signals fire in places you didn't want them; an explicit call
fires nowhere you didn't explicitly put it, including downstream code FLS has never seen.

### B4. Database-level options

A trigger has no precedent anywhere in this repo; CLAUDE.md's "ORM only" convention argues against it
culturally even though it would close the bulk_create blind spot completely - the cost is invisibility to
a repo-wide grep and opacity to Django's own migration state, a portability risk for a package shipped
into unknown schemas. A deferred constraint solves intra-transaction ordering, not derived-row creation -
not applicable here. A periodic reconciliation task is more promising: FLS does already have a
background-task system, django.tasks with a DB-backed backend, confirmed via freedom_ls/webhooks/events.py
(imports default_task_backend and task from django.tasks, enqueues around lines 35-39) and
freedom_ls/deployment/settings_defaults.py:49-50 (DATABASE_TASKS using django_tasks_db.DatabaseBackend),
landed via spec_dd/3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/. What
FLS does not have is any existing periodic/scheduled task - only reactive, synchronous enqueueing at
create time. A genuinely periodic reconciliation job would be new scheduling infrastructure, not reuse of
an established pattern - name it as net-new scope if proposed.

### B5. Not storing it at all / a hybrid - rebuild_learners as the escape hatch

Direct precedent: freedom_ls/student_progress/management/commands/recalculate_progress_percentages.py is
exactly this pattern for a different denormalised field - its docstring states the use case verbatim:
useful for backfilling after a field was added, or after data migrations that may have left stale values.
It uses .iterator() and a plain djclick command with no special machinery. A rebuild_learners command
following the same shape - clear existing Learner rows (or diff against them) and re-run A2's derivation -
is not a competing alternative to B1-B3; it is the necessary complement to all of them, because every
mechanism above has at least one silent-gap failure mode. The organisations plan itself endorses the
underlying shape independently of Learner: the callable should live in an importable module, with the
migration file as a thin wrapper (spec_dd/3. done/2026-08-21_09:09_organisations/2. plan.md:635) - the
same function the backfill migration calls should be the same function rebuild_learners calls.

### B6. External research - signals vs explicit calls

Django's own signals documentation states that signals are implicit function calls which make debugging
harder, and that if the sender and receiver of a custom signal are both within your own project, you are
better off using an explicit function call - adding separately that signals give the appearance of loose
coupling but can lead to code that is hard to understand, adjust and debug, and that where possible you
should opt for directly calling the handling code rather than dispatching via a signal. See
https://docs.djangoproject.com/en/6.1/topics/signals/

Lincoln Loop's widely-cited anti-patterns piece argues signals scatter related logic across files, noting
the standard for putting signals in a signals module is not always followed, and recommends overriding
save()/delete() or making an explicit helper call instead so a future developer can see what code is
executed - while conceding legitimate, narrower uses remain for extending third-party apps or cross-app
communication. See https://lincolnloop.com/blog/django-anti-patterns-signals/

The django-antipatterns.com catalogue lists signals under its antipattern index for the same reason:
implicit, hard-to-trace control flow. See https://www.django-antipatterns.com/antipattern/signals.html

Django's own QuerySet reference confirms the mechanical blind spot cited throughout this document:
bulk_create() does not call save() and does not send pre_save/post_save signals. See
https://docs.djangoproject.com/en/6.0/ref/models/querysets/#bulk-create

The even-handed reading, applied to FLS specifically: the consensus "prefer explicit calls" advice is
scoped to the case where sender and receiver are both within your own project. FLS's situation inverts
that premise for at least one of the two creation paths: a downstream project extending FLS is, by design
(CLAUDE.md), expected to write its own code against CohortMembership/UserCourseRegistration - code that
is definitionally not within FLS's project. That is close to the one case both Django's docs and the
community pieces carve out as legitimate for signals: decoupling across a boundary the receiver's author
does not control. This is the basis for the recommendation below - not a rejection of the general
"prefer explicit" guidance, but a recognition that FLS's submodule-distribution model is the specific
situation that guidance doesn't fully cover.

---

## Recommendation

A named combination:

1. One explicit helper, ensure_learner(user, organisation), in student_management/queries.py (B0), an
   idempotent get_or_create keyed on site, user and organisation - analogous to
   _ensure_default_organisation's reasoning in organisations/signals.py:15-42. The single source of truth
   for "how a Learner row gets made," reused by everything below.
2. post_save signals on CohortMembership and UserCourseRegistration, defined in student_management (not
   organisations - the B0 layering pitfall), delegating immediately to ensure_learner(). This is the
   default-safe mechanism specifically because FLS cannot enumerate every downstream creation site (B6) -
   a signal is the one mechanism that automatically covers code FLS's own repo has never seen, as long as
   that code calls .save(), which ordinary ORM usage does by default; bulk_create is a deliberate,
   conscious performance escape hatch a downstream author reaches for on purpose, not by accident.
3. rebuild_learners management command, mirroring recalculate_progress_percentages.py, calling the same
   derivation logic as the backfill migration (A4). Ship it in the same change as the model, not as a
   follow-up - it is the direct mitigation for every gap the signal cannot close (bulk_create, update(),
   loaddata, a downstream integration that bypasses .save() entirely).
4. Document, in the model's own docstring and in upgrade_notes.md, that Learner rows are best-effort and
   eventually-consistent, not a transactional guarantee, and name rebuild_learners as the recovery path.

What FLS deliberately does not do: a DB trigger (culturally out of step with the ORM-only convention,
opaque to the migration graph); a deferred constraint (wrong tool); a truly periodic reconciliation task
(real new scheduling infrastructure this repo doesn't have yet - rebuild_learners run manually, or via a
downstream project's own cron, is a lower-cost substitute for v1, revisit if drift turns out to be a
recurring operational problem).

Named failure mode if the mechanism is missed at some creation site anyway: because the mechanism is
anchored on post_save, the residual gap is precisely bulk_create()/update() paths and fixture/loaddata
restores - both silent, no exception, no log, just a registration or membership that exists with no
matching Learner row. The educator interface's "learners of this organisation" list would silently
under-count real learners, with nothing prompting anyone to notice until a user reports a missing
learner - exactly the drift rebuild_learners exists to turn into a one-command fix rather than a support
investigation. A second, narrower residual risk: a future contributor adding a third creation path for
organisation membership has no structural prompt to notice the Learner-sync convention exists at all
unless they already know to look in student_management's signal-wiring - discoverability is improved
over ad-hoc explicit calls scattered across the codebase, but not perfect, and should be named as a known
limitation rather than claimed away.

---

status: ok
