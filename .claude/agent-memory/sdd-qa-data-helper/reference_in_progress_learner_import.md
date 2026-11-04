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
