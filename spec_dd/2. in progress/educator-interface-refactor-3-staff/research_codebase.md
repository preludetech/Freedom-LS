# Research: codebase (educator-interface-refactor-3-staff)

Question: what in the existing codebase does moving the staff area into `freedom_ls/educator_interface/panels/staff/` touch, reuse or conflict with?

All line numbers are the CURRENT tree (branch `educator-interface-refactor-3-staff`, after `extract_panels_framework-1-gather-generic-code` and `educator-interface-refactor-1-scaffolding-and-common`). Paths are relative to `freedom_ls/educator_interface/` unless they start with another root. `actions.py` is 3,300+ lines, `views.py` about 3,400.

Method note: I had no shell, so I could not run `git`, ruff or pytest. Everything below comes from reading and grepping the tree. Unused-import lists are derived by reading, not by ruff; the spec's implementation must let ruff have the last word.

## 1. Current location of every moving name

### 1.1 `actions.py`

Role helpers (all staff-only, one contiguous block):

| Name | Lines |
|---|---|
| `grantable_roles_for` | 200-209 |
| `roles_grantable_on` | 212-218 |
| `role_reach` | 221-237 |
| `actionable_roles` | 240-255 |
| `role_entries_shown_to` | 258-279 |
| `has_grantable_roles` | 282-286 |

Lines 289-332 (`inactive_cohort_response`, `cohort_not_empty_sentence`) directly follow and are cohort code, so they stay.

Refusal and state helpers, then the actions: one contiguous block, lines 1496-2772. It sits between `cohort_state_actions()` (1491-1493, stays) and `LearnerBulkAction` (2775, stays).

| Name | Lines |
|---|---|
| comment + `REFUSAL_MESSAGES` | 1496-1518 |
| `SEARCH_LISTBOX_ID` | 1520 |
| **`OTHER_SITE_MESSAGE`** (missed by the idea) | 1521-1523 |
| `_organisation` | 1526-1527 |
| `_refused` | 1530-1532 |
| **`role_refusal_response`** (the idea calls it `refusal_response`) | 1535-1542 |
| **`_staff_member_name`** (missed by the idea) | 1545-1548 |
| `staff_member_changed_response` | 1551-1580 |
| `staff_member_state` | 1583-1596 |
| `_entries_after` | 1599-1617 |
| `AddStaffMemberAction` | 1620-2114 |
| **`StaffRowMixin`** (missed by the idea) | 2116-2127 |
| `AddRoleAction` | 2129-2171 |
| `AddStaffMemberToCohortAction` | 2173-2205 |
| `CohortRoleAction` | 2207-2236 |
| `ChangeRoleAction` | 2238-2339 |
| `RemoveStaffFromCohortAction` | 2341-2384 |
| `StaffRoleAction` | 2386-2431 |
| `DeactivateRoleAction` | 2433-2548 |
| `CohortChange` (NamedTuple) | 2550-2554 |
| `ChangeCohortsAction` | 2556-2685 |
| `StaffMemberStateAction` | 2687-2699 |
| `DeactivateStaffMemberAction` | 2701-2736 |
| `ReactivateStaffMemberAction` | 2738-2772 |

The block is about 1,366 lines (88 + 1,278), matching the idea's "about 1,365".

Name flags against the idea:
- **`refusal_response` is not a staff name.** In `actions.py` it is the framework function imported at line 182 from `freedom_ls.panel_framework.actions`. Cohort code uses it too (`inactive_cohort_response`, line 295). The staff helper the idea means is `role_refusal_response` (1535). `_refused` (1530) calls the framework `refusal_response`, so the new module must still import `refusal_response` from `panel_framework.actions`. It stays in `actions.py` as well.
- **The lazy `interface_config` import is in `staff_member_changed_response`** (line 1557: `from freedom_ls.educator_interface.views import interface_config`, with `first_visible_section` imported beside it at 1558). It is not in `refusal_response`/`role_refusal_response`. That function also pops the request attributes `works_with_cohorts` and `may_see_staff_roles` (line 1563).
- **Missed staff-only names inside the ranges**: `OTHER_SITE_MESSAGE`, `_staff_member_name`, `role_refusal_response`, `StaffRowMixin`. All four are used only inside the staff block, so they move with it.
- **A same-name trap**: `ReactivateRegistrationAction._refused` (line 912) is a method on a learner class and is not the staff `_refused`. Do not move it.
- Nothing in the lists was renamed or already moved. Every name the idea lists still exists, with the one `refusal_response` caveat.

What the staff block depends on from elsewhere in the flat `actions.py`: nothing cohort or learner. A grep of the block for every cohort and learner helper (`inactive_cohort_response`, `RequiresActiveCohortMixin`, `_membership_changed_response`, `_picker_cohorts`, the bulk-action bases and the rest) finds no use. Staff code also does not use `_uuid_from`, `_empty_message`, `_picker_title` or `_register_title` from `panels/common/actions.py`. It uses only `EducatorReasonMixin` (bases of `RemoveStaffFromCohortAction`, `DeactivateRoleAction`, `DeactivateStaffMemberAction`) and `_action_params` (lines 2228, 2400, 2417, 2480).

What the rest of the flat `actions.py` uses from the staff block: nothing. The only cross-reference left is the import at line 48 (`may_see_staff_roles`, used only at 265, 2427 and 2495, all staff). So flat `actions.py` has no dependency on `panels/staff/` after the move.

Staff-only imports in `actions.py` that become unused in the flat module (read, not ruff-checked):
- `STAFF_CHANGED` (46)
- `may_see_staff_roles` (48)
- forms `AddStaffMemberForm`, `ChangeRoleForm`, `StaffEmailForm`, and probably `CohortSetForm` (2629 only)
- `ORGANISATION_SCOPE`, `RoleEntry`, `current_role_entries` from `staff.py` (79-83)
- queries `ADD_STAFF_MEMBER`, `ASSIGN_COHORT_VIEWER`, `ORGANISATION_ROLES`, `STAFF_ROLES`, `has_staff_assignments`, `pickable_staff`, `role_target`, `staff_assignments`, `staff_of`, `CHANGE_STAFF_MEMBER`
- `_active_role_assignments`
- the `role_assignment` imports: `ASSIGN`, `GrantableRole`, `add_staff_member`, `assign_role`, `deactivate_role`, `grantable_roles`, `is_last_organisation_admin`, `is_site_level_admin`, `set_staff_member_active`
- `ensure_staff_member`, `StaffMember` model, `RefusalReason`, `RoleChangeRefused`, `get_role_config`, `ObjectRoleAssignment`
- `match_or_create_user`, `lookup_user`, `MIN_TERM_LENGTH`, `term_condition`, `field_error_count`, `NamedTuple`, `QueryDict`, `replace`, `timezone`

Still used by flat code, so they stay: `cohorts_visible_to` (849 and others), `can`, `count_noun`, `join_prose`, `denied_response`, `transaction`, `cast`.

### 1.2 `views.py`

| Name | Lines |
|---|---|
| `DashboardConfig` (stays here until refactor-2 moves it) | 2485-2489 |
| `StaffDataTable` | 2492-2583 |
| `StaffConfig` | 2586-2641 |
| `OrganisationAuditLogTable` (next block; refactor-2) | 2644-2691 |
| `AuditLogConfig` (refactor-2) | 2694-2725 |
| `interface_config` (uses `StaffConfig` at 2733) | 2728-2734 |

`StaffDataTable` and `StaffConfig` are adjacent, with no staff-only helper between them and nothing staff-only among the module-level helpers elsewhere in `views.py`. Other staff-name uses in `views.py` that are NOT in those two classes and stay in `views.py`, repointed to `panels.staff.actions`:
- 1628-1630: `AddStaffMemberToCohortAction()`, `ChangeRoleAction()`, `RemoveStaffFromCohortAction()` in the cohort Settings panel's actions
- 1645: `roles_grantable_on(self.request, cohort)`

`views.py` import block, staff names (lines 77-109, 118-126, 166-170, 178):
- Drop outright, staff-only: `AddRoleAction`, `AddStaffMemberAction`, `ChangeCohortsAction`, `DeactivateRoleAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction`, `actionable_roles`, `grantable_roles_for`, `StaffRoleFilter`, `may_see_staff_roles`, `StaffQuickView`, `staff_role_entries` (line 178).
- Drop from the queries import because only the staff block used them: `VIEW_ORGANISATION_STAFF` (201), `staff_assignments` (213), `staff_of` (214).
- Repoint to `panels.staff.actions`, because cohort code still needs them: `AddStaffMemberToCohortAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`, `roles_grantable_on`.
- New import in `views.py`: `StaffConfig` from `panels.staff.config`, for `interface_config` (2733).
- Keep (still used elsewhere): `site_level_admins` (1274), `StaffMember` (768-771), `STAFF_CHANGED` (1618, 1702), `Prefetch`, `Page`, `Sequence`, `TableQuery`, `Column`, `TableFilter`, `ListViewConfig`, `OrganisationScopeDenied`, `interface_path`, `User`, `OrganisationSectionConfig`, `OrganisationScopedRequest`.

### 1.3 `filters.py`

| Name | Lines |
|---|---|
| `may_see_staff_roles` | 100-110 |
| `StaffRoleFilter` | 113-156 |

They sit between `LearnerCourseFilter` (90-97) and `AuditActorFilter` (159). After the move the flat `filters.py` no longer needs: `can`, `STAFF_ROLES`, `VIEW_ORGANISATION_STAFF_ROLES`, `staff_assignments`, `get_role_config`. It still needs `User` for `AuditActorFilter`, until refactor-2 moves that.

`may_see_staff_roles` also sets a request attribute of the same name. The `OrganisationScopedRequest` annotation (`panels/common/request.py` 55) is only a type hint and needs no change. `staff_member_changed_response` pops the same string key.

### 1.4 `quick_views.py`

`StaffQuickView` is lines 152-171, the end of the file. The idea says "137 to the end", but 137-149 is `CohortQuickView` and 150-151 is blank. Its range is 152-171.

After removal, `quick_views.py` no longer needs: `STAFF_CHANGED` (line 20), `current_role_entries` (28), the `TYPE_CHECKING` `User` import (43-44, used only as a `"User"` string inside `StaffQuickView`), and probably `TYPE_CHECKING` itself. The module docstring (line 1) says "Learners, Cohorts and Staff sections" and needs a one-word update. `email_below_name` is still used by `LearnerQuickView`.

`visible_registrations_with_progress` (47-62) is used only by `LearnerQuickView`, confirming the idea.

### 1.5 Names that stay flat

`staff.py` has `ORGANISATION_SCOPE`, `_NAMED_COHORTS`, `_cohort_label`, `RoleEntry`, `staff_role_entries` and `current_role_entries`. It imports nothing from `educator_interface`, so it is a leaf and the new modules can import it without cycles. The staff forms (`AddStaffMemberForm`, `ChangeRoleForm`, `StaffEmailForm`, `CohortSetForm`) stay in `forms.py`.

## 2. What `panels/` and `panels/common/` look like now, and what each moved block imports

Tree today: `panels/__init__.py` plus `panels/common/{__init__,actions,badges,bulk_actions,filters,ids,report,request,tables}.py`. No `panels/staff/` exists. Refactor-1 gave every `panels/common/` module an explicit `__all__`. Underscore names (`_action_params` and the like) are exported through `__all__` so cross-module imports stay lint-clean.

What `panels/common/` exports that staff code uses:
- `actions.py`: `EducatorReasonMixin`, `_action_params`. Also exported but unused by staff: `_uuid_from`, `_empty_message`, `_picker_title`, `_register_title`.
- `request.py`: `OrganisationScopedRequest` (a typing-only `HttpRequest` subclass, used with `cast("OrganisationScopedRequest", ...)`; it already declares the staff attrs `grantable_roles`, `role_reach`, `may_see_staff_roles`) and `OrganisationSectionConfig`. `LAST_ORGANISATION_SESSION_KEY` is not used by staff.
- `tables.py`, `badges.py`, `bulk_actions.py`, `filters.py`, `ids.py`, `report.py`: not used by staff code. The staff table has no bulk actions and builds its own `Column`s.

Imports each new module needs (estimated from the moved code; ruff has the last word):

- **`panels/staff/filters.py`**: `cast`; `QuerySet`; `HttpRequest`; `User`; `OrganisationScopedRequest` (panels.common.request); `can`; `STAFF_ROLES`, `VIEW_ORGANISATION_STAFF_ROLES`, `staff_assignments`; `ChoiceFilter`; `get_role_config`.
- **`panels/staff/actions.py`**: the large import set listed in 1.1, plus from panels.common `EducatorReasonMixin`, `_action_params` and `OrganisationScopedRequest`; from the flat `staff.py` `ORGANISATION_SCOPE`, `RoleEntry`, `current_role_entries`; from `panels/staff/filters.py` `may_see_staff_roles`; from `forms.py` the staff forms; `STAFF_CHANGED` from `events`; from `panel_framework`: `ConfirmAction`, `ModalPanelAction`, `PanelAction`, `changed_response`, `denied_response`, `field_error_count`, `join_prose`, `refusal_response`, `PanelContext`. Plus the function-level `from freedom_ls.educator_interface.views import interface_config` in `staff_member_changed_response`, kept as is.
- **`panels/staff/data_tables.py`**: `DataTable`, `Column`, `TableQuery`, `TableFilter` (panel_framework); `Prefetch`, `QuerySet`, `Page`, `Sequence`, `HttpRequest`, `cast`; `User`; `Learner`, `StaffMember`; `staff_of`, `staff_assignments`, `site_level_admins`; `OrganisationScopedRequest`; `StaffRoleFilter` (staff.filters); `actionable_roles` (staff.actions); `staff_role_entries` (flat `staff.py`).
- **`panels/staff/config.py`**: `OrganisationSectionConfig` (panels.common.request), `ListViewConfig`, `PanelAction`, `Model`, `HttpRequest`, `cast`, `User`, `OrganisationScopeDenied`, `STAFF_CHANGED`, `VIEW_ORGANISATION_STAFF`, `staff_of`, `interface_path`, `OrganisationScopedRequest`; `StaffDataTable`, `StaffQuickView`, `grantable_roles_for` and the six actions, `may_see_staff_roles`.
- **`panels/staff/quick_view.py`**: `cast`, `TYPE_CHECKING`/`User`, `QuickView`, `STAFF_CHANGED`, `email_below_name`, `current_role_entries`, `OrganisationScopedRequest`.

Import-graph shape: `filters` is the leaf; `actions` imports `filters`; `data_tables` imports `filters` and `actions`; `quick_view` is independent; `config` imports `data_tables`, `quick_view`, `actions`, `filters`. The only cycle is the existing lazy one, `actions` to `views.interface_config`. `views.py` imports `panels.staff.config` and `panels.staff.actions` at the top. The cohort code in `views.py` importing from `panels.staff.actions` gives cohort-to-staff, one-way, as the idea wants.

## 3. Importers and string references of each moving name

### 3.1 Production code

Only `views.py` (section 1.2) and `actions.py` itself (section 1.1) import staff names. Nothing else in `freedom_ls/` does: `reporting.py`, `templatetags/educator_tags.py` (imports `LearnerCourseSummary` and `learner_course_summaries` only), `urls.py` (imports `views` as a module and no staff name), `qa_helpers/`, `tasks.py`, `learner_management/` and `reports/` have no matches. A repo-wide grep for all names in the list, excluding `spec_dd/`, found them only in the files named here.

Cross-module uses between flat modules (the "learner and cohort code in the flat modules that uses staff names"): only `views.py` 1628-1630 and 1645 (cohort Settings panel), listed above. No learner code uses a staff name. `quick_views.py` has no staff dependency on other modules; `filters.py`'s `may_see_staff_roles` is used by `actions.py` (265, 2427, 2495) and `views.py` (2617, 2629).

Dotted-path references in production code:
- `actions.py` line 1557: the lazy `views.interface_config` import (stays function-level; its target does not move).
- `migrations/0001_rename_unregister_bulk_runs.py` line 5: `_ACTIONS = "freedom_ls.educator_interface.actions."`. It rewrites stored learner/cohort bulk-run paths and names no staff class (the idea's "no `BulkActionRun.action_path` row points at staff names" stands: no staff class has `@register_bulk_action`). The test `tests/migrations/test_0001_rename_unregister_bulk_runs.py` line 15 has the same prefix. No change.
- Templates: only the context names `staff_member_state`, `actionable_roles` (an attribute on rows), and docstring mentions of `DeactivateRoleAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction`, `RemoveStaffFromCohortAction`. There are no dotted-path references to a staff module. Template paths stay (idea). Docstring-only mentions in `templates/educator_interface/modal/*.html` are class names, not paths, so they need no edit.
- Cotton / `educator_interface/templates/.../staff_role_buttons.html` reads `object.actionable_roles`, which `StaffDataTable.get_rows` sets (2550). No change.

### 3.2 Tests

- `tests/invariants/test_config_authorisation.py`: line 34 `from freedom_ls.educator_interface.views import StaffDataTable`; used at 183 only, as a throw-away `list_view = StaffDataTable` in `test_walk_interface_skips_detail_paths_for_a_list_with_no_instance_view`. The import repoints to `panels.staff.data_tables`. The module docstring (line 3) names `educator_interface.views.interface_config`, which does not move.
- `tests/interface_walk.py`: imports `interface_config` from `views` only, with no staff name. No change.
- `tests/test_filters.py`: line 24 imports `StaffRoleFilter` from `educator_interface.filters`; line 36 imports `StaffDataTable` from `views`. Uses at 293-294, 345-430, 490, 497 (all in the staff slice).
- `tests/test_views.py`: line 7507 `educator_views.StaffDataTable` in the module-level `EDUCATOR_TABLES` list (7498-7509). It is a module-attribute access (it fails with AttributeError, not silently, once removed from `views`). This list also holds `educator_views.OrganisationAuditLogTable` (7508), which refactor-2 repoints. The test stays in `test_views.py` and the entry is repointed. Lines 3784 and 3815: `monkeypatch.setattr("freedom_ls.educator_interface.actions.grantable_roles", ...)` (2 patches; they move with the slice and repoint to `panels.staff.actions.grantable_roles`).
- `tests/test_actions.py`:
  - Imports, lines 33-50: `actions_module` (module object), `REFUSAL_MESSAGES`, `AddStaffMemberToCohortAction`, `grantable_roles_for` (all staff); and line 60 `current_role_entries` from the flat `staff.py`.
  - **Module-object access**: `actions_module.REFUSAL_MESSAGES` at 3651 (staff; AttributeError after the move). `mocker.spy(actions_module, "can")` at 7019 is learner code (a bulk run reads permitted learners once) and still resolves, since `can` remains in the flat `actions.py`.
  - **String patches targeting staff names, 21 of them** (the idea says "about 17"; the count today is 21): `assign_role` at 3543, 3941, 3959, 9660; `grantable_roles` at 3746, 3864, 3884, 3910, 4107, 4149, 4292, 4922, 4982, 5144; `current_role_entries` at 4512; `cohorts_visible_to` at 4549 (via `_reach_only`, 4546-4552); `deactivate_role` at 4837, 5232; `grantable_roles_for` at 9304, 9468, 9526. Each repoints to `freedom_ls.educator_interface.panels.staff.actions.<name>`. Two non-staff patches in this file stay: `move_between_cohorts` (2620) and `record_learner_entry` (6309).
  - Patches at 4691 and 5386 target `freedom_ls.learner_management.role_assignment.is_last_organisation_admin`, unaffected.
  - Relevance check on the looked-up-module rule: `cohorts_visible_to` is imported into both the flat `actions.py` (learner code at 849, 947, 1000, 1346) and the staff block (`role_reach`, line 231). The patch at 4549 must follow the staff copy, which is where `_reach_only` needs it. After the move the staff copy lives in `panels/staff/actions.py`, so it needs its own `cohorts_visible_to` import and the patch string repoints there.
- Other tests (`test_staff.py` for flat `staff.py`, `test_forms.py`, `test_sidebar.py`, `test_dashboard.py`, playwright) have no staff-name import or patch. Playwright tests `test_members_flow.py`, `test_deactivate_reactivate.py` and `test_cohort_settings_staff_flow.py` drive the UI only.
- No `mock.patch`, `mocker.patch` or `patch.object` for a staff name exists anywhere in `freedom_ls/`; all are `monkeypatch.setattr("dotted.string", ...)`.

### 3.3 Docs and skills

- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` names no staff module or class. Line 41 cites `freedom_ls/educator_interface/filters.py` for the audit filters (refactor-2's concern). No edit for staff.
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` line 231 lists "`StaffDataTable`, `AddStaffMemberAction`, `STAFF_ROLES`, `staff_of`" as examples of Python names that say "staff". It names no file path. No edit is required.
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` line 297 points to `educator_interface/views.py` as "the worked example, with `compact = True`" (not staff-specific); not part of this spec.
- No match for the staff names in `docs/`, `config/`, `CLAUDE.md` or `README.md`.

## 4. Current test slices

Caution: the idea's ranges (main's 3157-5735 and 8560-9444 in `test_actions.py`; 2811-3740 in `test_views.py`) are stale. Re-derived below.

### 4.1 `tests/test_actions.py` (about 9,800 lines)

Staff slice A, cohort-less staff dialogs and the cohort-scoped add dialog: **3311-5908**. It starts at the `@pytest.mark.django_db` decorator above `test_grantable_roles_are_cached_on_the_request` (3312) and ends with `test_the_cohort_dialog_does_not_tell_an_organisation_admin_about_rank` (5900-5908). Sub-blocks:
- add member dialog and lookup: 3323-4118
- add role to chosen cohorts: 4119-4395
- remove role, deactivate role: 4397-4858
- change cohorts: 4860-5238
- staff member state (suspend and reactivate): 5240-5503
- search: 5505-5706
- cohort-scoped add (the `AddStaffMemberToCohortAction` URL tests): 5708-5908

Staff slice B, who a cohort admin may add through `AddStaffMemberToCohortAction`, and the cohort role actions: **8618-9546**. It starts at the comment `# who a cohort admin may add` and runs through `test_the_change_role_dialog_offers_only_grantable_cohort_roles_with_the_held_one_checked` (9518-9546). It holds `AddRoleAction` tests (8747-8911), the staff-viewer scoping tests (8913-9115), `RemoveStaffFromCohortAction` (9167-9329) and `ChangeRoleAction` (9331-9546).

Staff slice C, one stray test: **9651-9670** `test_a_refused_role_change_is_a_message_dialog`, sitting in the shared "message dialog" block (9549-9672 around the shared `_assert_message_dialog`). The shared block (the helper at 9549 plus the learner and cohort tests at 9561-9648) stays.

Total about 3,550 lines (slice A 2,598, slice B 929, slice C 20).

Other staff-related lines inside non-staff territory of the same file, which stay in `test_actions.py`:
- 6427-6437: `_reason_remove_role` and `_reason_suspend_member`, and entries in `REASON_DIALOGS` (6440-6448). They are parametrised with learner and cohort dialogs.
- 8491-8497 and 8512-8514: staff branches of `_single_row_dialog_url` and `_SINGLE_ROW_DIALOG_WEIGHTS`, again parametrised with learner and cohort dialogs.

**Dependency problem for the split.** The cross-cutting blocks above call helpers defined inside slice A: `_staff_member_holding` (4401), `_remove_role_url` (4397), `_state_url` (5240) and `_cohort` (4119; used at 6428, 6436, 8628 and in slice B). So the helpers cannot simply travel with the slice; either keep a shared copy in `tests/helpers.py` (which already holds `_interface_url`, `_bulk_*`) or let `test_actions.py` import them from the new `tests/panels/staff/test_actions.py` (importing from a test module is poor practice). The spec must decide.

Shared fixtures and helpers the staff slices use from the top of the file or from conftest:
- `_post` (148-149), defined in the learner/cohort part and used by ~170 non-staff call sites. Staff uses it at 3339, 3351, 4138, 4419, 5253, 5717, 9178, 9346, 9565 and elsewhere.
- `_interface_url`, imported from `tests/helpers.py` (line 61-68).
- `panel_request` fixture from `tests/conftest.py` (used by `test_grantable_roles_are_cached_on_the_request`).
- Root-conftest fixtures: `mock_site_context`, `logged_in_client`.
- **`organisation` fixture** is defined at 3370-3372, inside slice A, but is used by every test in the file from line 176 onward (it is a module-level fixture, so the position does not matter). Cutting slice A out would leave learner and cohort tests without it. It must move to `tests/conftest.py` (where `panel_request` already lives) or remain behind. `tests/test_learner_import.py:76` defines its own `organisation`, so it has no conflict.
- **`admin_client` fixture** (3375-3378), used only in slices A, B and C (about 60 uses). It moves with the slice. Its builder `_holder_client` (3330-3335) is also used only there.
- Local staff helpers: `_add_staff_member_url`, `_lookup`, `_submit_role`, `_confirm`, `_text`, `_role_values`, `_cohort_post`, `_remove_dialog`, `_remove`, `_active_roles`, `_change_*`, `_state_*`, `_staff_member_row` (5256), `_search`, `_options`, `_cohort_overview_*`, `_cohort_viewer_cohorts`, `cohort_admin_setup`, `_cohort_admin_ctx`, `_lookup_in_cohort`, `_add_role*`, `viewing_cohort_admin`, `colleague_with_roles_elsewhere`, `_remove_staff_from_cohort*`, `_change_role*`.
- `cohort_admin_setup` and `_cohort_admin_ctx` (8625-8649) import `CohortConfig` from `views`, which stays until the cohort spec.
- `_assert_message_dialog` (9549), shared with learner tests and used by slice C. It stays; slice C needs it, so it should be shared as well.

The module-level imports in `test_actions.py` lines 5-124 include many staff-only imports (`REFUSAL_MESSAGES`, `AddStaffMemberToCohortAction`, `grantable_roles_for`, `current_role_entries`, `STAFF_CHANGED`, `GrantableRole`, `assign_role`, `deactivate_role`, `RefusalReason`, `RoleChangeRefused`, `StaffMember`, `ObjectRoleAssignment` and so on). Ruff will tell which now go unused in the remainder.

### 4.2 `tests/test_views.py`

Staff section slice: **2962-3921**, from the `role_holder_client` fixture to `test_the_viewers_own_row_offers_neither_state_action`. About 960 lines. Everything the slice defines (`role_holder_client`, `_grant_staff_member`, `_staff_document`, `_staff_member_row`, `_scope_lines`, `QUERY_BOUND`, `MARKERS`, `_marker_labels`, `_hold`, `_staff_quick_view_text`, `_make_viewer_and_subject`, `_member_emails`, `_members_search`, `_remove_triggers`, `_change_cohorts_triggers`, `_state_triggers`, `_make_site_level`, `_turn_off`, `ONLY_STAFF_MEMBER_LINE`, `VIEWER_ROLE_SECTIONS`) is used only inside the slice. `QUERY_BOUND = 66` has a same-named constant in `tests/invariants/test_course_shares.py` (69; value 53) but they are independent. It uses `_interface_url` and `_get_document` from the top of the file (153-166); and `GrantableRole`, `custom_role_config`, `SettingsWrapper`, `assign_role`, `StaffMember` imports. So `_interface_url` and `_get_document` need a shared home (or a duplicate) once the slice moves.

Note: `tests/test_views.py` is the old name for what the idea calls main's 2811-3740 range; nothing in the slice was renamed. The two `actions.grantable_roles` patch strings are at 3784 and 3815 (inside the slice).

Cohort-area tests that sit inside or beside the slice and do NOT move: 3633-3656 (the cohort Settings and History panels refresh on `staffChanged`); the cohort Settings staff panel tests at 1309-1620 (`_staff_section`, `_staff_on` and the rest, cohort area, driving `AddStaffMemberToCohortAction` through `CohortConfig`).

Proposed split of the slice. Almost every test is a page-level HTTP test that exercises table, config and cell templates together, so the cut is by the part under test, not by how the test is wired. Proposal:

`tests/panels/staff/test_data_tables.py` (the rows, columns, cells, sorting, search, filter links, empty states and per-row triggers `StaffDataTable` produces):
- 2985 (names and emails), 3041 (nameless member), 3068 (name escaped)
- 3113-3163: roles cell reads whole organisation, two cohorts, four cohorts, inactive cohort marker
- 3224-3290: row markers (`_make_viewer_and_subject`, each marker, inactive muted, own row "You")
- 3303 (names-only viewer sees no roles or buttons), 3352 (page lists only roles the site defines), 3374 (roles viewer, no buttons)
- 3399 (no `StaffMember` row is inactive), 3414 (superuser with one cohort role), 3428 (cohort name escaped)
- 3441 (query bound), 3485-3547 (search, role filter narrowing, default link, mobile select), 3576 (header sort link), 3588, 3604, 3618 (empty and no-match messages)
- 3660-3921: per-row triggers (own row, cohort admin's own row, remove, change cohorts, state actions, site-level and turned-off rows)

`tests/panels/staff/test_config.py` (section-level behaviour `StaffConfig` owns: `view_capability`, `authorise_instance`, `get_intro_context`, `get_cell_context`, `refresh_events`, nav visibility):
- 3013 (staff section 404 for a cohort role holder), 3024 (site admin with no role can open it), 3058 (an id under `staff/` is a 404)
- 3329 (a staff viewer role gets 404 on other sections; parametrised over the other sections), 3341 (sidebar of a staff viewer lists Staff alone)
- 3555 and 3565 (the only-staff-member intro line: `get_intro_context`)
- 3000 (cohort role holders see no Administration group) and 3387 (a cohort admin still gets the dashboard) are shell-level, not staff-specific. They can move into `test_config.py` or stay in `test_views.py`; the spec decides. `test_the_first_use_message_is_a_sentence` and its sibling, the `EDUCATOR_TABLES` parametrisation (7498-7530), stay in `test_views.py` and only change the `StaffDataTable` reference.

`tests/panels/staff/test_quick_view.py` (does not exist yet; justified by 2 real tests): `_staff_quick_view_text` (3166-3180), `test_a_role_names_who_added_it` (3183-3199) and `test_a_role_with_no_recorded_grantor_reads_added_without_a_by_clause` (3202-3221). `tests/test_quick_views.py` itself contains no `StaffQuickView` class. Its only staff test is `test_a_malformed_pk_of_a_staff_row_404s` (781-788), which hits `StaffConfig` instance authorisation through the quick-view URL; it could go to `test_config.py`. The idea expected `test_quick_view.py` "if any `StaffQuickView` tests"; they exist in `test_views.py`, not `test_quick_views.py`.

Judgement calls the spec should settle: whether tests that exercise cell templates but not `StaffDataTable` itself (the row-trigger tests 3660-3921) belong in `test_data_tables.py` (the table holds the columns that render them) or `test_actions.py` (they test which actions `is_offered`). The cleanest rule is by what the assertions read: they read table rows, so `test_data_tables.py`.

### 4.3 `tests/test_filters.py`

Staff slice: **288-507**, from `_staff_member_pks` (288) to `test_the_role_choices_carry_the_display_names` (493-506). It contains the `staff_request` fixture (299-303), the role filter tests (306-420), `_staff_toolbar` (424-440) and the "names-only viewer" tests (443-506). Many use `StaffDataTable` (`filter_queryset`, `get_queryset`, `get_context`, `parse_query`), so the module `tests/panels/staff/test_filters.py` imports `StaffDataTable` from `panels.staff.data_tables`.

Uses top-of-file imports: `_educator_request` (tests.helpers, also used by other tests in the file), `TableQuery`, `OrganisationFactory`, `CohortFactory`, `UserFactory`, `assign_role`, `pytestmark = usefixtures("_site_context")` (line 51, so the new file needs the same pytestmark). Exports it contributes to the shrink: remove `StaffRoleFilter` (24) and `StaffDataTable` (36). Following refactor-2's removal, the audit slice from 509 (`audit_request`) to the end also leaves.

### 4.4 `tests/test_quick_views.py`

No `StaffQuickView` tests. The one staff-adjacent test is at 781-788 (see 4.2). The file's docstring says "The learner and cohort quick views", so it already excludes staff.

### 4.5 Other staff-area test files

`tests/test_staff.py` tests flat `staff.py`, which stays, so it stays. Playwright files stay.

## 5. The test-mirroring hook and `mirroring_baseline.txt`

How it works (`claude_plugins/django-stack/scripts/check_test_mirroring.py`, configured in `pyproject.toml` `[tool.test_organisation]`, lines 103-109):
- It walks every `*.py` under each app, skipping `tests/playwright/` and skipped dirs. A collected file (`test_*.py`) must live at `<app>/tests/<sub...>/test_<name>.py` with `<app>/<sub...>/<name>.py` or `<app>/<sub...>/<name>/__init__.py` existing (the `conforms` function).
- Anything else is a "violation". A violation passes only if its path is in `test_organisation/mirroring_baseline.txt` (debt; lines may only be deleted) or covered by `test_organisation/mirroring_exemptions.txt` (reasoned, permanent). A baseline line that is no longer a violation fails as stale, and so does an exemption that covers no violation.
- `tests/invariants/` in educator_interface is exempted (line 18 of the exemptions file).

What this means for the staff move:
- `tests/panels/staff/test_actions.py`, `test_config.py`, `test_data_tables.py`, `test_filters.py` and `test_quick_view.py` conform, because `panels/staff/{actions,config,data_tables,filters,quick_view}.py` will exist. A `test_*.py` for a module that does not exist (for example `test_panels.py`) would be a new violation; the checker would fail it.
- `quick_view.py` (singular) is the module name the idea picks; the test must be `test_quick_view.py` to match.
- Existing precedent for this layout: `tests/panels/common/test_{bulk_actions,request,badges,filters,report}.py` mirror `panels/common/*.py`.
- Flat tests that stay conform because their flat modules stay: `test_actions.py` (`actions.py`), `test_views.py` (`views.py`), `test_filters.py` (`filters.py`), `test_quick_views.py` (`quick_views.py`), `test_staff.py` (`staff.py`).

`mirroring_baseline.txt` today, educator_interface block (lines 36-45): `test_cohort_delete_action.py`, `test_course_visibility_and_interest.py`, `test_create_cohort_action.py`, `test_dashboard.py`, `test_document_title.py`, `test_interface_urls.py`, `test_learner_section.py`, `test_organisation_switcher.py`, `test_sidebar.py`. **None of these files is touched by the staff move**, so refactor-3 has no baseline line to delete (the idea expects "any line the move makes stale"; there is none today). `test_dashboard.py` (line 40) is refactor-2's. `test_actions.py`, `test_views.py`, `test_filters.py` and `test_quick_views.py` are not in the baseline.

The import-contract side (`test_organisation/import_contracts.toml` section `id = "educator_interface"`, 190-198, and `import_baseline.txt` 46-47) polices what `freedom_ls.educator_interface.tests` imports. Test modules under the new `tests/panels/staff/` are inside the `tests` prefix, so they are covered by the same contract. The new tests import the same third-party and app modules as before, so no new edge is expected. The single baselined edge is `test_course_visibility_and_interest -> course_interest.factories`, unrelated.

Housekeeping: every new directory needs an empty `__init__.py` (`panels/staff/__init__.py`, `tests/panels/staff/__init__.py`). `tests/panels/__init__.py` and `tests/panels/common/__init__.py` already exist. Package `__init__.py` files let `tests/panels/staff/test_filters.py` and `tests/test_filters.py` coexist, as `tests/panels/common/test_filters.py` already does.

## 6. Size and natural seams of the staff actions (record only)

Default per the idea is one `panels/staff/actions.py` of about 1,370 lines. If a split were wanted, the seams in the code are:

1. Role helpers and refusal/state helpers (200-286 and 1496-1617, about 210 lines): `grantable_roles_for`, `roles_grantable_on`, `role_reach`, `actionable_roles`, `role_entries_shown_to`, `has_grantable_roles`, `REFUSAL_MESSAGES`, `role_refusal_response`, `staff_member_changed_response`, `staff_member_state`, `_entries_after` and the rest. Everything else imports these, and none of them import the action classes (only the lazy `views` import). This is the cleanest seam.
2. Add flow (1620-2205, about 585 lines): `AddStaffMemberAction` (495 lines, with 30-odd methods), plus `AddRoleAction` (2129) and `AddStaffMemberToCohortAction` (2173), which subclass it. `StaffRowMixin` (2116) is needed by `AddRoleAction`, so it would have to live with the helpers or the base.
3. Cohort-scoped role actions (2207-2384, about 180 lines): `CohortRoleAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`. The cohort area draws all three, as `AddStaffMemberToCohortAction` too.
4. Per-row role actions (2386-2685, about 300 lines): `StaffRoleAction`, `DeactivateRoleAction`, `CohortChange`, `ChangeCohortsAction`.
5. Member state (2687-2772, about 85 lines): `StaffMemberStateAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction`.

Coupling that would constrain a split: `StaffRowMixin` is a base of four classes across seams 2, 3, 4 and 5. `_organisation` and `_refused` are used by every action. `ChangeCohortsAction` and `DeactivateRoleAction` both inherit `StaffRoleAction`. The idea explicitly chose one module, and the tests (slice A, B, C) are not organised along these seams either (they cluster by dialog).

## 7. Likely conflicts with refactor-2 (`dashboard-and-audit-log`, in progress on another branch)

Refactor-2's idea (`spec_dd/2. in progress/educator-interface-refactor-2-dashboard-and-audit-log/idea.md`) moves: `DashboardConfig`, `DashboardPanel` and the dashboard half of `reporting.py`; `AuditLogConfig`, `OrganisationAuditLogTable`, `AuditLogEntryTable`, `TargetedAuditLogEntryTable`, `_record_export` and friends, `HistoryPanel`; the audit filters (`AuditActorFilter`, `AuditActionFilter`, `AuditPeriodFilter`); the audit and dashboard test slices. No class is moved by both specs, but they edit the same files in adjacent hunks:

| File | Staff edit | Refactor-2 edit | Conflict shape |
|---|---|---|---|
| `views.py` import block | drops 12 staff names, repoints 4, adds `StaffConfig`; trims queries import | drops `DashboardConfig`/audit imports, adds new config imports; probably touches `quick_views`/`reporting`/filters import lines | **Same lines of one import block.** The `filters` import (118-126) loses `StaffRoleFilter, may_see_staff_roles` from one end and the three Audit filters at the other. Expect text conflicts to resolve by hand. |
| `views.py` body 2485-2734 | removes 2492-2641 | removes `DashboardConfig` 2485-2489 and 2644-2725 | The staff block sits **directly between** the dashboard and audit-log blocks. Both specs delete a hunk adjacent to the other's, plus the `interface_config` list at 2728-2734 (staff changes the `StaffConfig` reference's import, refactor-2 changes the Dashboard and AuditLog references). Likely textual conflict on `interface_config` and its neighbouring blank lines. |
| `filters.py` | removes 100-156 | removes 159-end audit filters (`AuditActorFilter`, `AuditActionFilter`, maybe `AuditPeriodFilter`) | **Adjacent hunks** (staff 100-156 abuts `AuditActorFilter` at 159) plus the shared import header (lines 5-38). After both land, the flat `filters.py` keeps only the three learner filters; many imports become unused. |
| `quick_views.py` | removes 152-171 and the `STAFF_CHANGED`/`current_role_entries`/`TYPE_CHECKING` imports | likely none (audit and dashboard have no quick view) | Low risk. |
| `actions.py` | removes 200-286, 1496-2772, many imports | expected none (neither area has actions here) | Low risk; only the shared import header, where refactor-2 may have no change. |
| `reporting.py` | none | dashboard half moves | None. |
| `tests/test_views.py` | removes 2962-3921, repoints 3784, 3815 and 7507 | removes audit slices (about 4044-4570 and 7317-7680 on main) and repoints 7508 | The staff slice (ends 3921) sits close to the audit slice (starts about 4044). The `EDUCATOR_TABLES` list (7498-7509) has `StaffDataTable` and `OrganisationAuditLogTable` on adjacent lines, so both specs edit it. Also the import block at line 85+ (`from ...views import (`). |
| `tests/test_filters.py` | removes 288-507 and the `StaffRoleFilter`/`StaffDataTable` imports | removes 509-end, `AuditActorFilter`/`AuditActionFilter`/`AuditLogEntryTable` imports | **The two removed slices are adjacent** (staff ends 507, audit starts 509, with the `audit_request` fixture at 509-516) and both edit the import block (18-37). |
| `tests/test_dashboard.py`, `mirroring_baseline.txt` | none | repoints `test_dashboard.py` and deletes baseline line 40 | The staff spec edits no baseline line, so no conflict, but both touch the file if the staff spec chooses to tidy it. |
| `tests/invariants/test_config_authorisation.py` | repoints the `StaffDataTable` import (34) | unlikely, unless it also touches audit imports at the same block | Low. |
| `tests/panels/` | creates `tests/panels/staff/` | creates `tests/panels/dashboard/` and `tests/panels/audit_log/` | New dirs, no overlap; `tests/panels/__init__.py` already exists. |

Cross-dependencies rather than conflicts: refactor-2 states the audit tables need no sibling imports, and its audit `HistoryPanel` is used by learner and cohort areas, not staff. Staff code uses nothing from the dashboard or audit areas. So the two specs can merge in either order; only mechanical conflicts remain.

## 8. Other facts worth carrying into the spec

- The `views.py` shell `interface_config` list (2728-2734) is `NavGroup("Administration", [StaffConfig, AuditLogConfig])`. Nav order does not change.
- `panels/common/request.py` already declares `grantable_roles`, `role_reach`, `may_see_staff_roles` and `works_with_cohorts` request attributes, which the staff helpers set on the request (by `scoped.grantable_roles = ...`). No change needed there.
- `educator_interface/templates/educator_interface/{modal,partials,data-table-cells,quick_views}/staff*` template paths do not change.
- Standalone import guard: `freedom_ls/panel_framework/tests/test_import_guard.py` checks `panel_framework` imports only; the staff modules import nothing from there that is new.
- Ruff and import ordering: the repo sorts imports with isort-style grouping (`freedom_ls` first-party). The new modules need the same ordering.

status: ok
