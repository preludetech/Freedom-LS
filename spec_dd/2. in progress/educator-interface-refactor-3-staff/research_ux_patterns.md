# Research: UX patterns for the staff area move

Scope: the move is pure, so the UX job is to keep it that way and prove it. No outside sources were needed. Everything below comes from the repo.

## User-facing surfaces the move must not change

Organisation staff section (`/<org>/staff/`):
- Staff data table (cards below the table breakpoint, table above), the role filter, the search box (`#staff-q`), the "No staff members match these filters." empty state and "Clear filters".
- Quick view (`StaffQuickView`, template `quick_views/staff.html`).
- Toolbar "Add staff member" button and its modal (`modal/add_staff_member.html`): search listbox (`#staff-search-input`, `#staff-search-listbox`, `#staff-search-results`; `SEARCH_LISTBOX_ID` moves with the code, so its value must stay), then the role step.
- Row actions: add role, change role, deactivate role, change cohorts, deactivate and reactivate staff member. Their modals are `change_role`, `change_cohorts`, `deactivate_role_confirmation`, `deactivate_staff_member_confirmation` and `reactivate_staff_member_confirmation`.
- Refusal and state responses (`REFUSAL_MESSAGES`, `refusal_response`, `staff_member_changed_response`). Message text, HTTP status and any HTMX headers (HX-Trigger, retarget) must stay identical.
- The lost-access flow, which lands on the not-found page via `refusal_response`.

Cohort Settings tab staff actions: `panels/cohort_staff.html`, the add, change and remove actions (`AddStaffMemberToCohortAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`, modal `remove_staff_from_cohort_confirmation.html`), and the history entry shown afterwards.

Templates, URL names, URL paths and the app label stay, so no template should need to be edited. A template diff in the PR is a red flag.

## Existing Playwright coverage (`freedom_ls/educator_interface/tests/playwright/`)

- `test_members_flow.py`: the main staff coverage. Add, change and remove a cohort admin; cards vs table; the clear-filters empty state; touch targets at phone size; the add-member button staying in view at 375px; long-email overflow; the change-cohorts dialog on a phone; search-results alignment.
- `test_cohort_settings_staff_flow.py`: a cohort admin changes then removes a viewer and reads it in the history.
- `test_lost_access_flow.py`: navigation and confirm after losing access (staff page).
- `test_section_smoke.py`: each section loads with no console errors (the `staff` row).
- `test_cohort_detail_mobile.py`, `test_touch_targets.py` and `test_keyboard_flow.py` are cross-cutting. The grep found no `staff` text in the last two, so treat them as light cover.
- `test_deactivate_reactivate.py` and `test_register_deactivate.py` are about cohorts and registrations, not staff. There is no Playwright test for the staff deactivate and reactivate flow, so only the Django tests cover it.

Cross-cutting Django tests that stay in place and need repointing only: `invariants/test_permission_matrix.py` (about 105 staff hits), `invariants/test_organisation_isolation.py`, `invariants/test_config_authorisation.py`, and `interface_walk.py`.

## How to verify "no UX change"

1. Run the full suite. Moved Django tests are the main proof, and patch strings must be checked by running them, not by grep (as the idea says).
2. Run the Playwright staff files above (`test_members_flow`, `test_cohort_settings_staff_flow`, `test_lost_access_flow`, `test_section_smoke`) before and after the move. They cover phone and desktop sizes already.
3. Template and static guard: `git diff --stat` for the PR must show no change under `templates/` or `static/`. Any change to them means the move was not pure.
4. HTMX response equivalence (cheap, high value): the moved actions are tested through the test client. Spot-check that the moved tests are unchanged in their assertions, and that only import and patch strings differ. Diff the test bodies (for example `git diff --color-moved` between the old and new test files) so moved blocks appear as moves, not edits.
5. Gaps worth a one-off manual smoke at 375, 768 and 1280px: staff deactivate and reactivate (no Playwright cover), the role filter, and the staff quick view. Do this once after the move. No new tests are needed for a pure move.
6. Visual regression tooling is not used in this repo for this area. Adding it is out of scope for a pure move, so rely on points 1 to 5.

## Risks specific to the move

- A wrong patch or `monkeypatch.setattr(module, ...)` target silently stops mocking and may still pass. Make sure the Playwright and Django runs exercise the real refusal paths.
- A stale import of a moved name in the cohort area would show up as a broken Settings tab, which is why `test_cohort_settings_staff_flow.py` should be in the verification set.
- The lazy `interface_config` import in `refusal_response` must be repointed to its new module path, or the refusal and lost-access paths fail only at run time.

status: ok
