---
name: reference-in-progress-learner-import
description: Staging a LearnerImport frozen in RUNNING (300 rows / 120 processed) so the import result page shows the polling progress bar; no factory exists, no task is enqueued
metadata:
  type: reference
---

Nov 2026, educator-interface-design-learner-csv-upload-design-fix.
- LearnerImport (learner_management/models.py) has NO factory; tests use LearnerImport.objects.create. Pass site= explicitly.
- Result view only finds imports where requested_by == request.user AND organisation == URL org (else 404).
- in_progress = status not in (done, failed); percentage = processed_count*100//row_count. PREVIEWED redirects to preview.
- Creating the row directly enqueues nothing, so it stays frozen. Only `housekeeping` sweeps (_close_as_failed for unpicked/orphaned runs) could flip it to failed if run.
- Script: `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_running_learner_import_script.py` (NOT idempotent: creates a new import each run; file_name qa-in-progress-300.csv).
- Verify render: Client(HTTP_HOST='127.0.0.1:8000') + force_login inside transaction.atomic()+raise.
If asked again, wrap as a qa_helpers command with --status/--rows/--processed.
- Run log: 962e2d06 (1st run), b0a8013a-f296-486a-a209-17ab55684f0e (2nd run, 4 Nov 2026; started_at=now, script changed from now-1min).
  Earlier running imports pile up because the script is not idempotent. Never touch the old ones unless asked; give the tester the NEW pk.
  The "mark it done" follow-up: `assert` status==running, then update(status=DONE, processed_count=row_count, finished_at=now) + set final_label on the unprocessed rows. Done and verified for b0a8013a: the page reads "Added 300 learners" / "New account 300" / "300 setup emails were sent" using the row labels only, so no User accounts are needed.

## Staging a FAILED import + an other-org educator (Nov 2026, same branch)
- Failed: pick a PREVIEWED import with addable preview labels, `assert` status, then
  `queryset.update(status=FAILED, error_message=..., processed_count=0, started_at=now, finished_at=now)`.
- "Staff who can't see demodev": `qa_create_single_org_educator --organisation-slug <other> --email X --password X`
  (`--password` added Nov 2026). Create the other org first with OrganisationFactory(site=site, slug=...).
  The ORA post_save makes an OrganisationMember on that other org only. is_staff is irrelevant to the educator UI.
- Every demodev import URL (upload/preview/result) 404s for a non-demodev educator (scope_request).
- BULK_BACKGROUND_THRESHOLD lives in freedom_ls/panel_framework/config.py (AppSettings, default 250,
  read from Django settings by name; no env var, not set in config/settings_*.py).

## Round 3 (6 Nov 2026): REUSE rather than re-create
- Asked again for RUNNING + FAILED imports: reused 962e2d06 (running 300/120, still frozen) and
  38d52845 (failed, "Something broke.", 3 rows, started/finished set). Check they're still in state before creating new ones.
- Cohort admin persona: `qa_create_single_org_educator --cohort-name "<cohort>"` (option added this round)
  grants cohort_admin on that cohort instead of organisation_admin. Made qa-cohortadmin-r1106@example.com on
  demodev "Cohort 2025.04.06" (testpass123). Other-org staff = qa-otherstaff-r1105@example.com (qa-other-org), password reset to testpass123.
- Non-member user: import `_ensure_user`/`_ensure_consents` from that command inside `_site_context`; made qa-joiner-r1106@example.com (testpass123), no Learner/StaffMember/ORA.
- Org membership models are learner_management.Learner / StaffMember (no OrganisationMember class).
