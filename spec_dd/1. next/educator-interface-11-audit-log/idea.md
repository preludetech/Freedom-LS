# Audit log

Spec 11 of 12 in the educator interface rebuild. Read `../educator-interface-full-polish/spec-order.md` first. Depends on specs 6, 7 and 9. Runs alone after them.

## What

A staff-readable record of who did what to whom in an organisation. One append-only model. Every action in the educator interface writes to it, the role utilities write to it, and it is shown per organisation, per learner and per cohort.

## Why

Five of the seven comparable systems have one, and the earlier permission research recommended it. FLS has none. The role assignment utilities carry six `# TODO: AuditLog entry` comments, `system_admin` has a `view_audit_log` permission pencilled in as future, and the only audit-shaped records are `LegalConsent`, `WebhookEvent` and the `assigned_by` fields. Once organisation staff can deactivate learners and remove educators from a screen, "who did this" is a question someone will ask.

The product owner chose to build this as its own spec after the actions exist, rather than fold a model into each of specs 6 to 9, so those specs could run in parallel without sharing a model.

## What is settled

**The model.** Site-aware, append-only, no update or delete through the ORM in application code. Fields: actor (user, nullable for system actions), action (a short string from a fixed vocabulary), target (generic key plus a stored label so the entry reads after the target is gone), organisation, when, and an optional reason. A small JSON field for details such as the source and destination cohort of a move, or the counts of a bulk run. No third-party history package; the vocabulary and the reading surface are FLS-specific and the model is small.

**Vocabulary.** One entry per capability in the spec 5 matrix, named in the past tense (learner added, learner deactivated, membership moved, registration deactivated, role granted, role removed, cohort deactivated, import committed). The strings are the ones the product docs and the UI use.

**Reason.** Optional everywhere, prompted for on removals and deactivations, following Open edX. Never required.

**Writers.** The role utilities close their TODOs. Every action in specs 6 to 9 writes one entry per object, and a bulk run writes one summary entry with the per-object detail in the JSON field. Writing happens inside the action's transaction.

**Readers.** A history tab on the learner and cohort detail pages (spec 7 left the slot), newest first, paged. An organisation-level log as a section, filterable by actor, action and date, through spec 2's table. Spec 5's matrix says who reads it: site admins and organisation staff.

**Retention.** Decided in the spec. Default: keep everything; add a management command to prune older than a configurable age, not run by default.

**Docs.** A short "History" section in `docs/product/educator-interface.md`, and the vocabulary listed in the developer doc from spec 12 so a downstream project can write its own entries.

## Open until the spec

- Retention, above.
- Whether webhook deliveries or report generations belong in the log. Default no; they have their own records.
- Whether a downstream project can extend the vocabulary through an app setting.

## Out of scope

- Field-level change tracking, undo, or restoring from the log.
- Anything learner-facing.
- Login and authentication events; `django-axes` and allauth cover those.

## Resources

- `../educator-interface-full-polish/comparable-systems-learner-management.md`, section 4 and the per-system audit notes.
- `../educator-interface-5-permissions/research_permission_ux_patterns.md`, the audit recommendation.
- Skills: `fls-dev:multi-tenant`, `fls-dev:admin-interface` (read-only admin for the model), `fls-dev:testing`.
