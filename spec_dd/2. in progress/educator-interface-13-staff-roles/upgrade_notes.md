---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/modal-header.html
  - freedom_ls/panel_framework/templates/cotton/modal-body.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/read_only.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/delete_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_denied.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_unavailable.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_run_stopped.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-actions.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_nav.html
  - freedom_ls/panel_framework/templates/cotton/panel-card.html
  - freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html
  - freedom_ls/panel_framework/templates/cotton/panel-person-link.html
  - freedom_ls/base/templates/cotton/quick-view-trigger.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_settings.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_settings.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_messages.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_staff_member.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/change_cohorts.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/staff_member.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/staff_roles.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/cohort_name_form.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/learner_name_form.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-13-staff-roles

## Breaking changes

None for a project that uses FLS as shipped and does not override roles.

### Roles and permissions

Two roles are added to `BASE_ROLES` in `freedom_ls/role_based_permissions/roles.py`, both assigned
on an organisation:

- `organisation_staff_viewer` holds `freedom_ls_learner_management.view_organisation_staff`.
- `organisation_staff_roles_viewer` holds that permission and
  `freedom_ls_learner_management.view_organisation_staff_roles`.

Four permissions are new:

- `freedom_ls_learner_management.view_organisation_staff`
- `freedom_ls_learner_management.view_organisation_staff_roles`
- `freedom_ls_role_based_permissions.assign_organisation_staff_viewer`
- `freedom_ls_role_based_permissions.assign_organisation_staff_roles_viewer`

`site_admin` and `organisation_admin` now hold all four. `cohort_admin` now holds
`freedom_ls_role_based_permissions.assign_cohort_admin`,
`freedom_ls_role_based_permissions.assign_cohort_viewer` and
`freedom_ls_audit_log.view_auditlogentry`.

A project that replaces the roles for a site through `FREEDOMLS_PERMISSIONS_MODULES` does not pick
these up from `BASE_ROLES`. Until its own roles module is updated:

- Nobody can open the Staff section. `StaffConfig.view_capability` is now
  `freedom_ls_learner_management.view_organisation_staff`. It was
  `freedom_ls_learner_management.view_staffmember`.
- A cohort admin has no Staff panel on a cohort's Settings tab, cannot add or change roles on
  their cohorts, and cannot open a cohort's History tab.

### Behaviour that changed

- A cohort admin can now grant, change and remove `cohort_admin` and `cohort_viewer` on the
  cohorts they administer, from the cohort's Settings tab, and can read that cohort's History
  tab. They pick only from staff they can already see. Only a holder of
  `freedom_ls_learner_management.add_staffmember` on the organisation creates staff.
- A person can change their own organisation or cohort role when they may assign that role on
  that target. `assign_role` and `deactivate_role` no longer raise `RefusalReason.SELF` for
  these. The last-organisation-admin lock stays, and so does `RefusalReason.SELF` for your own
  staff membership and your own site role.
- `assign_role` raises `RoleChangeRefused(RefusalReason.NOT_PERMITTED)` for a role that does not
  suit its target: a role in `ORGANISATION_ROLES` on a cohort, or a cohort role on an
  organisation.
- `RefusalReason` gains `ALREADY_STAFF`, `INACTIVE_STAFF_MEMBER` and `NOT_VISIBLE`.
- A staff member can have no roles. The Staff list shows them with "No roles yet".
- An `OrganisationSectionConfig` subclass with no `view_capability` is now shown only to a viewer
  who holds `freedom_ls_learner_management.view_cohort` on the organisation or on one of its
  cohorts. A project section that relied on "can enter the organisation" as its only gate is
  hidden from a holder of a viewer role alone.
- A new audit action, `staff_member.added`, is written when a person is added to staff with no
  role.

### Python names

- `LearnerSettingsPanel` and `CohortSettingsPanel` in `freedom_ls/educator_interface/views.py`
  are removed. The learner Settings tab is `LearnerSettingsStack` (`LearnerNamePanel`,
  `LearnerAccountPanel`). The cohort Settings tab is `CohortSettingsStack` (`CohortNamePanel`,
  `CohortStaffPanel`, `CohortStatusPanel`).
- `PICKER_MIN_TERM_LENGTH` is removed from `freedom_ls/comms/messaging.py`. Use
  `MIN_TERM_LENGTH` from `freedom_ls/accounts/search.py`.
- `ORGANISATION_ROLES` in `freedom_ls/learner_management/queries.py` names the roles held on the
  organisation itself. `STAFF_ROLES` now includes the two viewer roles.

### Templates

- `educator_interface/panels/cohort_settings.html` and
  `educator_interface/panels/learner_settings.html` are removed. An override of either no longer
  renders. Their content is in `cohort_name.html`, `cohort_staff.html`, `cohort_status.html`,
  `learner_name.html` and `learner_account.html` in the same directory.
- Every dialog is now `<c-modal-header>`, `<c-modal-body>` and `<c-modal-footer>` as siblings.
  `<c-modal-body>` is new and carries the padding and the spacing between blocks. A project
  dialog that wraps its content in its own padded `<div>` still renders; move it to
  `<c-modal-body>` to match. A read-only dialog (`panel_framework/modal/read_only.html`) ends in
  a Close footer.
- `<c-modal-header>` takes `title_id` and `closable`.
- `<c-panel-person-link>` and `<c-panel-avatar-chip>` take a `badges` slot, which puts badges on
  a line under the name and email.
- `<c-data-table>` takes `cards_when_narrow`. A `DataTable` that sets `cards_when_narrow = True`
  shows cards wherever its own container is narrower than 58rem, instead of only below `md`. The
  Staff table sets it.
- A table filter with no choices for the current request is left off the toolbar, Add filter
  and the filter sheet.
- A `ListViewConfig` with a `quick_view` and no `instance_view` now serves the quick view at
  `<pk>/__quick-view`.

## Manual steps

1. Run `manage.py migrate`. It applies
   `freedom_ls_learner_management.0012_alter_staffmember_options` and
   `freedom_ls_role_based_permissions.0004_alter_objectroleassignment_options`, which create the
   four permissions.
2. If the project replaces roles through `FREEDOMLS_PERMISSIONS_MODULES`, update each roles
   module: add the two viewer roles if you want them, give the admin roles the four new
   permissions, and give `cohort_admin` the three listed above. Run
   `manage.py validate_role_permissions` to check the result.
3. Run `manage.py sync_role_permissions` so existing role holders get the new permissions.
   `--dry-run` reports what it would change.
4. Rebuild Tailwind (`npm run tailwind_build`). The templates use new utility classes.
5. Re-apply any override of a template listed in `changed_template_paths` against the new
   version.
