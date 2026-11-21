---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-refactor-3-staff

## Breaking changes

The educator interface's staff area moved out of the flat `freedom_ls.educator_interface` modules into
`freedom_ls.educator_interface.panels.staff`. No behaviour, URL, URL name, template path, stored value or app label
changed, and there is no re-export shim. A downstream project that imports one of these names from its old module
must switch to the new one.

From `freedom_ls.educator_interface.filters` to `freedom_ls.educator_interface.panels.staff.filters`:

- `StaffRoleFilter`, `may_see_staff_roles`

From `freedom_ls.educator_interface.quick_views` to `freedom_ls.educator_interface.panels.staff.quick_view`:

- `StaffQuickView`

From `freedom_ls.educator_interface.actions` to `freedom_ls.educator_interface.panels.staff.actions`:

- role helpers `grantable_roles_for`, `roles_grantable_on`, `role_reach`, `actionable_roles`, `role_entries_shown_to`,
  `has_grantable_roles`
- refusals and responses `REFUSAL_MESSAGES`, `SEARCH_LISTBOX_ID`, `OTHER_SITE_MESSAGE`, `role_refusal_response`,
  `staff_member_changed_response`, `staff_member_state`
- actions `AddStaffMemberAction`, `StaffRowMixin`, `AddRoleAction`, `AddStaffMemberToCohortAction`, `CohortRoleAction`,
  `ChangeRoleAction`, `RemoveStaffFromCohortAction`, `StaffRoleAction`, `DeactivateRoleAction`, `CohortChange`,
  `ChangeCohortsAction`, `StaffMemberStateAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction`
- private helpers `_organisation`, `_refused`, `_staff_member_name`, `_entries_after`

From `freedom_ls.educator_interface.views`:

- `StaffDataTable` → `freedom_ls.educator_interface.panels.staff.data_tables`
- `StaffConfig` → `freedom_ls.educator_interface.panels.staff.config`

`views.py` still imports `StaffConfig`, `AddStaffMemberToCohortAction`, `ChangeRoleAction`,
`RemoveStaffFromCohortAction` and `roles_grantable_on` for its own use, so importing those from `views` keeps working
for now. Don't rely on it: import from the new modules.

Underscore-prefixed names are not public API. They moved with the same spelling, but may change without notice.

## Manual steps

- Grep your project for each old dotted path above, including strings passed to `mock.patch` or
  `monkeypatch.setattr`. A patch target must name the module that looks the name up: the staff actions now look up
  `assign_role`, `grantable_roles`, `current_role_entries`, `cohorts_visible_to`, `deactivate_role` and
  `grantable_roles_for` in `freedom_ls.educator_interface.panels.staff.actions`. A stale string on
  `freedom_ls.educator_interface.actions` can still resolve and then patch nothing, so tests pass without patching
  what they meant to.
- No migrations, settings, packages or Tailwind rebuild are needed.
