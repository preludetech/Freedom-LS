# Research: best practices for adding a lifecycle state to `CourseApplication`

Scope: practices that sharpen the spec. The idea, `answers.md` and `research_review_foundations.md` already
settle: TextChoices + service functions, no FSM library, audit-log fit, privacy of the reject message,
partial unique index direction, `updated_at` handling. Not repeated here. Items marked (inferred) are my
judgement, not a cited source. Web sources are listed at the end.

## 1. Transition service functions: locking and atomicity

1. **Lock inside the same `atomic()` that writes.** `select_for_update()` takes its lock when the queryset is
   evaluated, and evaluating it outside a transaction raises `TransactionManagementError` on PostgreSQL.
   Re-fetch the row inside the function (`CourseApplication.objects.select_for_update().get(pk=...)`); never
   check state on an instance the caller loaded earlier, because the check would run against stale state.
   (Django docs, select_for_update.)
2. **Lock only the application row.** If the function needs `course` or `organisation`, either fetch them
   after locking, or use `select_for_update(of=("self",))`. Without `of=`, `select_related()` rows are locked
   too (the course and organisation rows would be locked for the whole transaction, blocking unrelated
   work). A `select_related` over a nullable FK (`user`, `anonymous_applicant`, `form_progress` are all
   nullable here) combined with `select_for_update()` raises `NotSupportedError` ("FOR UPDATE cannot be
   applied to the nullable side of an outer join"). So: lock the bare row, then read relations. This is a
   real trap for this model.
3. **Test locking with `TransactionTestCase`.** In `TestCase` the wrapping transaction hides the
   "must be in a transaction" error, so a service that forgets `atomic()` still passes. The spec's tests
   should include at least one test for the concurrent case (two decisions racing: second sees the new state
   and is refused) in a `TransactionTestCase`/`transaction=True` test, or assert via a threaded test.
4. **Refuse by current state, not by "did the row update".** Two idioms exist: lock-then-check (house style,
   chosen) or a guarded `UPDATE ... WHERE state IN (...)` returning the rowcount. The second skips the lock
   and the `save()`, so `updated_at` (auto_now) does not move and no model signals fire. Stay with
   lock-then-check; use the guarded update only if a bulk path appears. (inferred)
5. **One transition table, one refusal path.** Keep a single mapping
   `{action: allowed_from_states}` and one helper that checks it, so the refusal message, the status-page
   "can withdraw" test and the later educator "hide the button" test read the same table. Drift between the
   template's `{% if state in ... %}` and the service is the usual bug.
6. **Idempotent repeat vs refusal.** Decide per action and write it down: a second `withdraw` by double-click
   should either be refused with the same exception or be a no-op, never both depending on timing. Since the
   idea says "a refused transition raises" and "audit only when the state changed", the simplest consistent
   rule is: same-state repeat raises too, and the view catches the exception and shows the current state with
   a message. (inferred)
7. **Do side effects after commit.** The audit row goes inside the transaction (settled). Anything that
   leaves the database (analytics events such as `record_application_submitted`, future webhooks/email)
   belongs in `transaction.on_commit`, not inside the lock, so a rollback cannot publish a decision that did
   not happen. The existing `record_application_submitted` call sits after `complete()`; check it still runs
   once, after commit, when submit becomes a service function.
8. **Thoughtbot's warning**: a status column plus a separate log can contradict each other under concurrency
   unless the transition is validated against the locked row. This is the reason for points 1 and 4, and
   supports the idea's choice of "state is the source of truth, audit is a record of it".

## 2. Refusal exceptions

- Define one small exception hierarchy in the service module: a base (for example `ApplicationTransitionError`)
  and subclasses for the distinct refusals the idea already names: wrong current state, approve with no
  `user`, reject with an empty message. Views and tests catch the base; tests assert the subclass. This avoids
  `ValueError` string matching and avoids a caller catching too broadly (house rule: be specific about
  exception types).
- Carry the current state on the exception (or the application) so the view can say "this application is
  already withdrawn" without re-querying.
- Validate input before locking where it is cheap (empty reject message), and again nothing else: the state
  check must happen under the lock.
- Strip the reject message and treat whitespace-only as empty. Put a model-level max length on the field and
  enforce it in the service (a service call bypasses form validation). (inferred)
- A refused call must leave no audit row and not move `updated_at`: test both.

## 3. Data migration backfilling state

1. **Split schema and data into separate migrations** (add field, backfill, then tighten). Django's migration
   how-to uses exactly this three-step shape for adding a unique field: add nullable, `RunPython` populate,
   then `AlterField` to the final form. The same shape fits `state` and `organisation`: add `organisation` as
   nullable, backfill, then make it non-null (if the spec wants it required) in a later migration.
   PostgreSQL runs DDL transactionally, but mixing a big `RunPython` with later DDL in one transaction can
   hit "pending trigger events" errors when the table is altered after data changes in the same transaction.
   (Known PostgreSQL behaviour; inferred, not from the cited page.)
2. **`state` column default.** Add `state` with a default so `AddField` works on existing rows, then let the
   backfill overwrite. Pick the default deliberately: if the default is `submitted` the backfill only needs to
   touch the `draft` rows (open sitting), which is a smaller, simpler update. Whatever is chosen, the model's
   final default for new rows should match the creation paths (a course with a form starts `draft`; one with
   no form is submitted by the service at creation), so check that `_start_application` sets the state
   explicitly rather than leaning on the default.
3. **Use set-based `update()` over `.filter(...)` with the historical models**, using ORM expressions
   (`Exists`/`Subquery` or `form_progress__completed_time__isnull`), not row-by-row `save()`. It is one
   statement, no loops, no per-row `updated_at` side effects. Django's own batching example is for very large
   tables with `atomic = False`; applications are a small table, so a single `update()` is fine and the
   non-atomic route is unnecessary.
4. **Historical models have no custom methods or properties** (`is_submitted`, `submitted_time`, the `Course`
   manager helpers, `get_default_organisation`). The migration must restate the rule in ORM terms and must
   not import live model code or `organisations.utils`; the "site default organisation" must be read with
   `apps.get_model("organisations", "Organisation")` filtering `is_default=True, site=...`. A site without a
   default organisation (the invariant can be broken in an old database) must be a deliberate decision:
   raise with a clear message, or fall back, but do not silently leave nulls. (Django docs; Code Review
   Doctor, Vinta.)
5. **Site-aware manager.** Historical models do not carry the custom site-filtering manager, which is helpful
   here (no site context in a migration), but the backfill must still scope the organisation by the
   application's own `site_id`, not globally. Test with two sites. (inferred from the project's multi-site
   rule.)
6. **Sole-owner rule in SQL.** "Exactly one owning organisation" is a count over the M2M through table. Do it
   with an annotated `Count("course__organisations")` or a through-table query, not Python loops over every
   course. Zero owners and two-or-more owners both fall to the default; test both plus the one-owner case.
7. **Reverse function.** Provide `RunPython.noop` as reverse when reversing the schema step drops the column
   anyway (omitting `reverse_code` makes the migration irreversible and blocks rollbacks silently on some
   workflows; 22% of audited Django projects had this). Do not write a reverse that deletes data.
8. **Order the backfill and the constraint swap carefully** (next section). Both data and constraint steps
   should be tested through the migration test pattern used in this repo (check `django-test-migrations` or
   the existing migration tests), including a database seeded with: no sitting, completed sitting, open
   sitting, each with and without `user`, to prove the three rules and that nothing is left in the column
   default accidentally.
9. **Drift risk after backfill**: between the `AddField` and the backfill, a running app (or another worktree
   process) can create rows with the default state (Django warns of this race for the uuid example). The
   spec's deploy note should say the migration runs with the app stopped, or that the backfill is re-runnable
   (idempotent `update()` over rows that still hold the default). (Django docs.)

## 4. Constraint swap: unconditional unique to partial unique (PostgreSQL)

1. **A relaxed constraint cannot be violated by existing rows.** Replacing `unique(site, user, course)` with
   the same fields plus `condition=Q(state__in=ACTIVE)` only admits more rows, so no dedupe data migration is
   needed for this step. The inverse (adding a partial constraint on data that already has duplicates among
   active rows) would fail. Today's data has at most one row per (site, user, course), so the swap is safe,
   but the migration test should assert that explicitly.
2. **Order inside the migration:** the new states (and backfill) must exist before the partial index is
   built, because the condition reads `state`. So: migration A adds `state` and `organisation`; migration B
   backfills; migration C does `RemoveConstraint` then `AddConstraint`. Keep removal and addition in the same
   migration so there is no window with no uniqueness at all (they run in one DDL transaction on PostgreSQL).
   For a small table the plain `AddConstraint` is fine; concurrent index creation
   (`AddIndexConcurrently`/`atomic=False`) is only needed on large tables.
3. **Name the constraint for what it now means** (for example `unique_active_application_per_site_user_course`)
   rather than editing the old name. The idea says "Never edit existing migration files"; a rename-by-replace
   makes the intent readable in `\d` output. Also update the stale docstring NOTE and the comment on
   migration `0006`'s reasoning only by adding to new files, not by editing it.
4. **Put the ACTIVE states in one constant** (a module-level tuple or a `QuerySet`/`Q` helper) used by the
   constraint condition, `get_application_for_course`, `get_active_applications`, the claim rule and the admin
   filter. The constraint `condition` is baked into the migration, so a later change to the set of active
   states needs a new migration; say so in a comment next to the constant. Use `state__in=[...]` with literal
   values, not a reference to the Python constant's computed members, so the migration stays valid if the
   constant is later reworked.
5. **The partial index only protects rows with a non-null `user`.** `NULL` never equals `NULL` in a PostgreSQL
   unique index, so unclaimed applications (user null) are not constrained by it, which matches today and the
   claim design. State this in the spec so nobody reads the index as "one active application per applicant".
   If `nulls_distinct` thinking comes up: it is PostgreSQL 15+ only and not wanted here.
6. **Form validation vs database**: Django's `validate_unique`/`validate_constraints` runs a query for
   conditional constraints and is skipped if any field in `exclude` is needed. Do not rely on it for
   race-safety; the service function should catch `IntegrityError` from the create path (re-apply while an
   active one exists, two tabs) and turn it into the "you already have an application" outcome, inside a
   savepoint (`atomic()`), so the outer transaction is not poisoned. `_start_application` already uses
   `get_or_create`; check what it does now that "get" must mean "get the active one", otherwise a closed
   application will be returned by `get_or_create` and the re-apply path never creates a new row.
   (This is the most likely functional bug in the swap.)
7. **`violation_error_message` / `violation_error_code`** can be set on the constraint for admin/form
   validation, but Django 5.2+ also honours them without `condition`; the project is on Django 6, so setting
   them is cheap.
8. **Index for the common lookups**: the partial unique index also serves "active application for this user
   and course" lookups when the query repeats the same `state__in` predicate. A different predicate spelling
   will not use it; keep the lookups on the shared constant. (inferred; confirm with `EXPLAIN` if it matters.)

## 5. Timestamps and decision fields

- **Field naming.** Django convention is `<verb past participle>_at`/`_time`; the existing code uses
  `created_at`, `updated_at`, `claimed_at`, `claim_email_sent_at`, and `completed_time` on the sitting. Follow
  the app's own style (`_at`) for new fields. (The research file used `submitted_at`, `withdrawn_at`.)
- **Per-outcome vs single decision time.** The idea wants an API "decision time" and applicant-facing
  timestamps. Two defensible designs:
  - per-event fields (`submitted_at`, `withdrawn_at`, and `decided_at`), or
  - `decided_at` for approve/reject only, plus the state saying which.
  A single `decided_at` is enough because approve and reject are mutually exclusive terminal outcomes (the
  state tells which), and it lets an API consumer sort on one field. `submitted_at` and `withdrawn_at` stay
  separate because the applicant's own actions are not in the audit log (settled). Avoid `approved_at` and
  `rejected_at` as extra columns: they add a "both set" invalid state. (inferred; the sources found do not
  compare the designs directly.)
- **Nullable, set by the service only, never by `auto_now`.** Set them from one `timezone.now()` captured
  once in the service so the audit row, the field and `updated_at` agree to the same instant.
- **Consistency CHECK constraints.** A small `CheckConstraint` set keeps the row honest even for code
  that bypasses the service (admin, shell, data fixes):
  - `decided_at` is set iff state in (approved, rejected);
  - `rejection_message` is non-empty iff state is rejected (answers.md makes it required);
  - `submitted_at` is set iff state is not draft.
  Adding a check on existing rows requires the backfill to satisfy it first, so (a) put these in the migration
  after the backfill, and (b) the backfill must set `submitted_at` for the rows it makes `submitted`
  (`created_at` for no-form courses, `completed_time` for completed sittings: the same rule as today's
  `submitted_time`). Decide in the spec whether the stored `submitted_at` replaces the derived property
  (then `submitted_time` becomes an alias that stays in the API).
- **Approved/rejected by whom.** Do not add an `actor` FK: the idea keeps decisions in the audit log, where
  `actor_label` is staff. Adding a `decided_by` FK would duplicate audit data and add an erasure case.
- **Reject message field.** Name it for what it is (for example `rejection_message`), `TextField(blank=True)`
  at the column level with the service and a check constraint enforcing non-empty on reject; blank default
  avoids a backfill value. Keep audit `reason` for the reviewer-only text if any (separate from the message
  the applicant sees); never copy the applicant message into `details`.
- **Do not clear message/timestamps on state change in ways that lose history**; since a rejected application
  is closed and a re-apply makes a new row, no reset case exists. Make that explicit so nobody adds a
  "reopen" that overwrites a decision (reopening is a later spec).

## 6. Audit logging state changes

- **Write once, from the service, never from `save()` or a signal.** A signal-based audit would also fire for
  the data migration (historical models do not send these signals in the same way) and for admin edits; the
  service is the one place with the actor and the "state changed" fact. Same transaction as the change
  (settled).
- **Details shape.** Use stable keys (`from`, `to`) with the `TextChoices` *values* (not labels), so entries
  stay readable if labels are reworded. The `details` for approve and reject should not include the reject
  message (settled) or the applicant's name or email.
- **System actions.** If anything other than a human triggers a transition (none planned: withdraw and submit
  are the applicant's), a `actor=None` entry needs a decision about `actor_label`; the idea's rule means this
  spec writes no such entries, so the spec can say "no system actor in this spec".
- **Append-only history is the common recommendation** over per-state timestamp columns for full audit
  (sources: GOV.UK content-block ADR, thoughtbot), which supports using the existing audit log for the
  reviewer actions while only keeping the minimum timestamps on the model for the applicant's own actions.
- **Test the negative**: an entry exists exactly once per successful transition; none for a refused
  transition; none for the applicant's own submit and withdraw; none carries the applicant's name/email.
  The vocabulary invariant test will fail on unknown words, so add the glossary entry in the same commit as
  the action codes.

## 7. Other pitfalls worth a line in the spec

- **`get_or_create` and re-apply**: see 4.6. Re-apply must create a new row only when no active one exists.
- **Admin and `bulk_create`/fixtures**: any code path that creates applications without the service (admin is
  read-only, but fixtures, `qa_helpers` seeders, test factories) must set `state` and `organisation`
  consistently. Update the factories and the QA seed commands in the same change; a factory that leaves
  `state` at its default will produce rows that violate the check constraints above.
- **`is_submitted` derived from state**: after the change, `is_submitted` should mean "state is not draft"
  (a withdrawn application that was once submitted: is it "submitted"? decide, and note that the API keeps the
  field). Withdrawn-from-draft and withdrawn-from-submitted are indistinguishable unless `submitted_at` is
  kept (it is, when set before withdraw), so keep `submitted_at` on withdraw and derive from the timestamp if
  the distinction matters. (inferred)
- **Claim collision rule rewritten over states**: spec it as a table (held state × incoming state → winner),
  not prose, and include closed states: a held `rejected` application should not beat an incoming `submitted`
  one, and an incoming draft should not displace a held active one. A table maps one-to-one onto parametrised
  tests.
- **Withdraw as POST with confirm**: confirm dialog is UI only; the service must still refuse bad states,
  since the dialog does nothing for a replayed or double-submitted POST. On refusal return the status page
  (HTMX 422 rule applies if the request is HTMX).
- **Choices in the DB**: `TextChoices` is validated only in Python. If a `CheckConstraint(state__in=...)` on the
  column is wanted, adding a state later needs a migration; given five stable states this is optional.
  (inferred)

## Sources

- Django docs, `select_for_update()` (locks at evaluation, `of=`, nullable outer join error, `TestCase` hiding
  the transaction requirement): https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update
- Django docs, `UniqueConstraint.condition`, validation behaviour, `violation_error_*`, `deferrable`:
  https://docs.djangoproject.com/en/5.2/ref/models/constraints/#condition
- Django docs, writing migrations (non-atomic migrations, batching example, `RunPython.noop`, three-step unique
  field, race between `AddField` and `RunPython`): https://docs.djangoproject.com/en/6.0/howto/writing-migrations/
- Code Review Doctor, missing `reverse_code` in 22% of audited projects:
  https://dev.to/codereviewdoctor/22-of-django-websites-can-t-roll-back-prod-thanks-to-these-2-mistakes-4cln
- Vinta Software, writing Django migrations (historical models, reverse functions):
  https://www.vintasoftware.com/blog/writing-django-migrations
- Lincoln Loop, old migrations (no-op old data migrations once applied everywhere):
  https://lincolnloop.com/blog/dont-let-old-migrations-haunt-your-codebase/
- Django ticket #34304 (conditional unique constraint on FK, MySQL only; irrelevant on PostgreSQL but shows
  backend-specific ordering failures): https://code.djangoproject.com/ticket/34304
- Thoughtbot, modeling and inserting state transitions in Postgres (status column plus log can contradict under
  concurrency): https://thoughtbot.com/blog/modeling-state-transitions-in-postgres and
  https://thoughtbot.com/blog/inserting-state-transitions-in-postgres
- GOV.UK content block manager ADR 0009, domain events for edition history (append-only history):
  https://docs.publishing.service.gov.uk/repos/content-block-manager/architecture/decisions/0009-use-domain-events-to-record-edition-history.html

Not found by search: a source that directly compares per-state timestamp columns with one decision time; the
recommendation in section 5 is my judgement.

status: ok
