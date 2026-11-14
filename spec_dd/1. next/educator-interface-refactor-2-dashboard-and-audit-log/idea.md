# Move the dashboard and audit log areas into `panels/`

Spec 2 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Move two areas of `freedom_ls/educator_interface/` into the `panels/` package that `educator-interface-refactor-1-scaffolding-and-common` created.

- The dashboard area goes to `panels/dashboard/`: its config, its panel and the dashboard half of `reporting.py`.
- The audit log area goes to `panels/audit_log/`: its config, its data tables, `HistoryPanel` and its audit filters.

The tests for both move with the code to `tests/panels/dashboard/` and `tests/panels/audit_log/`. It is a pure move. Nothing about behaviour, URLs, templates or the database changes.

## Why

`views.py` is 3376 lines and `reporting.py` is a mix of three areas. These two areas are small and have no dependency on each other or on learner, cohort, course or staff code. They depend only on `panels/common/`. That makes them the cheapest areas to move and a good proof of the layout before the larger areas follow. The audit log tables are also the base of the History tabs on the learner and cohort pages, so moving them early gives those later specs a stable import target.

## What is settled

Line ranges below are main's, before `extract_panels_framework-1-gather-generic-code` lands. That spec changes `reporting.py`, `filters.py` and `views.py` imports. Re-check every range against the tree when the spec is written. Move by class name, not by line number.

**Dashboard, to `panels/dashboard/`:**
- `config.py` takes `DashboardConfig` (`views.py` 2436-2441).
- `panels.py` takes `DashboardPanel` and everything in `reporting.py` from `InlineFigures` through `gathered_figures` (`reporting.py` 332-560). It imports `LazyBodyPanel` and `render_region` from `panels/common/report.py`, not from `reporting.py`.
- The tests move from `tests/test_dashboard.py` to `tests/panels/dashboard/test_panels.py`, and any test of `DashboardConfig` goes to `tests/panels/dashboard/test_config.py`. Any dashboard test inside `tests/test_reporting.py` moves to `test_panels.py` too. Today there are only two mentions of the dashboard in that file, so check whether it has any.
- `LearnerCoursesPanel`, the cohort report classes and the shared report helpers stay in `reporting.py`. They belong to siblings.

**Audit log, to `panels/audit_log/`:**
- `config.py` takes `AuditLogConfig` (`views.py` 2639-2671).
- `data_tables.py` takes `_PERSON_TARGETS`, `_attach_target_users`, the `_export_when/who/run_id` helpers, `AuditLogEntryTable`, `TargetedAuditLogEntryTable`, `_record_export` (`views.py` 835-1030) and `OrganisationAuditLogTable` (2592-2638).
- `data_table_panels.py` takes `HistoryPanel` (1031-1075).
- `filters.py` takes `AuditActorFilter`, `AuditActionFilter` and `AuditPeriodFilter` (`filters.py` 206-293 on main). After `extract_panels_framework-1-gather-generic-code`, `AuditPeriodFilter` may be a subclass of the framework's `PeriodFilter`. Move whatever audit filter classes remain in `educator_interface/filters.py`.
- `LearnerHistoryPanel` and `CohortHistoryPanel` are not moved. They subclass `HistoryPanel` and belong to the learner and cohort areas. This spec only repoints their `HistoryPanel` import to `panels/audit_log/data_table_panels.py`.
- `TargetedAuditLogEntryTable` is also drawn by the cohort History panel. The same repointing rule applies to any sibling code that imports it.

**Tests for the audit log area:**
- The audit slices of `tests/test_views.py` (about 4044-4570 and 7317-7680 on main: the organisation log, its filters and the export) move to `tests/panels/audit_log/test_data_tables.py` and `test_data_table_panels.py`, split by the module each test exercises. The `AuditLogConfig` tests go to `test_config.py`.
- The audit filter tests (from `tests/test_filters.py`, from `audit_request` at about line 557 to the end of the file) move to `tests/panels/audit_log/test_filters.py`. The other filter tests stay for siblings.
- `tests/playwright/test_audit_log_flow.py` stays where it is.
- Each test directory has an empty `__init__.py`. A test file is created only alongside the module it mirrors.
- Each moved test removes only its own range, so the parallel specs conflict only mechanically on `test_views.py` and `test_filters.py`.

**References to repoint (clean break, no re-export shim):**
- Every import of the moved names in `views.py`, `reporting.py`, `filters.py` and `urls.py`-adjacent code. `views.py` imports `DashboardConfig` and `AuditLogConfig` for `interface_config`. Repoint those two imports to the new `config.py` modules.
- Every `mock.patch` or `monkeypatch` string and every `educator_views.<Name>` attribute access that names a moved class. This includes the `educator_views.*` tuple in `test_views.py` (about 7089-7109), which lists the audit tables and `HistoryPanel`. Patch the module where the name is looked up, not where it is defined, and run the tests: an attribute patch on the wrong module fails silently.
- The `OrganisationScopedRequest` references the moved code needs resolve to `panels/common/request.py`.
- `test_organisation/mirroring_baseline.txt`: drop the lines for any baselined test file that moves (`test_dashboard.py` is one) in the same change. The checker fails on stale lines.

**Database:**
- No migration. None of the moved classes is registered with `@register_bulk_action`, so no stored `BulkActionRun.action_path` changes. The upgrade notes do not set `requires_migrations`.

**Module rules:**
- Both `__init__.py` files are empty. Neither area imports a sibling area.

## Open until the spec

- Whether `test_reporting.py` holds any dashboard tests at all. The spec reads it and splits only what exists.
- Whether `AuditLogConfig` or `DashboardConfig` is covered by tests that sit inside shell-level tests (`test_interface_urls.py`, `test_sidebar.py`). If so, those stay and only their imports change.
- The final ranges, once the blocking specs have landed.

## Out of scope

- Any behaviour, UI, URL or template change.
- The learner, cohort, course and staff areas, including `LearnerHistoryPanel`, `CohortHistoryPanel` and the report panels in `reporting.py`.
- The flat domain modules (`forms.py`, `staff.py`, `learner_import.py`, `messaging.py`).
- Deleting the emptied flat modules, trimming `views.py`, and updating `urls.py`, `templatetags`, `qa_helpers`, fls-dev docs and test baselines. `educator-interface-refactor-7-cleanup` owns these.
- The `panels/common/` content. `educator-interface-refactor-1-scaffolding-and-common` owns it.

## Resources

- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`: sections 1.1 and 1.3 (line ranges), 3 (target tree), 4 (test split), 5 (references), 6 (Option A).
- `spec_dd/1. next/educator-interface-refactor/research_collisions.md`: what `extract_panels_framework-1-gather-generic-code` changes, and the parallel-spec collision rules.
- `spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`: who imports the moved modules.
- `spec_dd/1. next/educator-interface-refactor/idea.md`: the owner's original brief.
