---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/pagination.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/course_content.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_card.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/staff_card.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/cotton/modal-footer.html
  - freedom_ls/panel_framework/templates/cotton/panel-definition-list.html
  - freedom_ls/panel_framework/templates/cotton/panel-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/confirm.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_lazy_region.html
requires_settings_change: false
changed_settings:
  - DEFAULT_PAGE_SIZE  # optional: rows per page for a table with no page_size, default 10
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: extract_panels_framework-2-new-capabilities

## Breaking changes

- `DataTable.page_size` now defaults to `None`, and the page size comes from
  `DataTable.get_page_size()`: the table's own `page_size`, else the new `DEFAULT_PAGE_SIZE`
  setting (default 10). Code that reads `SomeTable.page_size` directly gets `None` for a table
  that sets none; call `get_page_size()` instead.
- `DataTable.get_queryset` and `DataTablePanel.get_queryset` may now return a sequence of row
  objects as well as a `QuerySet`, and `DataTable.get_context`, `DataTable.get_rows` and
  `DataTablePanel.narrow` accept `QuerySet | Sequence[object]` (and `narrow` returns it). A subclass that
  overrides these with the narrower `QuerySet` type still runs, but no longer matches the base
  signature for a type checker. `has_row_detail` and `get_row_label` now take `row: object`.
  A sequence-backed table may not set `search_fields`, filters, sortable columns or export
  columns, and must set `noun` and `noun_singular`; it raises `ImproperlyConfigured` otherwise.
- `ReasonForm.__init__` takes keyword-only `required` and `choices`. A host subclass with its own
  `__init__(self, data=None)` keeps working for actions that set neither `reason_required` nor
  `reason_choices`; one used by an action that sets either must accept and pass on those keywords.
- The `courseOutline` Alpine component is removed from
  `freedom_ls/educator_interface/static/educator_interface/js/alpine-components.js`. The course
  outline (`CourseContentPanel`) now renders through `<c-data-table>` with the framework's
  `childRows` component, pages at the default page size, and shows cards on a phone. A downstream
  override of `educator_interface/panels/course_content.html` that uses `courseOutline` must be
  rebuilt from the new template.
- Below `md`, `.btn` no longer gets `min-h-11` on panel pages; it keeps its desktop size and gets
  a 44px hit area from an invisible `::after`. Dialog footer buttons (`[data-modal-footer] .btn`)
  stay 44px tall. Pagination buttons dropped their `min-h-11 md:min-h-0` classes. A downstream
  template that relied on the old button height below `md` will look shorter.

## Manual steps

- Rebuild Tailwind (`npm run tailwind_build`): `tailwind.components.css` changed and new
  templates use new utility classes.
- Review overrides of the templates listed in `changed_template_paths`.
  `_data_table_region_base.html` passes new attributes to `<c-data-table>` (`has_child_rows`,
  `compact`, `leading_columns`, `row_template_colspan`); `_lazy_region.html` has a new `as_of`
  block, and a region that overrides `region_content` must include
  `panel_framework/partials/as_of.html` itself when its panel sets `show_as_of`;
  `modal/confirm.html` takes an optional `title_id`.
- Optional: set `DEFAULT_PAGE_SIZE` in settings to change the rows per page for every table that
  sets no `page_size`.
- New opt-in options, no action needed unless used: `reason_required` and `reason_choices` on
  reason actions (read the new `PanelContext.reason_choice`), `show_as_of` on lazy panels, and `compact`,
  `has_child_rows` / `get_child_rows`, `get_row_template_name` and sequence-backed rows on
  `DataTable`.
