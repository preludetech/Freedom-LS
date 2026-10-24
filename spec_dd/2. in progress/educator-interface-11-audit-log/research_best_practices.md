# Research: best practices for an application-level audit log in a multi-tenant Django app

Topic `best_practices` for spec 11 (audit log). Sources: the OWASP Logging Cheat Sheet was fetched and read this session. Django docs, PostgreSQL docs, GDPR text and the Django audit packages are cited from established knowledge; their URLs are given for the spec author to confirm, and are marked "(not re-fetched)". Searches for GFK-vs-string and trigger-based immutability returned only package pages (auditrum, django-partitioned-audit, postgres-audit-triggers), no authoritative comparison. FLS terms are used (learner, cohort, organisation, registration).

Inputs read: `idea.md` for this spec; section 4 of `comparable-systems-learner-management.md` (Docebo "immutable record", Canvas logs both users on masquerade, Open edX `ManualEnrollmentAudit` stores a typed reason, nobody offers general undo). The `research_permission_ux_patterns.md` file was not located by the grep of `spec_dd`; its audit recommendation is paraphrased in the idea and in section 4 ("actor, action, target, organisation, time, optional reason on removals").

## 1. What the audit log is, and what it is not

- OWASP's event list includes "user administration, admin actions, access to sensitive data, data import/export" as higher-risk functions worth logging, and warns against "alarm fog" from logging everything. Fits the settled scope: staff mutations only, not reads, logins, webhooks. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OWASP who/what/when/where attributes map to our fields: when (event time), who (actor, plus impersonator if any), what (action, target, result), optional reason, and an "interaction identifier that links related events from one user action" (suits a bulk run / import id).
- An application-level business audit log (this spec) differs from row-history packages (django-simple-history, django-auditlog, django-pghistory). Those track field diffs automatically; we explicitly exclude field-level tracking, so a small hand-written model with a fixed vocabulary is the right call. django-auditlog: https://django-auditlog.readthedocs.io/ ; simple-history: https://django-simple-history.readthedocs.io/ (not re-fetched).

## 2. Append-only enforcement (layers, cheapest first)

1. **Model layer.** Override `save()` to raise if the row is not being added; override `delete()` to raise. Weak alone: `QuerySet.update()`, `bulk_update()`, `QuerySet.delete()` and `bulk_create(update_conflicts=True)` bypass `save()`/`delete()`. Django docs state queryset `delete()` does not call the model `delete()` and `update()` does not call `save()`: https://docs.djangoproject.com/en/stable/topics/db/queries/#updating-multiple-objects-at-once (not re-fetched).
2. **Custom manager/QuerySet.** Subclass the site-aware queryset so `update()`, `delete()`, `bulk_update()` raise; only expose a `record(...)` creating classmethod. This is the standard Django pattern and covers application code. Must compose with the FLS site-aware manager (`fls-dev:multi-tenant`).
3. **Admin read-only.** `has_add_permission`, `has_change_permission`, `has_delete_permission` all return False (view only); all fields readonly. This also stops the admin "delete selected" action. Skill `fls-dev:admin-interface` applies.
4. **Database layer (optional hardening).** Two options in PostgreSQL: (a) a `BEFORE UPDATE OR DELETE` row trigger that raises an exception, installed with a `migrations.RunSQL`; (b) `REVOKE UPDATE, DELETE ON table FROM app_role`. Auditrum documents the privilege approach plus an optional SHA-256 hash chain for tamper evidence (https://pypi.org/project/auditrum/0.5.1/). Trade-offs: a trigger interferes with cascade deletes, test teardown and the retention prune command (these must bypass it, for example by disabling the trigger or a session setting), and it adds hand-written SQL in a repo whose rule is "ORM only, no raw SQL without security review". The idea says "no update or delete through the ORM in application code", which layers 1-3 satisfy. Treat layer 4 as out of scope or a documented downstream option.
5. **Tamper evidence** (hash chain, copy to WORM storage) is recommended by OWASP ("build in tamper detection", "copy logs to read-only media") but is a high-security-tier feature; over-engineering for a staff-readable LMS log. Mention only.

Prune exception: the retention command is the single sanctioned deleter. Give the queryset an explicit, named escape hatch that the command calls, rather than loosening `delete()` generally.

## 3. Actor and target modelling

**Actor.**
- `ForeignKey(AUTH_USER_MODEL, null=True, on_delete=SET_NULL)` plus a **stored actor label** (email or display name at the time). Null actor = system action (management command, webhook, migration). Without the stored label, hard-deleting a user erases who acted, which defeats the log.
- Do not use `CASCADE` (destroys history) or `PROTECT` (blocks user deletion and right to erasure). `SET_NULL` with a snapshot label is the common compromise; for GDPR erasure the label itself is then pseudonymised (section 8).
- FLS note: users are mostly deactivated rather than deleted (flags instead of deletes, per section 4), so SET_NULL will rarely fire, but must be safe.

**Impersonation.** Canvas logs both users on masqueraded calls; Docebo logs the real person behind an impersonation. If FLS (or a downstream project, e.g. django-hijack) lets staff act as another user, record `actor` = the real person and put the impersonated user in a second nullable field (or the JSON `details`). Not in this spec's settled fields; recommend either reserving a nullable `on_behalf_of` field now or declaring impersonation out of scope and noting the extension point. Do not silently log the impersonated user as actor.

**Target.**
- Option A: `GenericForeignKey` (content_type FK + `object_id`). Pros: Django-native, admin support, `GenericRelation` reverse lookups for "history of this learner". Cons: `object_id` type must fit all targets (check whether FLS models use UUID or int pks; use a CharField to be safe), no DB-level integrity (a feature here: the target may be deleted), reverse lookups need an explicit `GenericRelation` on models.
- Option B: store `target_type` (string like `app_label.model`) + `target_id` (CharField) + `target_label`. Pros: no join, stable in exports; cons: no ORM joins, no admin link.
- Common practice (django-auditlog and similar) is Option A with a stored `object_repr`. The idea settled "generic key plus a stored label", so follow that: `ContentType` FK, `object_id` as a string-capable field, `target_label` as `CharField`, snapshotted at write time so the entry reads after deletion. Index `(content_type, object_id)`.
- Many actions concern two entities (membership move: learner + cohort; registration: learner + course). Pick one primary target per entry and put the secondary in `details` with its own labels, or add an optional second reference. For the per-learner and per-cohort history tabs, an entry must be findable from both. Options: (i) nullable `learner` and `cohort` subject references on the entry (SET_NULL); (ii) duplicate entries per perspective; (iii) query `details` (poorly indexable). This is the main modelling decision the spec must make.
- Snapshot labels: store the label at write time, never recompute. Labels contain PII (names, emails): see sections 5 and 8.

**Organisation / site.** Include an `organisation` FK (nullable for site-level actions) and the site key from the site-aware base. Every read query must filter by site and organisation, and organisation admins must only see their own organisation's rows (per `fls-dev:multi-tenant`). Test cross-tenant leakage explicitly. Organisations are likely deactivated, not deleted; use SET_NULL plus a stored label to be safe.

## 4. Action vocabulary

- Fixed, past-tense strings, one per capability in the spec 5 matrix (the idea lists them). Prefer one convention, either namespaced (`learner.deactivated`, `membership.moved`, easy prefix filtering and collision-free downstream extension) or snake_case (`learner_deactivated`). The idea states "the strings are the ones the product docs and the UI use".
- Implement as a registry (module-level dict plus `register_action(key, label)`) so downstream projects can extend it; a closed `TextChoices` enum cannot be extended. Recommend a registry with FLS core registered at app ready, and `record()` raising `ValueError` for unregistered actions, so typos fail fast. Do not put `choices=` on the model field (migration churn each time a downstream project adds an action); validate in `record()`.
- Store the stable machine string, render the human label at read time (label wording changes need no data migration). Never store sentences as the action.
- Keep verbs symmetrical (deactivate/reactivate, add/remove, grant/revoke): the comparable-systems note says a bulk add without a matching remove gets noticed.

## 5. JSON details field

- Use `JSONField(default=dict, blank=True)`; keep small and flat. Intended contents: source and destination cohort ids + labels for a move, counts for bulk runs (requested, succeeded, skipped, failed), import id / batch id, per-object results for bulk.
- Do **not** store: passwords, tokens, reset links, invite tokens, session ids, full request bodies, files, whole before/after model dumps (field-level tracking is out of scope), or unneeded PII. OWASP: sensitive personal data should be "removed, masked, hashed, or pseudonymized where identity isn't needed", log only what is legally sanctioned, and never log access tokens, passwords, connection strings or keys.
- Bulk per-object detail can grow unbounded; cap the stored list (ids only, truncation flag) or write child entries (section 7).
- Validate required keys per action in `record()` so readers can render them. Keep values JSON-serialisable (UUIDs as str).
- OWASP advises sanitising CR/LF and using structured output to avoid log injection; the DB equivalent is escaping on render (Django templates auto-escape; labels are user-supplied, for example cohort names, so never mark them safe) and truncating labels and reasons to column length.

## 6. Transactions: inside the action, versus `on_commit`

- Write the entry **inside** the same `transaction.atomic` as the action (settled in the idea). The log and the change commit or roll back together: no entry for a failed action, no action without an entry. Right default for accountability.
- `transaction.on_commit()` is for side effects that must only happen after commit (emails, webhooks, tasks). Using it for the audit write risks losing the entry if the process dies between commit and callback; in tests, `on_commit` callbacks do not run in `TestCase` unless `captureOnCommitCallbacks` is used. https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit (not re-fetched).
- Trade-off: a failure to write the entry aborts the user's action (strong guarantee, desired here). Do not wrap the write in a bare try/except (project rule: no silent failures).
- Avoid `post_save` signals to generate entries: they cannot know the actor and fire for non-educator code paths. Call an explicit `record()` from the service/utility layer. The role utilities (six TODOs) need the actor passed in; add the parameter where missing.
- Pass the actor explicitly rather than via thread-local "current user" middleware: explicit is testable and works in management commands and imports.
- Event time: `default=timezone.now` on a `DateTimeField` (USE_TZ, stored UTC), set at write. Display in the user's or organisation's timezone at render. OWASP: record time in an international format with synchronised clocks.

## 7. Bulk operations

- Settled: one summary entry per bulk run, per-object detail in JSON. Compare Open edX, which writes one `ManualEnrollmentAudit` per enrolment.
- Trade-off: a summary entry makes per-learner history incomplete (the learner tab will not show a bulk deactivation unless it searches `details`). Alternatives: (a) one summary entry plus one entry per object sharing a batch id (OWASP interaction identifier), with per-object entries hidden from the organisation log by default and shown on the learner/cohort tab; (b) summary only, as settled. Option (a) multiplies rows (a 5,000-row import yields 5,001 inserts; `bulk_create` does it in one query but bypasses `save()`, so the append-only guard must live in the manager).
- Recommendation: honour the settlement but flag the per-learner history gap; if the learner tab must show bulk actions, add per-object child entries with a shared batch id. Decide in the spec; it drives indexing and section 3.
- For partially successful runs record counts of success, skip and fail.

## 8. Retention, privacy and erasure

- Keep-everything default plus an opt-in prune command matches common practice. The prune command should take an age (argument or setting), support `--dry-run`, delete in batches, write its own summary audit entry (OWASP: access to logs should be recorded, monitored and restricted; pruning the log is itself auditable), and not run by default.
- GDPR: audit logs of staff actions are generally justified under legitimate interests or legal obligation; data minimisation (Art. 5(1)(c)) and storage limitation (Art. 5(1)(e)) mean a retention period should be set and documented, and Art. 17(3) exempts erasure where retention is needed for legal claims or compliance. https://gdpr-info.eu/art-17-gdpr/ (not re-fetched). Practical approach: keep the entry, pseudonymise personal data in it on an erasure request.
- Pseudonymise on user erasure: a documented `anonymise_user(user)` function called by whatever flow anonymises the user, in the same transaction. It nulls the actor FK (SET_NULL does this automatically) and overwrites `actor_label` and any `target_label` referring to that person with a placeholder for entries where they were actor or target. Needs `(content_type, object_id)` indexed. It is an exception to append-only and must use the same sanctioned escape hatch as pruning. Names inside `details` and `reason` free text are the hard part: `reason` is staff-typed and may contain PII, so limit its length and add help text asking staff not to enter sensitive data.
- Comparable systems anonymise on delete (Moodle) or hard-delete (TalentLMS, Docebo), so downstream projects will likely need the hook; keep it a documented function, not signal magic.
- Access to the log is itself sensitive: limit to site admins and organisation admins (settled; `view_audit_log`). No export (out of scope).

## 9. Reason field

- Optional `CharField`/`TextField` with `blank=True`, prompted on removals and deactivations, never required (settled; Open edX). Strip whitespace, render escaped, treat as untrusted. Short max length (for example 500) with a form `maxlength`. One reason per bulk run, on the summary entry.

## 10. Indexing

Expected queries: per target (history tab), per organisation (org log, newest first, filtered by actor/action/date), per actor, date ranges. The organisation log is the hot path.
- `(organisation, -created_at)`, or with the site key leading if other FLS site-aware indexes do that (check existing conventions).
- `(content_type, object_id, -created_at)` for per-learner and per-cohort history and for the erasure lookup.
- `(actor, -created_at)` for per-actor.
- Possibly `(organisation, action, -created_at)` for the action filter; add only if measured slow, since each index costs on write.
- Order by `-created_at, -id` for stable pagination; paginate (offset paging degrades on very large logs; keyset pagination is an option). Time partitioning (django-partitioned-audit) is unnecessary here. A BRIN index on `created_at` is a cheap option for an append-only table.
- `select_related("actor", "organisation")` on list views to avoid N+1. Generic targets render from the stored label, so no GFK prefetch is needed (a benefit of the snapshot).

## 11. Testing

- Model: `save()` on an existing row raises; `delete()` raises; `QuerySet.update()`, `.delete()`, `bulk_update()` raise; admin has no add/change/delete permission (admin client gets 403 on change/delete URLs).
- `record()`: unknown action raises; null actor allowed; label snapshot survives target deletion and actor deletion (actor FK becomes null, label retained); organisation and site set correctly; details validated and JSON-serialisable.
- Transaction: when the surrounding action raises inside `transaction.atomic`, no entry persists; an entry exists after success.
- Each writer (the six role utility TODOs, each spec 6-9 action): a test asserting action, actor, target, organisation and details, using a shared assertion helper (avoids repetition).
- Bulk: one summary entry with correct counts.
- Multi-tenancy: other site's or other organisation's entries never appear; an organisation admin cannot read another organisation's log; learners and non-staff are refused; permission matrix row for the log.
- Readers: history tab ordering and paging, filters by actor, action and date range, timezone rendering, escaping of labels containing HTML.
- Retention command: dry-run deletes nothing; deletes only older than the cutoff; writes its own summary entry.
- Erasure hook: pseudonymises labels without deleting rows.
- If a DB trigger is added: a test that a direct UPDATE through a cursor fails.

## 12. Recommendations for this FLS feature

1. **Model** `AuditLog` on the site-aware base. Fields: site (from base); `organisation` (FK nullable, SET_NULL) + stored label; `actor` (FK nullable, SET_NULL) + `actor_label`; `action` (CharField validated against a registry, no `choices=`); `content_type` FK + `object_id` (CharField) + `target_label`; `details` JSONField(default=dict); `reason` (blank, length-limited); `created_at` (timezone.now, UTC). Optionally a nullable `batch_id` (UUID) for bulk runs and a reserved nullable `on_behalf_of` for impersonation.
2. **Append-only** by three layers: custom QuerySet/manager raising on `update/delete/bulk_update`, model `save`/`delete` guards, read-only admin. A DB trigger is optional and out of scope; document it as a hardening option. One named escape hatch for the prune command and the erasure hook.
3. **Writing** through one function, `AuditLog.record(actor, action, target, organisation, reason="", details=None)`, called explicitly from the service/utility layer inside the action's `transaction.atomic`: no signals, no thread-local request user, no `on_commit`, no try/except around it.
4. **Vocabulary** as a registry of past-tense keys with labels; FLS core registered at app ready; downstream extension through a documented `register_action()` (answers the open question: yes, via registry rather than an app setting). List the vocabulary in the spec 12 developer doc.
5. **Details** limited to ids, labels, counts and source/destination; never secrets or contact details; per-action required keys validated; cap bulk per-object lists.
6. **Bulk** writes one summary entry (settled). Raise in the spec that the learner/cohort tabs will not show individual bulk effects unless child entries with a shared `batch_id` are added; decide explicitly. Two-sided actions (move, registration) must be findable from both the learner and cohort tab: choose between nullable subject references on the entry and duplicate entries.
7. **Indexes**: org+time (with site as per convention), `(content_type, object_id, -created_at)`, `(actor, -created_at)`; order `-created_at, -id`; paged; `select_related("actor","organisation")`.
8. **Retention**: keep forever by default; a prune management command (age via argument and setting, `--dry-run`, batched, writes its own summary entry), off by default. Provide an anonymise function for erasure that rewrites labels; state in the docs the GDPR position (legitimate interests, storage limitation, pseudonymise rather than delete).
9. **Scope**: webhooks and reports excluded (own records), logins excluded (axes/allauth); per OWASP those belong to the security log rather than the business audit trail.
10. **Permissions**: add the `view_audit_log` row to spec 5's matrix for site admins and organisation admins; enforce organisation scoping on every query.
11. **Tests** per section 11, with a shared assertion helper and a cross-tenant test.

## References
- OWASP Logging Cheat Sheet (fetched): https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- Auditrum (privilege-based append-only and hash chain; from search result): https://pypi.org/project/auditrum/0.5.1/
- django-postgres-audit-log (uses a GenericForeignKey): https://github.com/ljodal/django-postgres-audit-log
- django-partitioned-audit: https://pypi.org/project/django-partitioned-audit/
- Django transactions / on_commit (not re-fetched): https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit
- Django queryset update/delete semantics (not re-fetched): https://docs.djangoproject.com/en/stable/topics/db/queries/#updating-multiple-objects-at-once
- django-auditlog, django-simple-history (not re-fetched): https://django-auditlog.readthedocs.io/ , https://django-simple-history.readthedocs.io/
- GDPR Art. 17 (not re-fetched): https://gdpr-info.eu/art-17-gdpr/

status: ok
