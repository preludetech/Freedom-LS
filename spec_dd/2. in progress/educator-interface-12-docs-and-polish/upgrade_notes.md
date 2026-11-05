---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/base/templates/cotton/modal-trigger.html
  - freedom_ls/base/templates/partials/header_bar.html
  - freedom_ls/base/templates/partials/header_bar_user_menu.html
  - freedom_ls/comms/templates/comms/partials/messages_button.html
  - freedom_ls/comms/templates/comms/partials/notification_bell.html
  - freedom_ls/course_applications/templates/course_applications/partials/applicant_details_field.html
  - freedom_ls/course_applications/templates/course_applications/partials/claim_link_notice.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_when.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_member_actions.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/deactivate_registration.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member_actions.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member_roles.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/membership_actions.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_preview.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_member.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/change_cohorts.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/cohort_inactive.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_cohort_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_learner_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_member_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_role_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/delete_cohort_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/move_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_learner_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_member_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/remove_from_cohort_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/resend_setup_email_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/_lazy_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_course_completion.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_educators.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_needs_attention_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_body_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_downloads_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_history_empty.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_card.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_empty.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/learner_import_result_body.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/members_empty.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html
  - freedom_ls/icons/templates/cotton/icon.html
  - freedom_ls/form_engine/templates/form_engine/inputs/long_text.html
  - freedom_ls/form_engine/templates/form_engine/inputs/text_input.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/boolean.html  # deleted
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/datetime.html  # new
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/panel-attention-list.html
  - freedom_ls/panel_framework/templates/cotton/panel-search-field.html
  - freedom_ls/panel_framework/templates/cotton/panel-stat-tile.html
  - freedom_ls/panel_framework/templates/cotton/panel-status-badge.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_details_value.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_nav.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result_body.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/datetime.html  # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_refresh.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/quick_view_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_sheet.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_empty.html  # new
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-12-docs-and-polish

These notes cover this spec's own changes only. The notes for the whole educator interface
rebuild (specs 1 to 12) go in `effort_upgrade_notes.md` beside this file.

## Breaking changes

- **Two bulk actions are renamed** in `freedom_ls/educator_interface/actions.py`, along with
  their `action_name`, which is the slug in the bulk action's URL:
  - `UnregisterFromCourseBulkAction` (`"unregister_from_course"`) is now
    `DeactivateRegistrationBulkAction` (`"deactivate_registration"`).
  - `UnregisterCohortFromCourseBulkAction` (`"unregister"`) is now
    `DeactivateCohortRegistrationBulkAction` (`"deactivate_cohort_registration"`).

  Both are labelled "Deactivate a course registration". Update any import, subclass, panel `get_bulk_actions()` list or hard-coded bulk URL that
  uses the old names.

  A stored `BulkActionRun` names its action class by dotted path, so the data migration
  `freedom_ls_educator_interface.0001_rename_unregister_bulk_runs` rewrites runs recorded under the
  old names. Run `migrate` before the background workers restart on the new code: a worker that
  picks up a queued unregister run before the migration cannot load its action and marks the run
  failed with "This action is no longer available."
- **`inactive_cohort_response(request, cohort, blocked_phrase)`** in
  `freedom_ls/educator_interface/actions.py` takes a required third argument: what the refused
  action would have done, completing "Reactivate the cohort … to" (for example
  `"deactivate it"`). A subclass of `RequiresActiveCohortMixin` must set `blocked_phrase`; it has
  no default.
- **Deleted templates.** Anything that includes, extends or points `empty_state_template` at one of
  these must move to `panel_framework/partials/table_empty.html` or its own template:
  - `educator_interface/partials/members_empty.html`
  - `educator_interface/partials/audit_log_empty.html`
  - `educator_interface/partials/audit_history_empty.html`
  - the cotton component `data-table-cells/boolean.html` (`<c-data-table-cells.boolean>`)
- **`DataTable.empty_state_template`** in `freedom_ls/panel_framework/tables.py` now defaults to
  `"panel_framework/partials/table_empty.html"` instead of `None`. A table that did not set it now
  shows that empty state. Its text comes from two new attributes: `empty_message` (default
  "Nothing to see", shown when the table has no rows) and `empty_no_results` (shown when filters
  or a search hide every row, with a "Clear filters" or "Show all" link). Set both on each of your own tables.
- **The `.modal-backdrop` class is removed** from `tailwind.components.css`.
  `.modal-backdrop-host` stays. A theme or template that used `.modal-backdrop` loses that styling.
- **Icons are decorative by default.** `<c-icon name="x" />` with no `aria_label` now renders
  `aria-hidden="true"` and no `role`; it used to render `role="img"` with the semantic name as its
  label. An icon that is the only thing conveying its meaning (a yes/no mark, a status icon with no
  text beside it) is now silent unless you give it `aria_label="…"`, which renders `role="img"` with
  that name. The svg carries `data-icon="<semantic name>"`; a test that located an icon by its
  `aria-label` slug should use that attribute. In `freedom_ls/icons/backend.py`, `build_svg` takes
  an optional `data_name` and `DefaultIconBackend.render` no longer substitutes the semantic name
  for an empty `aria_label`; a custom `IconBackend` keeps its signature.
- **`--color-error` is darker.** The default theme's value moves from `#E8553D` to `#D23319` and
  `first_class` from `#E53E3E` to `#D71D1D`, so error text passes 4.5:1 on white and both surfaces
  and white text passes on an error fill. `--color-error-hover` derives from it. Two invariants in
  `freedom_ls/base/tests/invariants/test_theme_contrast.py` pin those pairings for the shipped themes.
- **Dates and times have one format.** `display_for_value` and `display_for_field` in
  `freedom_ls/panel_framework/field_display.py` now return `3 Nov 2026` for a date and
  `3 Nov 2026, 07:37` for a date-time (the module constants `DATE_DISPLAY_FORMAT` and
  `DATETIME_DISPLAY_FORMAT`) instead of the locale's default. A table column holding a date-time
  uses the new `cotton/data-table-cells/datetime.html` cell, and
  `educator_interface/data-table-cells/audit_when.html` is deleted in its favour; anything that
  included it should include `panel_framework/partials/datetime.html` with `value=`.
- **Labels in sentence case.** `CreateCohortAction.label` and `form_title` read "Create cohort",
  and the course page's panels are titled "Cohort registrations" and "Direct registrations". A
  test or override that matched the Title Case strings must follow.

## Manual steps

- Run `manage.py migrate` before restarting background workers, so the
  `freedom_ls_educator_interface.0001_rename_unregister_bulk_runs` data migration rewrites stored
  bulk action runs to the renamed actions.

- Rebuild the Tailwind bundle (`npm run tailwind_build`). Text fields, selects and textareas now
  use the new `border-border-input` utility, file inputs gained styling, interface buttons and
  fields are 44px tall below `md`, and `scroll-padding` keeps a focused element clear of the
  sticky header and the selection bar.
- Review every `<c-icon>` in your own templates: give an informative icon an `aria_label`, and
  drop any `aria-hidden="true"` wrapper you only added to silence the old fallback (it is harmless
  to keep). For a per-row trigger, `<c-button>` and `<c-modal-trigger>` take an `aria_label` var
  that becomes the control's `aria-label`; start it with the visible label.
- Optional: a custom theme that sets its own `--color-error` should keep it at 4.5:1 or better
  against white, `--color-surface` and `--color-surface-2`, and under `--color-on-error`.
- If you override any template in `changed_template_paths`, re-apply your changes on top of the
  new version. The confirmation dialogs under `educator_interface/modal/` now share one shape:
  a question title, a body saying what stops, what is kept and how to undo it, and a Cancel
  button with `autofocus` beside a confirm button.
- Optional: a custom theme inherits the new `--color-border-input` token from the default theme
  (`#6B7280`). If your theme changes `--color-surface` or `--color-surface-2`, set
  `--color-border-input` so it stays at 3:1 or better against white and both surfaces
  (`docs/how tos/theme-fls.md`, "Surfaces and structural").
- Optional: a bulk action of your own can set `confirm_variant` (the confirm button's variant,
  default `"primary"`), `loading_text` (the confirm label while the request runs) and override
  `confirmation_title(count, cleaned_data)` (the dialog heading, default `"<label>?"`), all on `BulkAction`
  in `freedom_ls/panel_framework/bulk_actions.py`. A `DataTable` can set `noun`,
  the plural noun its caption, scroll region and selection bar use.
- The QA commands `qa_create_educator_modal_target` and `qa_create_educator_progress_targets` are
  deleted. Remove any script that calls them.
