---
requires_migrations: true
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

# Upgrade notes: educator-interface-refactor-7-cleanup

This is the last step of the educator interface code layout effort, which moved each educator area out of the flat
modules in `freedom_ls.educator_interface` into `freedom_ls.educator_interface.panels.<area>`. No behaviour, URL name,
URL path, template path or app label changed, and there is no re-export shim.

## Breaking changes

- `freedom_ls.educator_interface.actions`, `freedom_ls.educator_interface.quick_views` and
  `freedom_ls.educator_interface.reporting` no longer exist. The previous release left them holding only a docstring;
  this one deletes them, so importing them raises `ModuleNotFoundError`. `freedom_ls.educator_interface.filters` was
  already removed by `educator-interface-refactor-5-learner`.
- `freedom_ls.educator_interface.views` holds only the interface shell: `interface_config`, `interface_root`,
  `interface`, `scope_request`, `standalone_page_context` and their private helpers. It imports from the `panels`
  modules only what the shell itself uses. The names the earlier notes said "keep working for now" when imported from
  `views` do not resolve there any more; import each from the module named in the index below.
- `OrganisationScopedRequest` and `LAST_ORGANISATION_SESSION_KEY` live in
  `freedom_ls.educator_interface.panels.common.request`. `views` imports them for its own use; don't import them from
  `views`. `interface_config` stays at `freedom_ls.educator_interface.views`.

### Where each name went

Each earlier release's `upgrade_notes.md` lists, name by name, what moved from which flat module to which `panels`
module:

| Area | Notes |
| --- | --- |
| Shared helpers (`panels.common`) | `spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/upgrade_notes.md` |
| Dashboard and audit log (`panels.dashboard`, `panels.audit_log`) | `spec_dd/3. done/2026-11-20_20:03_educator-interface-refactor-2-dashboard-and-audit-log/upgrade_notes.md` |
| Staff (`panels.staff`) | `spec_dd/3. done/2026-11-21_09:55_educator-interface-refactor-3-staff/upgrade_notes.md` |
| Course (`panels.course`) | `spec_dd/3. done/2026-11-21_06:00_educator-interface-refactor-4-course/upgrade_notes.md` |
| Learner (`panels.learner`) | `spec_dd/3. done/2026-11-22_12:05_educator-interface-refactor-5-learner/upgrade_notes.md` |
| Cohort (`panels.cohort`) | `spec_dd/3. done/2026-11-23_16:10_educator-interface-refactor-6-cohort/upgrade_notes.md` |

This release adds no migration. `requires_migrations` is set because the effort's
`freedom_ls_educator_interface.0002_move_learner_bulk_runs` and `0003_move_cohort_bulk_runs` rewrite stored
`BulkActionRun.action_path` values, and a project upgrading past several of these releases at once needs them applied.

## Manual steps

- Run `uv run manage.py migrate`. If `0002_move_learner_bulk_runs` and `0003_move_cohort_bulk_runs` are already
  applied, it does nothing.
- Grep your project for `freedom_ls.educator_interface.views`, `.actions`, `.filters`, `.quick_views` and
  `.reporting`, in imports, settings, and strings passed to `mock.patch`, `monkeypatch.setattr` or `import_string`.
  Repoint each at its `panels` module using the index above. A project that only uses
  `include("freedom_ls.educator_interface.urls")` and lists the app in `INSTALLED_APPS` needs no action.
- No settings, packages, templates or Tailwind rebuild are needed.
