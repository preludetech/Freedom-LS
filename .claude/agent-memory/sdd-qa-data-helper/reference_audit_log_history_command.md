---
name: audit log history seed command
description: qa_create_audit_log_history seeds learner/cohort History tabs + org Audit log (bulk run with "and N more", system actor, deleted actor); entries are append-only so it runs once
type: reference
---
`uv run python manage.py qa_create_audit_log_history [--organisation-slug demodev]` (Nov 2026, design_educator_interface_audit_log).

- Uses real services (add_to_cohort, move_between_cohorts, remove_from_cohort, deactivate_learner,
  reactivate_learner(actor=None) = the "system" entry); setup_email_resent + bulk per-object entries
  + record_run_summary go through the writer. No production code writes bulk summaries yet
  (record_run_summary has no non-test caller), so the writer is the only way.
- AuditLogEntry is append-only: .delete()/.update() raise AppendOnlyError; only
  `AuditLogEntry.unscoped.prune_before(cutoff)` deletes. So the command refuses to re-run when
  "Audit QA Cohort" exists.
- Deleted actor: write an entry with the user as actor, then `user.delete()` -> actor NULL,
  actor_label kept (fresh user cascades only its EmailAddress).
- Cohort History tab = entries whose `subjects` contain the cohort key; the run SUMMARY's subjects
  are only the organisation, so the cohort tab shows the 56 per-object rows ungrouped, never the
  summary / "and N more" (that is on /educator/organisations/<slug>/audit-log only). page_size 25.
- Render check: Client(HTTP_HOST='127.0.0.1:8000') + force_login demodev@; tab URLs need HX-Request.
