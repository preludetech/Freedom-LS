---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-refactor-2-dashboard-and-audit-log

## Breaking changes

The educator dashboard and audit log code moved out of the flat `freedom_ls.educator_interface` modules into two
panel areas. No behaviour, URL, template path, stored value or app label changed, and there is no re-export shim.
A downstream project that imports one of these names from its old module must switch to the new one.

From `freedom_ls.educator_interface.reporting` to `freedom_ls.educator_interface.panels.dashboard.panels`:

- `InlineFigures`, `CohortFlags`, `FlaggedLearnerRow`, `CohortProgressRow`, `ExcludedCohort`, `GatheredFigures`
- `visible_active_cohorts`, `inline_figures`, `gathered_figures`
- `DashboardPanel`
- private helpers `_gather_visible`, `_average_progress`, `_flagged_learner_rows`, `_cohort_rows`

From `freedom_ls.educator_interface.views`:

- `DashboardConfig` → `freedom_ls.educator_interface.panels.dashboard.config`
- `AuditLogConfig` → `freedom_ls.educator_interface.panels.audit_log.config`
- `AuditLogEntryTable`, `TargetedAuditLogEntryTable`, `OrganisationAuditLogTable` →
  `freedom_ls.educator_interface.panels.audit_log.data_tables`
- private helpers `_attach_people`, `_export_when`, `_export_who`, `_export_run_id`, `_record_export` →
  `freedom_ls.educator_interface.panels.audit_log.data_tables`
- `HistoryPanel` → `freedom_ls.educator_interface.panels.audit_log.data_table_panels`

From `freedom_ls.educator_interface.filters` to `freedom_ls.educator_interface.panels.audit_log.filters`:

- `AuditActorFilter`, `AuditActionFilter`

`views.py` still imports `DashboardConfig`, `AuditLogConfig`, `HistoryPanel` and `TargetedAuditLogEntryTable` for
its own use, so `from freedom_ls.educator_interface.views import HistoryPanel` keeps working for now. Don't rely on
it: a later cleanup trims those imports. Import from the new modules.

Underscore-prefixed names are not public API. They moved with the same spelling, but may change without notice.

## Manual steps

- Grep your project for each old dotted path above, including strings passed to `mock.patch`. A patch target
  must name the module that looks the name up. A stale string on `views` or `reporting` can still resolve and
  then patch nothing, so tests pass without patching what they meant to.
- No migrations, settings, packages or Tailwind rebuild are needed.
