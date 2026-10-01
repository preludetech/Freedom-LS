---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/link.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/text.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/boolean.html
  - freedom_ls/base/templates/cotton/pagination.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/navigation_response.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-2-panel-framework-tables

## Breaking changes

These affect projects that declare their own `DataTable`, `DataTablePanel` or `ListViewConfig`
in `freedom_ls.panel_framework`, or that shadow the table templates.

- **`table_key` is required.** Every `DataTablePanel` subclass, and every `ListViewConfig` with a
  `list_view`, must set `table_key`, matching `[a-z0-9_]+`. Boot-time system checks enforce it:
  - `freedom_ls_panel_framework.E004`: no `table_key`.
  - `freedom_ls_panel_framework.E005`: `table_key` doesn't match `[a-z0-9_]+`.
  - `freedom_ls_panel_framework.E006`: two `DataTablePanel`s under one container share a key.
    All tabs count, including tabs that never render together.
  - `freedom_ls_panel_framework.E007`: a filter key doesn't match `[a-z0-9_]+`, or is one of
    `q`, `sort`, `page`, `export`.

  The table's region id is now `<table_key>-table`. Update any CSS, JS or tests that targeted the
  old id.
- **Column dicts become `Column`.** `DataTable.get_columns()` now returns a list of
  `freedom_ls.panel_framework.tables.Column` dataclass instances, not dicts. An unknown keyword is
  a `TypeError`. A cell template that needs extra fields needs a `Column` subclass. See
  `RelationLinkColumn` in `freedom_ls/educator_interface/views.py`.
- **Query parameters are renamed per table.** `?search=`, `?sort=`, `?order=` and `?page=` are
  replaced by `<table_key>-q`, `<table_key>-sort` (prefix `-` for descending; `order` is gone),
  `<table_key>-page`, `<table_key>-export` and `<table_key>-<filter key>`. Old bookmarked URLs
  and hand-built table links stop applying.
- **`DataTable` method signatures changed.** `get_rows(request, queryset, query)` now takes a
  `TableQuery` and only paginates. Searching, filtering and sorting move to
  `filter_queryset(request, queryset, query)`. `get_context(request, query, queryset, *, base_url,
  page_url, region_id)` replaces `get_context(request, queryset, base_url, table_id)`. `_prepare_columns` is removed: a
  sortable `Column` derives its own `sort_field`. Overrides of these methods need updating.
- **Default `page_size` is now 25** (was 5). Set `page_size` on your `DataTable` to keep the old
  value.
- **Templates moved to `panel_framework`.** `cotton/data-table.html` and
  `cotton/data-table-cells/{text,link,boolean}.html` moved from `freedom_ls/base/templates/` to
  `freedom_ls/panel_framework/templates/`. The `data_table_tags` library moved to
  `freedom_ls/panel_framework/templatetags/`. Template paths and the library name are unchanged,
  so `<c-data-table>` and `{% load data_table_tags %}` keep working. `c-data-table` was rewritten
  and takes a different set of inputs (see `_data_table_region_base.html`). A shadowed copy of the
  old markup will break.
- **Removed:** the `<c-scroll-table-labels>` component (`freedom_ls/base/templates/cotton/scroll-table-labels.html`),
  its `scrollTableLabels` Alpine component, and the educator cell templates
  `educator_interface/data-table-cells/progress_check.html` and `_link_to_cohort.html`. Tables
  render as cards below `md` instead.
- **`escape_csv_formula` moved** to `freedom_ls.base.csv_safety`, alongside `FORMULA_TRIGGERS` and
  a new `UTF8_BOM`. `FORMULA_TRIGGERS` is no longer defined in
  `freedom_ls.site_aware_models.admin_exports`. Import both from `freedom_ls.base.csv_safety`.
- **`c-pagination` gains `links` and `page_url` inputs.** Without `links` it behaves as before, so
  existing calls with `page_param_name`/`extra_params` keep working.
- **`educator_interface/interface.html` and `panel_framework/navigation_response.html`** now pass
  `csrf_token` into the main template include, so bulk-action forms can post. An override that
  still uses `... request=request only` will render those forms without a CSRF token.

## Manual steps

1. **Run `uv run manage.py check`.** Fix any `freedom_ls_panel_framework.E004`–`E007` errors by
   adding a `table_key` to each of your `DataTablePanel`s and `ListViewConfig`s, and renaming any
   invalid filter keys.
2. **Convert column dicts** in your `DataTable.get_columns()` to `Column(...)`.
3. **Re-check shadowed templates.** If your theme shadows any path in `changed_template_paths`,
   diff it against the new FLS version and re-apply your changes. A shadowed `cotton/data-table.html`
   must be rebuilt from the new one.
4. **Update links to tables** (bookmarks, emails, hand-built URLs) to the prefixed parameters.
5. **Rebuild Tailwind.** Run `npm run tailwind_build` (or your project's equivalent). The new
   toolbar, filter, selection bar, mobile cards and filter/sort sheet use utility classes your
   current bundle may not have.
6. **Deployment, only if you give a table `get_export_columns()`.** The CSV export streams rows
   with a server-side cursor (`QuerySet.iterator()`). Behind PgBouncer in transaction-pooling mode,
   set `DISABLE_SERVER_SIDE_CURSORS: True` in that database's `DATABASES` entry. Under a sync
   Gunicorn worker a long download can hit the worker timeout, so raise `--timeout` or use an
   async/threaded worker.

No migrations, settings keys, Python packages or npm packages change.
