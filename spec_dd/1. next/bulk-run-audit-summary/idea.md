A bulk action in the educator interface writes one audit-log entry per changed object and nothing else. Registering three learners for a course shows as three unrelated rows in the organisation's Audit log. The audit-log spec (`spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/1. spec.md`, decision 3 and the "Spec 8" paragraph under Documentation) says a bulk run writes an entry per changed object plus one `bulk_action.completed` summary, all sharing a `run_id`. The Audit log then shows the summary row with the per-object entries folded under "Show N entries". It also puts an optional reason input in the bulk confirmation. Neither was built: `audit_log.writer.record_run_summary` exists, but only the `qa_create_audit_log_history` seed command calls it.

## Where it goes wrong today

- `RecordedBulkAction.execute` (`freedom_ls/panel_framework/bulk_actions.py`) creates a `BulkActionRun` and calls `run_bulk_action` (`bulk_runs.py`). The run's pk would make a natural shared `run_id`.
- The framework's only after-run hook is `RecordedBulkAction.on_finished(run)`, and it fires for background runs only (`report_finished`). Runs at or under `BULK_BACKGROUND_THRESHOLD` finish inline and have no hook.
- The per-object writers in `learner_management` (`register_for_course`, `deactivate_learner` and similar) take no `run_id`. The `PermittedBulkAction.perform` subclasses in `educator_interface/actions.py` call them.
- The bulk confirmation has no reason input. The eight single-object dialogs have one (`EducatorReasonForm`).

## Proposed direction

- Add a generic `after_run(run, result)` hook on `RecordedBulkAction`, a no-op by default, called from `run_bulk_action` once a run closes, inline and background alike. The panel framework must not import FLS's `audit_log` (an import guard enforces this), so the hook stays generic and FLS overrides it.
- FLS's bulk actions (or a small mixin in `educator_interface`) override `after_run` to call `record_run_summary` with the run's pk as `run_id`.
- Thread an optional `run_id` through the `learner_management` writers, so each per-object entry carries it. A background worker has no request, so it cannot come from the request.
- Add an optional reason to the bulk confirmation. The framework offers a generic hook for it (for example a `reason_form_class` on the action), and the reason is stored on the run so a background task can read it. It is written once on the summary and on every per-object entry.

## What is still open

- A method hook, or a framework signal (`bulk_run_finished`)? The framework already uses overridable action hooks (`on_finished`, `on_result_shown`), so a method hook is the likely choice.
- Where the reason lives on the run: in `BulkActionRun.target`, or a new field with a migration.
- Whether the learner's History shows the per-object entry alone or also links to the run summary.

## Out of scope

- Run summaries for registration-rule reconciles. `audit-log-coverage-gaps` covers those.
