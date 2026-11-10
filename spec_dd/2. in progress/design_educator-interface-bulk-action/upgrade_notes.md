---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_footer.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/base/templates/cotton/dropdown-menu.html
  - freedom_ls/panel_framework/templates/cotton/modal-header.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_message.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result_body.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: design_educator-interface-bulk-action

## Breaking changes

None for a project that uses FLS as shipped.

The bulk-action selection bar is redesigned. At every width it sits above the table in place of
the toolbar while rows are selected, and sticks under the site header while the page scrolls. Its action
buttons are ghost, text-only buttons, and it has Select all, Deselect all and Clear controls.

`BulkAction.variant` changes meaning. It no longer styles the action's button in the bar. The value
`"error"` now marks the action as destructive (the new `BulkAction.destructive` property), and any
other value marks it as not destructive. The bar shows at most four permitted, non-destructive
actions as buttons (`PROMOTED_BULK_ACTION_COUNT` in `freedom_ls/panel_framework/panels.py`). The
rest go under a More menu, with destructive actions always last, in error text, below a rule. A
project bulk action that set `variant="primary"` to stand out now renders as a ghost button like the
others. One that set `variant="error"` moves from the bar into the More menu.

`DataTablePanel` adds two context keys, `promoted_bulk_actions` and `overflow_bulk_actions`, next
to the existing `bulk_actions`. The `<c-data-table>` component takes both as attributes.

The `tableSelection` Alpine component now sits on the table region (the element carrying
`data-table-region`) instead of on the bulk-action form. It covers the toolbar, the selection bar
and the table. The selection bar now renders inside the form, above the table, and the footer
(`table_footer.html`) renders for every table, bulk actions or not.

Without JavaScript, a bulk confirmation renders the list page with the confirmation open in
`#app-modal` over it. `panel_framework/views/bulk_confirmation.html` and
`panel_framework/views/_bulk_confirmation_base.html` are removed; an override of either no longer
renders. `<c-modal-header>` takes a `close_href`.

A bulk result names only failed rows: `BulkResult.entries` no longer holds skipped rows, and skips
are reported as counts only.

`<c-dropdown-menu>`'s trigger is now a `group/menu`. A chevron in a custom trigger turns with
`group-aria-expanded/menu:rotate-180`.

## Manual steps

Rebuild Tailwind. The templates use new utility classes and `tailwind.components.css` adds a
`[data-selection-bar-pending]` rule.

If your project overrides any of `data-table.html`, `table_selection_bar.html`,
`table_toolbar.html`, `table_footer.html` or `_data_table_region_base.html` under
`freedom_ls/panel_framework/templates/`, rebase the override on the new FLS version. An override
of `data-table.html` that keeps `x-data="tableSelection"` on the form breaks selection.

If your project overrides `freedom_ls/base/templates/cotton/button.html`, rebase it. The template
gains a `tone` attribute (`""` or `"error"`) for dropdown items. A new component,
`<c-dropdown-menu-separator />`, draws a rule between groups of items in a `<c-dropdown-menu>`.

Review your own `BulkAction` subclasses' `variant` values against the breaking changes above.
