---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/cotton/modal-footer.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/content_preview.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/course_details_preview.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-intercface-small-ui-polish

## Breaking changes

- **Course page panel stack renamed.** `freedom_ls.educator_interface.panels.course.instance_view.CoursePanelStack`
  is gone. The course page is now `CourseTabSet`, with two tabs: `CourseOverviewStack` (details,
  cohort and direct registrations) and `CourseContentStack` (content, reference). A project that
  imports or subclasses `CoursePanelStack` must move to these classes.
- **Course panel URLs moved under the Overview tab.** A course page panel that was served at
  `courses/<uuid>/__panels/<panel>` is now at `courses/<uuid>/__tabs/overview/__panels/<panel>`
  (or `__tabs/content/...` for the content and reference panels). Update any hard-coded panel URL.
- **`KEEPING_NAMES_SHOWN` moved.** It now lives in
  `freedom_ls.educator_interface.panels.common.registration_actions`, no longer in
  `freedom_ls.educator_interface.panels.cohort.actions`.
- **Header-less table columns render as a card footer.** On narrow screens, a `DataTable` column
  with no header is now drawn as a footer under the card's values (passed to the card as
  `action_columns`), not as a labelled value. A custom table that put data rather than buttons in
  a header-less column should give that column a header.

## Manual steps

- If the project overrides any template in `changed_template_paths`, re-apply its customisations
  on top of the new version: `cotton/data-table.html` and `_data_table_region_base.html` pass the
  new `action_columns` and `child_rows_collapsed` values, `cotton/data-table-card.html` renders the
  action footer, and `cotton/modal-footer.html` gains a `stepping` mode with `previous` and `next`
  slots. The two educator preview modals now use the new
  `educator_interface/partials/preview_stepping_footer.html` instead of a Close button.
- Rebuild Tailwind and run `collectstatic`: new templates were added and
  `panel_framework/js/alpine-components.js` changed (the `childRows` component honours
  `data-child-rows-collapsed`).
- Optional: a `DataTable` with `has_child_rows = True` can set `child_rows_collapsed = True` to
  start its groups closed.
