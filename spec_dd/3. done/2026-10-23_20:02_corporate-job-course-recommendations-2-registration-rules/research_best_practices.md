# Research: best practices for rule-based automatic registration

Topic `best_practices`, for spec 2 of the Registration rules effort. Builds on `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (vendor behaviour, not repeated here). Nothing below is a decision; each section ends with "Applies here".

Evidence: Django and PostgreSQL docs were fetched and read (cited). The reconciliation, advisory-lock and provenance points come from general engineering practice; one search found no authoritative source for them, so they are marked "(practice)". Vendor claims are from the earlier research file and carry its excerpt caveats.

## 1. Idempotent rule evaluation

**Practice: reconcile desired state against actual state, never replay events.** Compute "who should hold a rule-made registration" from current attributes, compare with "who does", then apply only the difference (create the missing, deactivate the surplus, reactivate the rule's own deactivated rows). Running it twice yields no further change. Event-style engines ("fires when a user becomes new to a group", Docebo) lose or double-apply on missed events and are why Docebo admins ask for workarounds; Moodle Workplace's "do not reapply while still matching" is an approximation of the same idempotency (earlier research file, section 1).

**Practice: enforce idempotency in the database as well as the code.** Use a unique constraint so a duplicate create is impossible, and write with `bulk_create(..., ignore_conflicts=True)` or `get_or_create` semantics. A partial `UniqueConstraint(condition=Q(...))` is supported by Django (https://docs.djangoproject.com/en/5.2/ref/models/constraints/). Caveat: `bulk_create` skips `save()` and signals, and with `ignore_conflicts` primary keys are generally not set on returned objects (I could not read the `bulk_create` section; it was past the fetched range of https://docs.djangoproject.com/en/5.2/ref/models/querysets/, so check it before relying on this).

**Practice: scope evaluation to what changed.** Evaluate one learner against all of an organisation's enabled rules (attribute change, `Learner` created), or one rule against all learners (rule enabled, edited, disabled). Both call the same per-(learner, course) decision function so results cannot diverge.

**Practice: decide per (learner, course), not per (learner, rule).** Two rules may target the same course. The final state for the pair is a function of all enabled rules, so compute "does any enabled rule match?" once. This is what Cornerstone does ("removed only after leaving all overlapping assignments") and what the idea already settles ("another enabled rule that matches blocks retraction").

Applies here: write one pure decision step (inputs: learner, course, existing registration, all enabled rules; output: create / deactivate / reactivate / leave) used by both evaluation entry points. Pair it with a database uniqueness guarantee on `LearnerCourseRegistration` so a racing create cannot make two rows. Check what uniqueness `LearnerCourseRegistration` has today before choosing between a constraint and `get_or_create`.

## 2. Provenance: FK versus source field, and several matching rules

Options:

| Option | For | Against |
|---|---|---|
| Nullable FK `created_by_rule` on the registration | Simple; joins; `on_delete=PROTECT` or `SET_NULL` is explicit; fits "reactivate only rows it deactivated itself" | Records only one rule; a second matching rule cannot be recorded |
| Source enum field (manual / self / rule) plus the nullable FK | Distinguishes the origins the idea names without inferring from `self_registered` and a null FK | Two fields that must agree; needs a `CheckConstraint` (rule set iff source is rule) |
| Separate link table (registration, rule) many-to-many | Records every rule that currently justifies the row; retraction is "delete my link; deactivate when no links remain", which is exactly the "other enabled rule blocks retraction" semantics, and needs no recomputation | A new table and migration; more writes; spec 3 and 4 must read it |

(practice; the many-to-many "justification" shape is the reference-counting pattern behind Cornerstone's overlapping-assignment behaviour and Arcoro's "removable only through the rule", earlier research file section 1.)

Further practice:
- Record the origin at creation and never overwrite it. "Never takes over a registration that already existed" then follows: if the row exists, the rule does nothing and writes no link or FK.
- Separate "who created it" from "who last deactivated it". "Reactivate only rows it deactivated itself" needs the second fact. Store it as a nullable `deactivated_by_rule` (or equivalent) so a row staff deactivated (null) is never touched. Cornerstone's "dynamic reassignment re-assigns only what dynamic removal removed" is the precedent.
- Add a database `CheckConstraint` for the invariants (https://docs.djangoproject.com/en/5.2/ref/models/constraints/), e.g. a rule FK cannot be set on a self-registered row.
- Make the rule FK `PROTECT` (or forbid delete in the model/admin) rather than cascade: deleting a rule must never cascade into registrations and progress. The idea already requires "disabled before delete", which fits.
- Keep `self_registered` as is and do not reuse it; the idea says rule-made rows are not self-registered.

Applies here: the open question is FK versus source field. Best-practice reading: a nullable FK for "created by rule" plus a way to represent "deactivated by rule" covers every rule the idea settles for spec 2. A link table is only needed if "which rules justify this row" must be shown (spec 4 educator screens, spec 3 recommendations). Note spec 3 gives `RecommendedCourse` its own provenance, so the shape chosen should be one that can be repeated there. Educator-interface 7's "registration source" display needs a single derivable value (manual / self / rule X), which the FK plus `self_registered` yields.

## 3. Soft deactivation versus deletion

- Every surveyed product that deletes on unmatch pays for it: Totara documents loss of settings, grades and group membership; Absorb and Cornerstone limit removal to not-started training (earlier research file sections 1 and 3).
- Practice: retraction is a state change (`is_active=False`), reversible, and leaves progress rows untouched. Moodle cohort sync's "suspend instead of unenrol" option is the same idea.
- Practice: make reactivation symmetrical to deactivation so a flapping attribute does not create churn: the learner re-matches, the rule's own deactivated row comes back, no new row, no second `course.registered` for a row that is merely reactivated (decide this explicitly; the idea is silent on whether reactivation notifies).
- Practice: a row's `is_active` must carry no other meaning. Check whether staff deactivation and rule deactivation are distinguishable (see section 2); without that, "never reactivate what staff deactivated" cannot be implemented.
- "Started" is a threshold choice. Absorb and Cornerstone use "not started" as the safe boundary. A conservative definition (any progress or any activity counts as started) leaves more rows alone, errs towards stale registrations rather than lost work, and is the vendor-consistent default.

Applies here: retract = deactivate only, never delete, never touch progress. Define "started" in one function used by both retraction and preview so they agree.

## 4. Protecting manual and self registrations

- Practice: the rule's write path must be "create if absent, otherwise do nothing". It must never `update_or_create` over an existing row, because that silently changes ownership. Absorb ("manual enrolment bypasses rules") and the idea agree.
- Practice: the retraction path must filter on provenance (`created_by_rule = this rule`, or the many-to-many link) in the query itself, not check it in Python afterwards, so a bug in the check cannot touch other rows. Test with fixtures holding a staff-made, a self-made and a rule-made registration for one course.
- Cornerstone greys out manual removal while a dynamic assignment is active, and Arcoro makes rule-assigned courses removable only through the rule. Whether staff may deactivate a rule-made row by hand is a decision for the spec; if they may, the row must not be reactivated by the rule (it is not "deactivated by the rule"), which the provenance design above supports.

Applies here: the three-origin test fixture above should be a core acceptance test.

## 5. Concurrency: attribute changes and rule edits overlapping

Facts from PostgreSQL (https://www.postgresql.org/docs/current/transaction-iso.html): under the default Read Committed, each statement sees only committed data, and a writer finding a row another transaction is changing waits and re-checks its `WHERE` clause. `ON CONFLICT DO NOTHING` can skip rows for the same visibility reason. Multi-row logic that must be consistent needs stronger isolation or explicit locks, and Serializable/Repeatable Read need whole-transaction retry.

Practice:
1. **Re-read inside the task, not at enqueue time.** The task receives primitive ids (see section 6), loads the current rule and the current learner attributes, and decides from what it reads. A task enqueued before an edit but run after it then evaluates the new rule. This makes "last write wins" correct for both orderings, so no versioning is needed for correctness.
2. **Serialise per learner or per organisation.** Options: (a) `select_for_update()` on the `Learner` row inside `transaction.atomic()` for per-learner evaluation, and on the rule row for per-rule evaluation (docs: https://docs.djangoproject.com/en/5.2/ref/models/querysets/ , `skip_locked` and `of` available; evaluation outside a transaction raises `TransactionManagementError`); (b) PostgreSQL advisory locks, cooperative, with transaction-level `pg_advisory_xact_lock` released on commit or rollback and try-lock variants that do not block (practice; sources found were practitioner blogs, e.g. https://reintech.io/blog/exploring-postgresql-advisory-locks-capabilities). Row locks need no extra machinery and fit this scale. Lock ordering must be fixed (e.g. always learner before rule) to avoid deadlock between a rule sweep and a single-learner evaluation.
3. **Chunk big sweeps.** A rule sweep over thousands of learners should run in batches, each in its own short transaction, re-reading the rule's enabled state at the start of each batch so a disable mid-sweep stops creating registrations. One long transaction holding row locks on every learner is the failure mode.
4. **Let the database arbitrate duplicates.** The unique constraint (section 1) is the last line of defence when two evaluations race to create the same registration; catch `IntegrityError` specifically and treat it as "already exists".
5. **Coalesce redundant work.** Many attribute edits (CSV import in spec 5) can enqueue many tasks. Because evaluation is idempotent and re-reads state, duplicates are harmless, only wasteful; dedupe by (site, learner) where cheap.
6. **Disabled mid-flight.** The "organisation switch off means nothing is evaluated" rule must be checked inside the task, not only at enqueue time, for the same reason as point 1.

Applies here: take the learner-row lock for single-learner evaluation, the rule-row lock for a sweep, batch the sweep, re-check switch and rule state per batch. No version counters.

## 6. Background task design with `django.tasks`

From https://docs.djangoproject.com/en/6.0/topics/tasks/ :
- Arguments and return values must be JSON round-trippable. Pass primitive ids (a site id, a rule pk), reload objects inside the task. Tuples, datetimes and model instances need explicit conversion.
- Enqueue after commit: wrap in `transaction.on_commit(partial(task.enqueue, ...))`, because a worker with a separate connection may run before the data exists. `on_commit` (https://docs.djangoproject.com/en/5.2/topics/db/transactions/) runs immediately outside a transaction, discards the callback on rollback, runs in registration order, and a failing callback does not roll back the transaction.
- The docs say nothing about at-least-once delivery; assume a backend may deliver twice and write tasks safe to re-run. `ImmediateBackend` runs synchronously (useful in tests); `DummyBackend` never runs tasks. `takes_context=True` exposes `context.attempt` for retries.
- Tests: `TestCase` rolls back, so `on_commit` callbacks never run; use `captureOnCommitCallbacks(execute=True)`.

Additional practice:
- **Carry tenant context as an argument.** A worker has no request, so the site must be passed (`site_id`) and the task must establish site-aware filtering itself, as the idea says. Verify against `fls-dev:multi-tenant` how site context is set outside a request, and never rely on thread-local state set by a middleware.
- **Re-validate the site in the task**: load the rule with the site filter so a wrong id cannot cross tenants.
- **Enqueue from one choke point.** Put the `on_commit` plus enqueue in a single helper called by the signal/save hooks for rule save, `Learner` attribute change and `Learner` creation. Hooks living in `save()` miss `bulk_create` and `QuerySet.update`; signals have the same gap. Decide which write paths (admin, spec 5 CSV import) call the helper explicitly. Spec 5 already plans one evaluation per import.
- **Detect real attribute change** (compare old and new relevant fields) before enqueuing, to avoid a task on every learner save.
- **Notifications from a worker.** `fire_webhook_event` does nothing outside a request (idea, open question). Best practice is a service function taking explicit arguments (site, registration) that both the request path and the task path call, rather than a task that fakes a request. Also consider batching or suppressing on large sweeps; Totara has per-audience modes and Absorb needs two switches (earlier research file section 3). Whether a sweep of thousands of learners should send thousands of `course.registered` events is an explicit decision.
- **Observability**: store a run record or at least log counts; Moodle Workplace keeps a per-rule report and auto-disables rules whose course was deleted.

Applies here: one task taking `(site_id, rule_id)` and one taking `(site_id, learner_id)`, both idempotent and re-reading state, enqueued only through an `on_commit` helper.

## 7. Dry-run and preview design

- **Same code path as the real run.** The preview calls the decision function from section 1 with a "do not write" flag and returns the list of actions. A separate "count query" that approximates the rule is what Absorb is criticised for (count disagrees with the result; customers ask for a list). Moodle Workplace shows count plus a full list; SmarterU lists failures with reasons (earlier research file).
- **List, not count, with a reason per row**: will register; will retract; left alone because started; blocked by another rule; skipped because a registration already exists. The idea requires the first two lists; the others are cheap by-products and explain apparent gaps.
- **Preview a proposed change, not a saved one.** For "edit", evaluate the unsaved rule (in memory) against the current learners and diff against current rule-made rows. Do not save, then roll back, in a request.
- **State drift between preview and confirm.** The preview is a snapshot; the confirmed run re-evaluates from live state. Say so in the UI and optionally show a preview timestamp. Do not apply the stored preview list as-is; it can disagree with the world by the time staff confirm (a staleness problem implied by the Absorb complaint).
- **Bound the cost.** Compute with set-based queries (conditions to a queryset filter), `select_related`/`prefetch_related` for the lists' display fields, and paginate or cap the rendered list.
- **Admin confirmation pattern.** Django admin supports an intermediate confirmation page, as the built-in delete action does (practice; I did not fetch the admin docs). Use a view or `ModelAdmin` hook that renders the preview before `save_model` proceeds. Consult `fls-dev:admin-interface`.

Applies here: one `plan(rule_state)` function returns structured actions; the admin preview renders them and the background task applies them. Keeps spec 4's educator screens a reuse, not a rewrite.

## 8. Django-specific patterns that fit

- **Seam in the style of `COURSE_ACCESS_BACKEND`**: a setting with a dotted path, loaded with `import_string`, kinds expose a small interface (matching queryset for a learner or for a rule; description for admin). Per project convention do not build a registry beyond the one kind.
- **Conditions as data, rendered to `Q`**: store conditions in relational form (the lists are ForeignKeys, dates are columns) and build a `Q` combining AND across attributes and OR within one. A queryset filter gives set-based preview and sweeps, and a per-learner check can be `queryset.filter(pk=learner.pk).exists()`, so one definition serves both and cannot drift.
- **Outcome as `TextChoices` with one value** now, so spec 3 adds a value without a reshaping migration.
- **Constraints**: unique rule-made registration per (learner, course) via the existing uniqueness; `CheckConstraint` for provenance invariants (https://docs.djangoproject.com/en/5.2/ref/models/constraints/).
- **`on_delete`**: `PROTECT` on the rule FK from registrations; the idea's "disable before delete" is then enforced by the database too.
- **Deactivated list entries**: matching goes through the ForeignKey regardless of the entry's `is_active`, only the admin choice-limiting excludes inactive entries (matches the idea).
- **Optional app**: gating on both `INSTALLED_APPS` and an organisation switch is the usual Django layering; the app should import-guard nothing in core, and core code should not import the rules app. Hooks therefore run from the rules app (signal receivers connected in `AppConfig.ready()`), which keeps the install optional. This answers part of the open question toward "optional in `INSTALLED_APPS`" at low cost, provided core never imports it.
- **Tests**: `ImmediateBackend` plus `captureOnCommitCallbacks(execute=True)` for the end-to-end path; a `TransactionTestCase` or threaded test only for the lock behaviour, since `TestCase` rollback hides commit-time races.

## 9. Summary of recommendations for the spec

1. Reconciliation, not events; one decision function used by sweep, per-learner evaluation and preview.
2. Database-backed idempotency: uniqueness plus `ignore_conflicts`/`IntegrityError` handling.
3. Provenance: nullable FK at creation, plus a recorded "deactivated by rule" marker; `PROTECT` on delete; `CheckConstraint` for invariants. Consider a link table only if the row must list all justifying rules.
4. Retract by deactivating only, never deleting, only provenance-matched rows, only when no other enabled rule matches and the learner has not started. One shared "started" function.
5. Protect manual and self rows by "create if absent, else nothing" and provenance-filtered retraction queries.
6. Concurrency: tasks carry ids and re-read live state; row locks (learner for single, rule for sweep) with fixed order; batched sweeps re-checking the switch and rule state.
7. Tasks: `site_id` argument, `on_commit` plus `partial` enqueue via one helper, safe to run twice, a service function for notifications that works without a request.
8. Preview: same code path, lists with reasons, computed from an unsaved rule, treated as a snapshot.

## Sources

- https://docs.djangoproject.com/en/6.0/topics/tasks/
- https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- https://docs.djangoproject.com/en/5.2/ref/models/constraints/
- https://docs.djangoproject.com/en/5.2/ref/models/querysets/ (select_for_update read; bulk_create not reached)
- https://www.postgresql.org/docs/current/transaction-iso.html
- https://reintech.io/blog/exploring-postgresql-advisory-locks-capabilities (search result, not fetched; practitioner source)
- Vendor behaviour: see `research_enrolment_rule_engines.md` and its cited URLs.

status: ok · reason: complete; bulk_create and admin-confirmation points marked unverified
