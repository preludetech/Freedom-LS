---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/modal-trigger.html
  - freedom_ls/panel_framework/templates/cotton/panel-table.html
  - freedom_ls/panel_framework/templates/cotton/panel-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_footer.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-profile-use-panels-framework-2-editable-list-panel

## Breaking changes

- `CreateInstanceAction`'s "add another" button changed. Its label is now "Add and add another"
  (was "Save and add another"), the primary button reads "Add" (was "Save"), and the button posts
  `action=add_another` (was `action=save_and_add`). A downstream subclass that overrides
  `submit_buttons`, or code and tests that post or look for `save_and_add`, must switch to
  `ADD_ANOTHER_BUTTON` and `wants_add_another()` from `freedom_ls.panel_framework.actions`.
  After an "add another" save the dialog now shows "Added <name>." above the empty form.
- `get_hidden_fields()` moved up to `PanelAction`, so every action can post hidden fields, and
  `panel_framework/modal/form.html` now renders `hidden_fields`. A downstream override of
  `modal/form.html` must render the `hidden_fields` loop, or row-scoped form actions lose their
  row parameter on submit.

## Manual steps

- Rebuild Tailwind: the panel templates now use `@container`, `@min-[58rem]:block`,
  `@min-[58rem]:hidden` and `empty:hidden`.
- If you override any template listed in `changed_template_paths`, re-apply your changes on top of
  the new version. `panel-table.html` gained a `cards_when_narrow` attribute, `panel-table-card.html`
  a `content` slot, `modal-trigger.html` forwards extra attributes to its button, and
  `table_footer.html` now includes `panel_framework/partials/entry_count.html`.
- New: `EditableListPanel` and `EditableListSummary` in `freedom_ls.panel_framework.panels`, with the
  check `freedom_ls_panel_framework.E009`, which runs on each `EditableListPanel` subclass you
  define. Nothing to do unless you use it.
