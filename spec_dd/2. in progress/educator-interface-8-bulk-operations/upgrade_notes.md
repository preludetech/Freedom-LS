---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_message.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_bulk_confirmation_base.html
requires_settings_change: true
changed_settings:
  - BULK_BACKGROUND_THRESHOLD  # optional: default 250; read by panel_framework's config
  - LEARNER_IMPORT_MAX_ROWS  # optional: default 2000
  - BULK_RECORD_RETENTION_DAYS  # optional: default 30
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-8-bulk-operations

## Breaking changes

The `BulkAction` API in `freedom_ls/panel_framework/bulk_actions.py` changed. This affects any
project that defines its own `BulkAction` subclass:

- `execute(request, queryset)` is now `execute(request, queryset, cleaned_data)` and returns a
  `BulkResult` (or a `BackgroundRun` when the work moves to a task) instead of `None`. The default
  `execute` calls `run_apply`, which calls the new per-object `apply(user, obj, cleaned_data)` and
  returns a `BulkOutcome` for each object. Move per-row logic into `apply` and drop the `execute`
  override where you can.
- `Selection.query_string` is gone. The `all_matching` selection mode is now resolved: it means
  every row the table's current search and filters match, across every page, minus `excluded`. An
  action that only expected `keys` mode can now receive a whole filtered table, bounded by
  `max_rows` unless the action's `runs_in_background(count)` says a task does the work.
- `classify_all(user, queryset, cleaned_data)` is now `classify_all(request, queryset,
  cleaned_data)`: it only ever runs inside a request, so it gets the whole request rather than
  the user alone. `apply(user, obj, cleaned_data)` is unchanged, since a background task calls it
  with no request.

`educator_interface/interface.html` now only extends the new `educator_interface/_shell.html`; the
sidebar, content header and breadcrumbs blocks moved there. A project that overrides
`interface.html` should move those overrides to `_shell.html`.

## Manual steps

- Run `manage.py migrate`. It applies `learner_management` migrations `0008_bulkactionrun`,
  `0009_learnerimport_learnerimportrow` and `0010_delete_bulkactionrun`, and `panel_framework`'s
  first migration, `0001_initial`. The bulk run record now belongs to `panel_framework`, with a
  generic scope in place of an organisation field; no shipped data moves, since the model never
  reached a release under `learner_management`.
- A project with its own panel-framework host can record and poll bulk runs by extending
  `RecordedBulkAction` (`freedom_ls/panel_framework/bulk_actions.py`); the status route
  `<table url>/__runs/<uuid>` is served by the framework dispatcher.
- Bulk actions over more than `BULK_BACKGROUND_THRESHOLD` objects, and learner imports above it,
  run as background tasks. They need the `db_worker` process the production `TASKS` setting already
  requires. Without a worker those runs stay queued until `fls_run_housekeeping` marks them failed.
- Keep `fls_run_housekeeping` scheduled. It now also deletes unconfirmed learner import previews
  after 24 hours, fails bulk runs and imports no worker picked up or that were orphaned in RUNNING,
  and deletes finished ones after `BULK_RECORD_RETENTION_DAYS`.
- The three new settings are optional; set them only to change the defaults.
- Rebuild Tailwind. The new import pages and bulk confirmation and result templates use utility
  classes the old bundle may not include.
- Re-apply any customisations to the templates listed in `changed_template_paths`.
