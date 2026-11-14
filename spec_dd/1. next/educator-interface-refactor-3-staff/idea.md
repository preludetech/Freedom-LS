# Move the staff area into panels/staff

Spec 3 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Move the staff area of `freedom_ls/educator_interface/` into `panels/staff/`, together with its tests. The staff area is the organisation staff section: its config, its data table, its actions, its role filter and its quick view. The move changes nothing the user can see.

## Why

`views.py` and `actions.py` are each over 3,000 lines and too big to read. The staff actions alone are about 1,365 lines of `actions.py`, and their tests are about 3,450 lines of `test_actions.py`. Moving the area out shrinks both files and gives staff code one place to live.

## What is settled

- The area is a pure move. URL names, URL paths, the app label and template paths stay. No behaviour changes.
- Line ranges below are main's, taken before `extract_panels_framework-1-gather-generic-code` lands. That spec rewrites parts of the same files, so the spec must re-check every range against the tree it starts from. The classes and functions are the contract, not the line numbers.
- The area gets these modules under `freedom_ls/educator_interface/panels/staff/`, plus an empty `__init__.py`:
  - `config.py`: `StaffConfig` (`views.py` 2534-2591).
  - `data_tables.py`: `StaffDataTable` (`views.py` 2443-2533).
  - `actions.py`: the role helpers `grantable_roles_for`, `roles_grantable_on`, `role_reach`, `actionable_roles`, `role_entries_shown_to` and `has_grantable_roles` (`actions.py` 192-280); `_staff_member_param` (from the 281-309 block); the refusal and state helpers `REFUSAL_MESSAGES`, `SEARCH_LISTBOX_ID`, `_organisation`, `_refused`, `refusal_response`, `staff_member_changed_response`, `staff_member_state` and `_entries_after` (1707-1832); and every staff action (1833-2982). That is `AddStaffMemberAction`, `AddRoleAction`, `AddStaffMemberToCohortAction`, `CohortRoleAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`, `StaffRoleAction`, `DeactivateRoleAction`, `CohortChange`, `ChangeCohortsAction`, `StaffMemberStateAction`, `DeactivateStaffMemberAction` and `ReactivateStaffMemberAction`.
  - `filters.py`: `StaffRoleFilter` and `may_see_staff_roles` (`filters.py` 145-205).
  - `quick_view.py`: `StaffQuickView` (`quick_views.py` 137 to the end).
- The three cohort-scoped actions (`AddStaffMemberToCohortAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`) and the role helpers move with the staff area, even though the cohort Settings tab draws them. The cohort area imports them from `panels/staff/actions.py`. That keeps the dependency one way: cohort to staff.
- `staff.py` (`RoleEntry`, `staff_role_entries`, `current_role_entries`) stays flat in `educator_interface/`. Its importers repoint only where they themselves move.
- `ReasonMixin`, the param helpers (`_uuid_from`, `_action_params`, `_uuid_param`), the picker dialog helpers, `ShowInactiveFilter`, `OrganisationScopedRequest`, `OrganisationSectionConfig` and the table helpers are not moved here. `educator-interface-refactor-1-scaffolding-and-common` has already put them in `panels/common/`. The moved code imports them from there.
- `visible_registrations_with_progress` stays in `quick_views.py`, because `LearnerQuickView` uses it. `StaffQuickView` does not use it. The old `quick_views.py` keeps the learner and cohort quick views until `educator-interface-refactor-7-cleanup` deletes it.
- The lazy `interface_config` import inside `refusal_response` stays function-level. Only its dotted path changes. Removing the cycle is a behaviour-adjacent change and is not done here.
- The moved code adds no migration. None of its classes is registered with `@register_bulk_action`, so no `BulkActionRun.action_path` row points at them. The spec sets no `requires_migrations` flag.
- Clean break, no re-export shim. The spec removes the moved names from `views.py`, `actions.py`, `filters.py` and `quick_views.py`. It repoints every import and every `mock.patch` and `monkeypatch` string for the names it moves, in production code and tests. This includes staff imports in the `views.py` import block and in the learner and cohort code that still lives in the flat modules.
- Patch strings point at the module where the name is looked up, not where it is defined. Main has about 17 of them in `test_actions.py` that target `freedom_ls.educator_interface.actions.<name>` for staff names (`assign_role`, `grantable_roles`, `grantable_roles_for`, `current_role_entries`, `cohorts_visible_to`, `deactivate_role`). Each becomes a `panels.staff.actions` path. The two `actions.grantable_roles` patches in `test_views.py` do the same. Attribute patches on a module object (`monkeypatch.setattr(actions_module, ...)`) break silently, so the spec runs the suite and does not rely on grep.
- Tests move with the code to `freedom_ls/educator_interface/tests/panels/staff/`. Every new test directory gets an empty `__init__.py`. Each slice is cut out by removing only this area's ranges from the flat file:
  - `test_actions.py`: the staff slice of `tests/test_actions.py`, about 3,450 lines (main's 3157-5735 and 8560-9444; the second range is the cohort-scoped role actions).
  - `test_data_tables.py` and `test_config.py`: the staff section slice of `tests/test_views.py`, about 940 lines (main's 2811-3740), split by the module each test exercises.
  - `test_filters.py`: the `StaffRoleFilter` and `may_see_staff_roles` tests from `tests/test_filters.py`.
  - `test_quick_view.py`: any `StaffQuickView` tests from `tests/test_quick_views.py`.
  - A test file exists only where its module exists, so the mirroring hook stays green.
- The spec removes from `test_organisation/mirroring_baseline.txt` any line the move makes stale, in the same PR. Cross-cutting tests (`invariants/`, `playwright/`, `migrations/`) stay where they are. Their staff-related imports are repointed.
- Other repoints: `tests/interface_walk.py` and `invariants/test_config_authorisation.py` where they import staff configs, and the `educator-interface` skill in `claude_plugins/fls-dev` if it names the moved staff files. `urls.py` is unchanged. `interface_config` in the shell `views.py` imports `StaffConfig` from its new module.
- `panels/staff/` has no `panels.py`, `data_table_panels.py`, `instance_view.py` or `bulk_actions.py`, because the staff section has no such content.

## Open until the spec

- The exact split of the `test_views.py` staff slice between `test_data_tables.py` and `test_config.py`, and the exact edges of the `test_filters.py` and `test_quick_views.py` slices. The spec reads the tests and decides.
- Whether the 1,365-line `actions.py` should be split further. The default is one `actions.py`, as the effort's decision states.

## Out of scope

- Any behaviour, UI, URL or template change.
- The flat domain modules: `forms.py`, `staff.py`, `learner_import.py` and `messaging.py`. The staff forms in `forms.py` stay where they are.
- Everything another area owns: `panels/common/`, the cohort, learner, course, dashboard and audit log areas, and the final cleanup of the emptied flat modules (`educator-interface-refactor-7-cleanup`).
- Removing the lazy `interface_config` cycle.

## Resources

- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`: the target tree (section 3), line ranges (section 1), the test split (section 4), dotted-path references (section 5).
- `spec_dd/1. next/educator-interface-refactor/research_collisions.md`: what `extract_panels_framework-1-gather-generic-code` changes in the same files.
- `spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`: why there is no shim.
- `spec_dd/1. next/educator-interface-refactor/idea.md`: the owner's original brief.
- `claude_plugins/django-stack/resources/testing.md`: the test-mirroring rule.
