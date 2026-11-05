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
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/cotton/pagination.html
  - freedom_ls/comms/templates/comms/partials/closed_note.html
  - freedom_ls/comms/templates/comms/partials/composer.html
  - freedom_ls/comms/templates/comms/partials/disclosure_line.html  # deleted
  - freedom_ls/comms/templates/comms/partials/thread.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_denied.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_upload.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_learners_results.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/member_change_refused.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_downloads.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_settings.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_settings.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/members_intro.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/run_status.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/staff_only_admin_callout.html  # new
  - freedom_ls/panel_framework/templates/cotton/data-table-actions.html  # new
  - freedom_ls/panel_framework/templates/cotton/modal-footer.html  # new
  - freedom_ls/panel_framework/templates/cotton/modal-header.html
  - freedom_ls/panel_framework/templates/cotton/panel-attention-row.html
  - freedom_ls/panel_framework/templates/cotton/panel-person-link.html  # new
  - freedom_ls/panel_framework/templates/cotton/panel-toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/delete_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_denied.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_unavailable.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_bulk_confirmation_base.html
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

- **The Members section is now Staff.** Its path moves from `/<org>/members` to `/<org>/staff`
  and its table's query parameters from `members-*` to `staff-*`; the old path answers 404 and no
  redirect is kept. `MemberConfig.url_name`, `menu_label` and `table_key` carry the new values;
  the Python names (`MemberConfig`, `OrganisationMember`, `MEMBER_CHANGED`, the `member.*` audit
  codes) are unchanged. Every string a person reads says staff or staff member: the heading, the
  caption and region name ("Staff members"), the empty states, "Add staff member", "Add a staff
  member", and the audit labels "Staff member deactivated" and "Staff member reactivated". The
  intro paragraph above the list, `partials/members_intro.html`, is deleted; the only-admin notice
  it also held moved to `partials/staff_only_admin_callout.html`.
- **Audit action labels name the noun first, and `AuditAction` gains `group`.** In
  `freedom_ls/audit_log/actions.py` these labels change: `cohort_membership.added` "Learner added
  to cohort", `cohort_membership.removed` "Learner removed from cohort", `cohort_membership.moved`
  "Learner moved between cohorts", `registration.added` "Learner registered for course",
  `registration.reactivated` and `.deactivated` "Learner course registration reactivated /
  deactivated", `cohort_registration.reactivated` and `.deactivated` "Cohort course registration
  reactivated / deactivated", `member.deactivated` and `.reactivated` "Staff member deactivated /
  reactivated". The seven shared webhook event type labels in
  `freedom_ls/base/webhook_event_types.py` follow (they show in the webhook subscription form).
  Labels are not stored, so no migration. `AuditAction(code, label, describe=None, group="Other")`
  takes a keyword `group` from `AUDIT_ACTION_GROUPS`; an action added through
  `AUDIT_LOG_EXTRA_ACTIONS` lands under "Other", and `audit_actions_by_group()` lists them.
- **The instance page header draws only `get_header_actions()`.** `InstanceView` in
  `freedom_ls/panel_framework/views.py` gains `get_header_actions()`, which returns
  `get_actions()` by default. `CohortInstanceView` and `LearnerInstanceView` return `[]` from it,
  show no stats, and show a badge only for a non-default state (Inactive; Pending for a learner).
  Their actions keep their `__actions/<name>` URLs and are offered from the Settings tab instead:
  `CohortSettingsPanel` now also carries Edit, and the new `LearnerSettingsPanel`
  (`learners/<pk>/__tabs/settings`, shown to anyone holding at least one of its actions) carries
  Edit name, Add to cohort, Register for a course, Resend setup email and Deactivate or
  Reactivate. A test or override that clicked a header button follows it to the Settings tab.
- **Every dialog ends in `<c-modal-footer>`.** The new component
  (`panel_framework/templates/cotton/modal-footer.html`) puts the `cancel` slot at the left and the
  default slot's actions at the right, and is sticky. Every `educator_interface/modal/*` template,
  `panel_framework/modal/{form,delete_confirmation}.html`, the bulk confirmation and result
  partials, the action-unavailable and action-denied partials, the modal host's discard prompt and
  the phone filter sheet use it; `<c-button-group>` is for buttons outside a dialog, and
  `test_every_dialog_ends_in_the_modal_footer_not_a_button_group` fails on a dialog that still
  uses it. `#app-modal` and `.side-panel-dialog` clip horizontally (`max-width: 100vw`,
  `overflow-x: hidden`) and the modal header's title wraps, so no dialog can push past a phone's
  edge.
- **Control links take a component; the prose underline is for prose.** New
  `<c-panel-person-link name user_id secondary href quick_view_url hx_nav>` renders a person as
  avatar and name in the row-link style, with an optional quick-view trigger; the learner and
  staff cells, the attention rows (dashboard, cohort overview, report) and the report summary
  table use it, and attention rows now pass `user_id` so the chip leads. Clear all, Clear
  filters, Show all, Reset, Select all matching, Clear selection, Check again, Export CSV and the
  import flow's links are `<c-button variant="link">` or small secondary buttons; back links use
  `<c-back-link>`. `test_no_control_link_is_hand_styled` and
  `test_every_anchor_with_visible_text_carries_its_own_classes` in
  `freedom_ls/panel_framework/tests/invariants/test_templates.py` fail on an `<a>` or `<button>`
  under `panel_framework/templates` or `educator_interface/templates` whose class carries
  `underline` or `text-primary`, or on a bare `<a>` with visible text; they scan FLS's own
  templates only.
- **Buttons in a data-table cell or card are small.** New `<c-data-table-actions>` wraps a cell's
  buttons with a gap; `<c-modal-trigger>` takes `size` and `class`; and a `.panel-data-table td
  .btn, .panel-data-table-card .btn` rule in `tailwind.components.css` forces the small size on
  any button inside a data table (`cotton/data-table.html` adds `panel-data-table` to its root,
  `data-table-card.html` adds `panel-data-table-card` to the card).
- **The phone sheet filters only and Sort is a menu.** `table_sheet.html` is titled and labelled
  "Filter", drops its sort radios, and renders only when the table has filters; `table_toolbar.html`
  adds a Sort dropdown menu (one `menuitem` per sortable column, carrying the column header's own
  link, with `aria-current` and a direction icon on the active one). Reset in the sheet no longer
  clears the sort (`DataTable.get_context`'s `reset_changes`). The desktop toolbar drops the
  "Sorted by …" text (the sorted column header carries `aria-sort`) and Export CSV is a small
  secondary button with the download icon. The selection bar's buttons are small below `lg` and the
  phone pager is two small icon buttons around "Page X of Y", always rendered and disabled at an
  end.
- **`TableFilter.widget` accepts `"grouped_checklist"`** (`freedom_ls/panel_framework/filters.py`),
  rendered as a checkbox per choice under the headings `get_groups(request)` returns (default: one
  unnamed group), as a popover form with one Apply in the toolbar and as collapsed groups in the
  sheet. `_toolbar_entry` adds `groups` and `form_hidden_inputs` for it. The audit log's What
  filter uses it.
- **The `select` base rule draws its own chevron** (`appearance-none`, two `currentColor`
  gradients, `pr-10`; list boxes keep none). A theme that shadows the `select` rule must draw one.
- **The Downloads card is a table.** `CohortReportDownloadsPanel` renders the last five ready
  reports (new `freedom_ls.reports.services.recent_cohort_reports(cohort, limit=5)`) plus the
  in-flight, stalled or newest failed one as rows (`DownloadRow`), each ready row with a small
  Download button; the Generate button sits beside the card title through the new
  `panel_header_action` block of `panel_framework/panels/_panel_base.html` (the card's
  `header_action` slot), is labelled "Generate report", and is disabled with the over-limit
  sentence as its `aria-describedby` while the cohort is over the learner limit. "Try again" and
  "Generate PDF report" are gone; `GenerateReportAction.label` is "Generate report".
- **A new Alpine component, `refocusAfterRequest`**, is registered in
  `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js` and listed in the
  `fls-dev:alpine-js` skill: a form with `x-data="refocusAfterRequest"`,
  `data-refocus-id="<id>"` and `x-on:htmx:after-request="refocus"` returns keyboard focus to that
  element once its request ends. Nothing else in this pass uses inline Alpine expressions or
  `hx-on`: the CSP build of Alpine runs no inline expression, and `hx-on` needs `unsafe-eval`.
- **The messaging disclosure line is removed.** `comms/partials/disclosure_line.html` is deleted
  and no longer included by `composer.html`, `thread.html` or `closed_note.html`; a template that
  included it must drop the include. In the quick view the composer's Send is a small icon-only
  ghost button named "Send".
- **The move dialog** is titled "Move <learner>" and opens with "Current cohort: <cohort>" and
  what the move does; its select's placeholder reads "Move to cohort" and its visible label is
  screen-reader only.

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
- Rebuild the Tailwind bundle (`npm run tailwind_build`): the `select` chevron, the
  `.panel-data-table` button rule and the new components' utilities are new.
- Update any bookmark, link or test that used `/<org>/members` or `members-*` query parameters to
  `/<org>/staff` and `staff-*`.
- Re-apply overrides of the templates listed above. A dialog you shadow must end in
  `<c-modal-footer>`, a control link must carry a component's classes, and a person in a row or
  list goes through `<c-panel-person-link>`; the two new invariant tests say which of your own
  templates under FLS's own template directories still need it.

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
