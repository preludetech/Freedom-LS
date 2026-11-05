---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_details.html  # removed
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_target.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_what.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_when.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_who.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_card.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_card_targeted.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_person.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_row_detail.html  # new
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: design_educator_interface_audit_log

The educator audit screens (a learner's History tab, a cohort's History tab and the organisation
Audit log) now show one compact line per entry with initials avatars, keep the description, reason
and a bulk run's entries in an expandable row detail, and offer a CSV export. Each export is
itself recorded as a new `audit_log.exported` audit action.

## Breaking changes

- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_details.html`
  is removed. Its content (description, reason, bulk-run entries) now renders in
  `educator_interface/partials/audit_row_detail.html`. A downstream override of the old file is no
  longer used; move any customisation to the new partial.
- The data-table templates in `panel_framework` gained a leading row-detail toggle column (a
  chevron in the table and on each mobile card) and an indented detail row, and the toolbar moved **Export CSV** (now also shown on mobile). A downstream
  override of `cotton/data-table.html`, `cotton/data-table-card.html`,
  `panel_framework/panels/_data_table_region_base.html` or
  `panel_framework/partials/table_toolbar.html` must be re-based on the new versions, or the
  audit row detail and mobile export link will not appear.

The new Python hooks are additive and need no change in downstream code:
`DataTable.row_detail_template`, `DataTable.has_row_detail`, `DataTable.applied_filter_text`,
`DataTablePanel.get_export_queryset` / `before_export`, the optional `queryset` argument to
`DataTablePanel.narrow`, and `ListViewConfig.get_export_queryset` / `before_export` /
`get_export_scope_slug`.

## Manual steps

- Rebuild Tailwind (`npm run tailwind_build`): `tailwind.components.css` changed (an open
  `data-row-detail` row carries its data row's bottom border and shares its hover) and the new templates use new utility classes.
- Review and re-apply any customisations to the templates listed above.
- No migrations, settings or package changes.
