---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/pagination.html
  - freedom_ls/comms/templates/comms/partials/notification_bell.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/quick_view_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_sheet.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_list_view_base.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-9-educator-administration

The educator interface gains a Members section. Organisation admins use it to list, add, re-scope,
remove, suspend and reactivate the people who hold a role in their organisation. It sits under a
new "Administration" navigation group and is only visible to users with
`freedom_ls_learner_management.view_organisationmember` on the organisation.

## Breaking changes

- **Event renamed.** `EDUCATOR_CHANGED = "educatorChanged"` in
  `freedom_ls/educator_interface/events.py` is now `MEMBER_CHANGED = "memberChanged"`, with no
  alias. Any downstream panel whose `refresh_events` lists the old constant, or any template that
  listens for `educatorChanged`, must switch to the new name. An import of `EDUCATOR_CHANGED` fails
  with an `ImportError`.
- **New system check `freedom_ls_panel_framework.E008`.** A `DataTable` may now declare
  `default_sort`. If it does, the value must be the `sort_field` of one of its sortable columns,
  optionally prefixed with `-`. Otherwise `manage.py check` fails at boot. Tables that declare no
  `default_sort` are not affected.
- **htmx 403/404 responses reload the page.** A user-triggered htmx request that gets an unmarked
  403 or 404 now reloads the current page instead of doing nothing. A response is marked when its
  body contains `data-htmx-swap-error`. The reload is skipped when the target is `#interface-main`
  or sits inside an element marked `data-htmx-owns-errors`. If a downstream fragment returns a
  bare 403 or 404 and handles it itself, mark the response or its container.
- **Role descriptions changed.** The `description` of `site_admin`, `organisation_admin`,
  `cohort_admin` and `cohort_viewer` in `freedom_ls/role_based_permissions/roles.py` was
  rewritten. Tests or copy that match the old strings need updating.
- **`assigned_at` moves on regrant.** `assign_object_role` and `assign_site_role` now set
  `assigned_at` to the current time when they reactivate an assignment or change its grantor.
  `assign_system_role` does not. `assign_object_role` and `remove_object_role` also validate the
  role against the role config of the target's site, not the default config.

## Panel framework additions

These are all opt-in, so existing sections keep working unchanged.

- `SectionConfigBase.view_capability`: a section the user lacks it for is left out of the
  navigation, and its pages return 404.
- `SectionConfigBase.intro_template_name` and `ListViewConfig.get_intro_context`: an intro slot
  above a list's table.
- `ListViewConfig.get_cell_context`: extra context passed to every cell template, computed once
  per request.
- `ListViewConfig.instance_view` may now be `None`. Instance paths under such a list return 404.
- A list root keeps actions with `renders_in_footer = False` out of its header, and passes
  `row_action_urls` to its cell templates so rows can render those actions.
- `DataTable.empty_state_template` replaces the fixed "No data available" message.
- `DataTable.default_sort` names the default sort column, so its header shows as sorted.

## Manual steps

1. Run `uv run manage.py migrate`. The data migration
   `learner_management/migrations/0006_delete_orphan_cohort_role_rows.py` deletes
   `ObjectRoleAssignment` rows whose cohort no longer exists, along with their guardian
   permission rows. From now on, deleting a `Cohort` deletes its role assignments and guardian
   rows automatically. You can also run guardian's `uv run manage.py clean_orphan_obj_perms` as a
   backstop.
2. Run `uv run manage.py check` to confirm that no downstream table trips
   `freedom_ls_panel_framework.E008`.
3. Search your code and templates for `EDUCATOR_CHANGED` and `educatorChanged` and rename them.
4. If you override any template listed in `changed_template_paths`, re-apply your changes on top
   of the new version. Pagination, row actions, the Filter and Sort controls and the pager are
   now at least 44px tall below the `md` breakpoint. The list and table templates also gained the
   intro slot, the empty-state template and row actions.
5. Rebuild Tailwind, because the shared templates use new utility classes such as `min-h-11` and
   `md:min-h-0`.
