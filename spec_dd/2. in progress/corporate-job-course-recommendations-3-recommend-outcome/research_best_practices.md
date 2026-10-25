# Best practices: rule-driven recommendations (spec 3)

Sources are cited inline. Items marked (general practice) are established engineering practice that I did not source from a page in this run. Treat them as lower confidence than the cited items.

## 1. Idempotent reconciliation: desired state vs incremental

- Prefer desired-state reconciliation. For a given rule and scope, compute the set of (learner, course) pairs that should exist, diff it against the rows the rule currently owns, then create the missing rows and delete the surplus rows. Running it twice gives the same result, so retries, duplicate task deliveries and missed triggers all heal themselves. (general practice: the Kubernetes controller and level-triggered reconciliation pattern.)
- Incremental, event-driven updates ("learner X changed, so add or remove one row") are fine as a fast path for a single learner. Back them with the same per-learner function the full reconcile uses, so there is one definition of "should this learner have this row".
- Make the reconcile function take a scope (one learner, or one rule, or one organisation) and share one code path for every trigger and for the preview. The preview is then a dry run of the same diff: it returns the "to create" and "to remove" sets without writing.
- Create in bulk with `bulk_create(..., ignore_conflicts=True)` against the unique constraint, so a repeat evaluation creates nothing new and a concurrent insert does not fail the batch. Delete with one filtered `delete()` that is restricted to the rule's own rows.

## 2. Provenance and ownership of derived rows

- Store the owner on the row: a nullable FK to the rule (`on_delete` chosen deliberately). NULL means admin-made. The reconciler only ever reads or deletes rows where `rule=<this rule>`, so admin-made rows are never touched. This matches the decision in the idea ("rules never take over rows").
- Because uniqueness is per learner+course, if an admin-made row exists the rule's insert is skipped (it conflicts), and the row stays admin-made. Never update the owner on conflict. Use `ignore_conflicts`, not `update_conflicts`.
- Decide the FK's delete behaviour explicitly. If the rule is deleted, the rows it made should be retracted, so `CASCADE` fits. `SET_NULL` would silently turn rule-made rows into admin-made ones, which is the wrong outcome. Check this against what spec 2 chose for registrations.

## 3. Many-to-many provenance (one row, several sources)

Two options:

1. **Recompute (stateless).** Keep one row per learner+course with no counter. When a rule stops matching a learner, the reconciler checks whether any other enabled rule of the same outcome still matches that learner and course. If none does, it deletes the row. It is simple and self-healing. It costs an evaluation of the other rules on each retraction.
2. **Reference counting / a through table.** A join table (`RecommendedCourse` to rule) holds one row per source, and the recommendation row exists while it has at least one source. A plain integer counter is fragile: it drifts under retries and races, and it can't be repaired without recomputing. A through table is exact and auditable, but it is more schema.

Recommendation: with a single nullable FK and an "other enabled rule still matches" check, only one rule can own a row, so when rule A made the row and rule B also matches, B has nothing to record. If rule A is then disabled, the row must stay for B. That needs either the recompute step to re-attribute the row to B, or a through table. Re-attributing on retraction (set the FK to a surviving matching rule rather than deleting) is the lowest-cost fix and keeps the single-FK schema. Avoid bare integer counters. (general practice, no specific source.)

## 4. Adding a unique constraint to a table with possible duplicates

- A `UniqueConstraint` migration fails with an IntegrityError if duplicates exist. Ship a data migration that dedupes first, and make the constraint migration depend on it. Django orders migrations by `dependencies` and `run_before`, not by filename. The O'Reilly "Testing Database Migrations" appendix shows this exact failure and fix (a cleanup `RunPython` migration, then the constraint migration regenerated to depend on it): https://www.oreilly.com/library/view/test-driven-development-with/9781449365141/apd.html
- Django's migration how-to covers the related pattern of adding a unique field to existing rows: a `RunPython` step plus `reverse_code=migrations.RunPython.noop`, in separate migrations so the schema change and the data change are not mixed: https://git.joshthomas.dev/mirrors/django/src/branch/main/docs/howto/writing-migrations.txt (mirror of the Django docs). The same page's older version (https://django.readthedocs.io/en/1.9.x/howto/writing-migrations.html) warns about rows written between steps, so keep the window short.
- Dedupe rule for this table: group by (user, site, course), keep one row (the oldest, or prefer an admin-made row if a creator concept exists), delete the rest. Keep the oldest `pk` for determinism. The dedupe migration should use `apps.get_model` (historical models), not the real model, and be idempotent.
- If provenance is added in the same spec, order the migrations as: (1) add the nullable rule FK (and organisation, if chosen), (2) dedupe, (3) add the `UniqueConstraint`. All pre-existing rows are admin-made (NULL), so no backfill is needed.
- Postgres detail (general practice): adding the constraint takes a lock while it builds the index. For a small table this is fine. For a large table, create the index concurrently first and attach it, but that is probably unnecessary here.
- Choose uniqueness over the right keys. If the model stays keyed on user+site, the constraint is `(user, site, course)`. Do not include the rule in the constraint, or two rules could each create a row for the same learner and course.

## 5. Soft delete vs hard delete for retracted recommendations

- Hard delete matches the idea: a retracted recommendation is gone, with no dismiss, expiry or ranking, and a learner's dashboard reads the table directly. A soft-delete flag would need every dashboard query and the unique constraint to account for it (a partial unique constraint over live rows), and an un-retracted row would need reviving.
- Soft delete is justified only when you need history ("why was this recommended, and when was it removed") or must remember a learner's dismissal so it is not recreated. Dismissal is out of scope, so there is no need. (general practice.)
- If an audit trail is wanted later, add it separately (an event log) instead of keeping dead rows in the table.

## 6. Race conditions with background tasks

From Django's tracker and docs, as surfaced in search:

- `get_or_create()` is only atomic if the database enforces uniqueness on the lookup fields. Without the constraint, concurrent calls can insert duplicates. So the unique constraint in section 4 is a prerequisite, not an optimisation.
- `get_or_create()` itself handles the lost race by catching the `IntegrityError` and re-running `get()` (Django tickets https://code.djangoproject.com/ticket/12579 and https://code.djangoproject.com/ticket/7402). Inside an outer transaction, the failing insert must run in a nested `atomic()` (savepoint), otherwise the outer transaction is broken. Django's own implementation does this. A GitLab report of the same failure: https://gitlab.com/glitchtip/django-vtasks/-/merge_requests/32
- `select_for_update()` does not protect the create path: if the row doesn't exist there is nothing to lock, and in the lost-race case the row fetched after the IntegrityError is returned unlocked (https://code.djangoproject.com/ticket/29499, fixed in later versions; check the release notes for the Django 6 behaviour).
- Practical pattern for the reconciler:
  - Rely on the unique constraint and treat a conflict as a normal outcome (`bulk_create(ignore_conflicts=True)`, or `get_or_create` in a savepoint).
  - To serialise two reconciles of the same rule, lock the rule row (`Rule.objects.select_for_update().get(pk=...)` inside `transaction.atomic()`), or take a Postgres advisory lock keyed on the rule. A lock on the parent rule row works, because it exists. (general practice.)
  - Make the task idempotent and safe to run twice, and have it re-read the rule's enabled state and the organisation switch inside the transaction, so a task queued before a disable doesn't re-create rows after it.
  - Clearing on registration and the reconciler can race: the reconciler skips already-registered learners, but a registration can land between the check and the insert. Reduce this by doing the registered-check in the same transaction as the insert, and by having a final cleanup in the reconcile that deletes recommendations for registered learners. That makes the system eventually consistent.
- Deletes from the registration path (clearing a recommendation) should be a single `filter(...).delete()`, which is idempotent and does not need a lock.

## 7. Multi-tenant scoping of rows

- Where a model is keyed on user+site and rules belong to an organisation, a rule needs a way to find only its own organisation's rows. Options:
  1. **Provenance only.** The rule FK already identifies the rule's rows (the rule belongs to one organisation). The reconciler filters on `rule=...`. No extra column. Works for retraction and for "rule disabled". It does not tell you the organisation of an admin-made row, and a user in two organisations cannot be told apart for those rows.
  2. **Add a nullable `organisation` FK** (set for rule-made rows, NULL for admin-made). It makes dashboard and reporting filters direct and allows a constraint such as "rule's organisation equals the row's organisation". It duplicates information derivable through the rule, so it needs a check or constraint to stay consistent.
  3. **Re-key on `Learner`** (organisation-scoped). This is the cleanest tenant model but changes the existing model and every path that touches it. The idea says the model stays standalone and additive, which argues against this.
- Recommended: option 1 unless the dashboard must filter by organisation, in which case option 2. The idea's open question hinges on that dashboard behaviour. If a user is in two organisations and both recommend the same course, the unique (user, site, course) constraint gives one row, which the dashboard shows once. That is correct for the learner, since the recommendation is the same course. Retraction by one organisation's rule must not remove a row another organisation's rule also wants, which is the many-to-many case in section 3.
- Always scope queries by site as well (the site-aware manager does this for FLS models). Do not let a task for one organisation's rule query by learner or user alone.
- Test tenant isolation explicitly: two organisations on the same site with the same user, one org's rule retracting must not touch the other's rows. (general practice; see the project skills `fls-dev:multi-tenant` and `fls-dev:testing`.)

## 8. Summary of recommendations for the spec

1. Reconcile by desired state through one scoped function shared by triggers, background task and preview (dry run).
2. Nullable rule FK for provenance. NULL means admin-made. Never reassign on conflict. Use `CASCADE` on rule delete unless spec 2 says otherwise.
3. Unique constraint on (user, site, course), with a dedupe data migration first. Three ordered migrations: add the field, dedupe, constrain.
4. Retract by recompute; where a surviving enabled rule still matches, re-attribute the row to it rather than deleting. No integer counters.
5. Hard delete. No soft-delete flag.
6. Concurrency: unique constraint plus `ignore_conflicts`, savepoint around any `get_or_create`, lock the rule row for the reconcile, re-check state inside the transaction, and a final cleanup of registered learners.
7. Tenant scope: filter by rule (which implies organisation); add an explicit organisation FK only if the dashboard or reporting needs it. Test the two-organisation case.

## References

- https://www.oreilly.com/library/view/test-driven-development-with/9781449365141/apd.html
- https://git.joshthomas.dev/mirrors/django/src/branch/main/docs/howto/writing-migrations.txt
- https://django.readthedocs.io/en/1.9.x/howto/writing-migrations.html
- https://code.djangoproject.com/ticket/29499
- https://code.djangoproject.com/ticket/12579
- https://code.djangoproject.com/ticket/7402
- https://code.djangoproject.com/ticket/20429
- https://gitlab.com/glitchtip/django-vtasks/-/merge_requests/32

status: ok
