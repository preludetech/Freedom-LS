# Research: prior art for an audit log

Question: what has already been tried for an audit log, here in FLS or elsewhere, and what happened?

Method note: git history could not be searched (read-only tools, no Bash). The only commits seen are the five in the session's git status (the latest is `dcf91ef8 educator-interface-11-audit-log: start the spec`). Everything under "In FLS" comes from `spec_dd/` documents and the code. Web findings come from search snippets and one doc fetch, so treat details marked "snippet" as unverified against the primary page.

## 1. In FLS: nothing has ever been built

**Short answer: no audit model, view or attempt has existed.** Every earlier mention is a deferral.

### Timeline of decisions

| When | Where | What was decided |
|---|---|---|
| 2026-03-09 | `spec_dd/3. done/2026-03-09_11:26_role_based_permission_system_foundations/0. idea.md` line 65 | Out of scope: "Audit logging of permission changes (good future enhancement)". |
| 2026-03-09 | same dir, `1. spec.md` lines 213, 405-406 | `view_audit_log` ("Can view the system audit log") pencilled in as a FUTURE `system_admin` permission, commented out. Mirrored in `freedom_ls/role_based_permissions/registry.py:131` and `roles.py:134`. |
| 2026-03-09 | same dir, `1. spec.md` line 657 | A rule was written that "All role assignment and removal goes through utility functions that sync permissions and write audit logs". The implementation synced but did not write the logs. The six TODOs are the gap. |
| 2026-03-09 | same dir, `2. plan.md` lines 280, 286 | Plan said "Keep TODO comment for AuditLog". This is when the `# TODO: AuditLog entry ...` comments were added: as placeholders alongside the first role utilities, deferred because the idea excluded audit logging. The `research_common_complaints.md` (line 158) had flagged missing audit trails for permission changes as a common complaint. |
| 2026-10-01 | `3. done/2026-10-01_22:00_educator-interface-5-permissions/` (`idea.md` 68 and 126, `1. spec.md` 36 and 64, `2. plan.md` 658-660) | Spec 5 explicitly excluded the audit log ("spec 11 adds the audit log row" to the capability matrix) and told the implementer to keep the `TODO: AuditLog` comment while adding the last-site-admin guard to `remove_site_role`. Its `research_permission_ux_patterns.md` line 170 only recommends "Show who assigned a role and when". |
| 2026-10 | `1. next/educator-interface-full-polish/comparable-systems-learner-management.md` section 4 (lines 102-129) and section 6 item 2 (lines 162-166) | Five of seven comparable systems have a staff-readable log. Minimum fields: actor, action, target, organisation, time, optional reason on removals. Where it is shown was left as "a separate question". |
| 2026-10-22 | `3. done/2026-10-22_11:25_educator-interface-9-educator-administration/` `research_codebase.md` lines 98-99 and 291; `research_reference_implementations.md` lines 77 and 96 | Confirmed: `grep AuditLog` finds only the six TODOs. `assigned_by` records only the granter, not the remover, so "who removed it and when" needs the log. Spec 9's strings are to be consumed by spec 11. Keep the TODOs. |
| 2026-10 | `1. next/roadmap.md` lines 81 and 108 | Decision 3: "An audit log is in scope, as spec 11, after the actions it records exist." Open question "Audit log retention" is assigned to spec 11 with no later owner. |
| 2026-10-23 | `3. done/...registration-rules/research_prior_art.md` line 60; roadmap line 438 | Registration rules want an audit trail of rule actions. Rule actions appear in the log "if spec 11 has landed". `deadlines-6-educator-management` also depends on spec 11 (roadmap lines 516, 526). |

So there are at least two downstream consumers (registration rules, deadlines 6) beyond specs 6 to 9. The vocabulary will be extended by later specs, which bears on the open question about extending it.

### The six TODOs (`freedom_ls/role_based_permissions/utils.py`)

- Lines 271, 294: object role assign and remove.
- Lines 328, 373: site role assign and remove.
- Lines 399, 417: system role assign and remove.
- Remove functions already accept `removed_by` (docstring at 346 says "for future audit logging"), so the actor parameter is plumbed. Assign functions take `assigned_by`.
- `remove_object_role` and `remove_system_role` use a bare `.update(is_active=False)` with no row check, so a call that removes nothing (already inactive, or never held) would still log unless the writer checks the update count. `assign_*` returns an existing row on a repeat call, so a repeat assign would also log unless it checks `created` or a changed field. Idempotent writers need a "did anything change" rule. (Inference from the code, not a recorded decision.)
- `remove_site_role` already runs in `transaction.atomic()`; the others do not. "Write inside the action's transaction" means those need wrapping.

### Existing audit-shaped records (not a log)

- `LegalConsent` (`freedom_ls/accounts/models.py:174`): the precedent in-repo for append-only. Rejects updates in `save`, fully read-only in admin, site-aware. Reuse this pattern. Nothing mentions rejecting deletes on the model itself.
- `WebhookEvent` / `WebhookDelivery` (`freedom_ls/webhooks/models.py:376-391`): event type, payload, created_at. Admin has add, change and delete disabled. Cover only webhook event types. `research_deletion_semantics.md` section 5 (`3. done/2026-08-30_08:06_final_pre_deploy_db_structure_cleanup/`) found that deleting a `WebhookEndpoint` cascaded away every delivery record, "the entire audit trail for that endpoint". Lesson in-repo: do not let audit evidence die with its subject. It proposed `SET_NULL` plus denormalising the URL, which is the same reasoning as the idea's "stored label so the entry reads after the target is gone".
- `assigned_by` on the three role assignment models (`role_based_permissions/models.py:23, 57, 99`): granter only. Overwritten by `_refresh_assignment` when a role is re-granted, so history of earlier granters is lost.
- `ApplicationStateTransition` (`course_applications/models.py`, mentioned in `views.py:135`): an existing per-domain transition row, the nearest in-repo pattern for an event table. Not general.
- Security audit research (`3. done/2026-03-13_21:21_security-audit/`): `research_iso27001.md` section 2.9 lists fields per event (user, description, UTC time, device, IP) and says permission changes and administrative actions must be logged, tamper-protected, and suggests django-auditlog or simple-history. `research_gdpr.md` pattern 4 sketches a `DataAccessLog` (SET_NULL users, resource type and id, timestamp, IP) and line 159 recommends configured retention with automatic purge. `research_popia.md` line 65: an LMS should provide audit logs and consent records to help the deploying organisation show compliance. These support the idea but also raise IP address and personal-data retention, which the idea does not mention.
- `spec_dd/corporate-readiness/research_procurement.md` line 15: "Audit logs (immutable, exportable)" is a hard requirement, often scored in RFPs, for corporate buyers. Exportable is not in the idea (CSV via spec 2's table may cover it).
- `webhook-translation-layer/research_admin_ux.md` line 517: note to mask secrets in audit trails. Relevant to what goes in the JSON details field (never log tokens or secrets).

### What was deferred and why

1. Audit logging of permission changes: deferred in March as a "good future enhancement", to keep the role foundation small.
2. The log in spec 5: deferred so the matrix and checks could ship without a model.
3. The model in each of specs 6 to 9: deferred by the product owner to one spec so 6 to 9 could run in parallel.
4. Retention: deferred to spec 11 with no research yet.

## 2. Comparable systems (from the existing FLS note, plus new web checks)

From `comparable-systems-learner-management.md`:
- Docebo Audit Trail: immutable, who (including the impersonator), what, when. Retention not found.
- Google Classroom log: Admin console, filterable, default last 7 days, BigQuery export on paid tiers.
- TalentLMS Timeline: nearly every event, filterable by event type, date, user, course; CSV export.
- Moodle: logs report and logstore. Open edX: tracking log plus `ManualEnrollmentAudit`. Canvas: both users logged on masquerade; "Admin Tools" logging. LearnDash: none found.
- Nobody offers undo. Reversibility comes from flags, not the log. Matches the idea's out-of-scope line.

## 3. Elsewhere: what went wrong and what was learnt

### 3.1 Django ecosystem

**django-auditlog** (docs: https://django-auditlog.readthedocs.io/en/latest/usage.html, fetched).
- Signal-based automatic logging. Docs do not say whether `bulk_create` or `bulk_update` are logged (signals do not fire for them); verify yourself. Lesson: signal-based logging silently misses bulk paths. FLS's plan to write explicit entries from the action code and a summary entry for bulk runs avoids this.
- Actor attribution via middleware: every change in a request is attributed to the current user, and system-initiated changes need manual logging. Lesson: take the actor explicitly (as the role utilities' `assigned_by` and `removed_by` already do) rather than from thread-local state.
- Many-to-many changes create one entry per add or delete, so one form save can create several entries. Lesson: define one entry per user-meaningful action.
- Storing full serialized state is optional and heavy; JSON "changes" are stored per entry. Lesson: keep the details field small and specific, as the idea does.
- Retention: `auditlogflush` with `--before-date` (permanent deletion). Same shape as the idea's prune command. Docs warn it cannot be reversed.
- `mask_fields` exists because secrets leaked into change records. Lesson: allow-list what goes in details.
- FK string representation option "reintroduces known issues": entries created when nothing changed, missed updates. Lesson for the stored target label: it is a snapshot at write time, not a live string.
- Search did not surface specific performance issues from its GitHub tracker. That gap remains open.

**django-simple-history** (https://django-simple-history.readthedocs.io/en/stable/ , snippet).
- Every `save()` writes a history row even with no change, so tables inflate; shipped `clean_duplicate_history` to repair it. Retention via `clean_old_history --days N` (default 30). Bulk helpers (`bulk_create_with_history`) exist because bulk bypasses signals, and an N+1 in the helper was fixed in 3.2.0. Lesson: no-op writes and bulk paths are the two recurring problems. It mirrors every model with a second table and migrations that must be kept in step with the source model; this is the cost the idea avoids by choosing one small model.

**Django admin `LogEntry`** (https://code.djangoproject.com/ticket/37287 , ticket proposing an index on `action_time`; snippet).
- Table reaches millions of rows; "Recent actions" query becomes a sequential scan because `action_time` is unindexed.
- Generic foreign keys are not indexed by default. Django tickets https://code.djangoproject.com/ticket/30122 and https://code.djangoproject.com/ticket/26964 (docs request) concern a composite `(content_type, object_id)` index. Blender ID's deployment docs (https://docs.blender.org/id/deployment) report the admin log slowing at hundreds of thousands of rows and added the composite index by hand outside migrations. Earlier attempts to index `object_id` stalled because it was a TextField, which MySQL cannot index unbounded.
- Lesson for FLS: declare the indexes in the model's `Meta` from day one: `(organisation, -when)`, `(content_type, object_id, -when)` for the per-learner and per-cohort tabs, and `(actor, -when)`. Use a bounded `CharField` for the target key (FLS uses string `object_id` for roles already). FLS is on PostgreSQL, so the MySQL limit does not apply.

### 3.2 Moodle

Sources (tracker and forum snippets): https://tracker-old.moodle.org/browse/MDL-53795 (missing index on `logstore_standard_log`, slow backups with about 145M rows), https://tracker-old.moodle.org/browse/MDL-53869 (participation report not using an index, index added), https://tracker-old.moodle.org/browse/MDL-11901 (reads on a large log table block inserts, slowing nearly every page view), https://moodle.org/mod/forum/discuss.php?d=311248 (18 GB standard log table, module pages taking up to 3 minutes), https://moodle.org/mod/forum/discuss.php?d=384451 (prune old rows then `OPTIMIZE TABLE`, both hurt the site while running), https://moodle.org/mod/forum/discuss.php?d=259072 (legacy log moved out of the main database in 2.7; the new table's definition differs so some legacy fields do not carry over).
- The legacy `mdl_log` logged every page view into the transactional database. Moodle moved to pluggable log stores (`logstore_standard`, with an option to send logs elsewhere) and an events API, so logging is a defined set of named events rather than free text.
- Even the new store needed indexes added years later, and pruning was a manual, disruptive job. Lesson: set retention and indexes up front, and prune in batches.
- The current official guidance on the legacy log was not confirmed by search. The idea's scope (staff actions only, no page views, no learner activity) avoids the volume problem entirely. Keep this scope fence explicit in the spec: webhook deliveries and report generations stay out, as the idea defaults.
- Moodle's fixed event names are the model for the idea's fixed vocabulary.

### 3.3 GitLab audit events

Sources (snippets): https://gitlab.com/groups/gitlab-org/-/epics/3206 (partitioning strategy for audit events), https://gitlab.com/gitlab-org/gitlab/issues/7865 (partition by year on `created_at`), https://gitlab.com/gitlab-org/gitlab/-/merge_requests/36298/commits (migration creating a partitioned copy with monthly partitions), https://gitlab.com/gitlab-org/gitlab/-/merge_requests/239886 (`ai_audit_events`: both tables grow unbounded; the MR makes no retention or schema change until size is measured).
- `audit_events` grew large enough to need date-range partitioning, retrofitted with a background migration and a table swap. It was the first partitioned table in their app database, and a UI change to encourage time-bounded queries was a listed blocker.
- Streaming of audit events was released behind a feature flag for performance concerns.
- Lesson: audit tables grow forever by default, and retrofitting partitioning is a large project. Users query by time window, so a date filter default (Google defaults to 7 days) keeps the reader fast. FLS volumes (staff actions in one organisation) are far lower; plain indexes plus a prune command are adequate. Do not design partitioning now, but keep `when` indexed and require a bounded date or page in every reader.
- The completion state of the epic and any current retention policy were not confirmed.

### 3.4 Open edX `ManualEnrollmentAudit`

Sources (snippets of fork mirrors, not upstream): https://git.andalsoftware.com/Andal.LND/edx-platform/commit/a7ed319d58b17bc8ed698f462f6b28b7b7f13d92 (audit creation API), https://git.andalsoftware.com/Andal.LND/edx-platform/commit/ec79aeca44f355affaf981762b3e1ecfae960202 (manual enrollment app API), https://git.andalsoftware.com/Andal.LND/edx-platform/commit/e3b0bffa503f7942b9e3aa31b3eee0be293b0dec (revert of a field removal).
- Fields: acting user, target email, `state_transition` (a fixed set: enrolled to enrolled, enrolled to unenrolled, unenrolled to enrolled, unenrolled to allowed-to-enroll, allowed-to-enroll to enrolled), `reason`, link to the enrollment, and `role`. The helper validates the role and transition against allowed constants and raises `ValueError`.
- Stores the email, not only a user link, so the entry makes sense for people with no account yet. Same idea as FLS's stored target label.
- It records enrolment only, not staff role changes (the FLS spec 9 research flagged this as unverified).
- The `role` argument was removed from the instructor dashboard and then restored by a revert, so a field added to an audit record becomes load-bearing for integrators quickly. Lesson: settle the field list before shipping; adding is cheaper than removing.
- Reason is free text and optional in the UI for most paths. The FLS idea follows this.

## 4. Lessons mapped to the idea

| Lesson | Source | Bearing on spec 11 |
|---|---|---|
| Signals miss bulk paths; explicit writes do not. | auditlog, simple-history | Keep explicit writer calls; add a test that every action in the matrix writes an entry (a completeness test like spec 5's). |
| No-op writes bloat tables. | simple-history | Writers log only on real change; decide for repeat assign and remove calls. |
| Generic FK needs a composite index declared in the model. | Django tickets, Blender ID | Add indexes in the first migration. Use a bounded string key. |
| Retention is always retrofitted; prune is disruptive. | Moodle, GitLab | Ship the prune command now, batch the deletes, document the default of keep everything. |
| Evidence dies with its subject. | FLS webhook CASCADE finding, edX stores email | Stored label, `SET_NULL` on actor, no cascade from user or target deletion. Decide what GDPR deletion of a `User` does to actor and label text (open). |
| Secrets and personal data leak into details. | auditlog `mask_fields`, ISO and GDPR notes | Allow-list the JSON keys per action; no IP or tokens unless a decision says so. |
| Fields become load-bearing. | edX revert | Fix the field list and vocabulary before downstream specs (registration rules, deadlines 6) consume them. |
| Scope creep (page views, field diffs) causes the volume problem. | Moodle | Keep the idea's out-of-scope list. |

## 5. Gaps and questions for the spec

- Git history was not checked. Confirm with `git log --all -S AuditLog` that no abandoned branch exists.
- No django-auditlog or simple-history GitHub issue threads on performance were retrieved; claims about them come from docs and adjacent Django tickets.
- Does append-only need to block queryset `delete()` and `update()` (a custom manager) as well as `save()` on existing rows? `LegalConsent` blocks only updates in `save`.
- What happens to rows when the actor or a target `User` is hard-deleted for GDPR (the roadmap leaves hard deletion to the Django admin)? Actor is nullable, the stored label may hold a name or email.
- Idempotent writers (see section 1) and wrapping the non-atomic role utilities.
- Whether "exportable" (a procurement requirement) is met by spec 2's CSV export on the organisation log.
- Vocabulary extension by downstream projects and by later specs (registration rules, deadlines 6).

status: ok
