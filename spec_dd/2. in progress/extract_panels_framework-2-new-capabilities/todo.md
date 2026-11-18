# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether to stabilise `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`: it timed out on a visibility check in two full runs on a loaded machine and passes when run alone
- [x] (user) Review three changes made beyond the plan: `modal/confirm.html` takes an optional `title_id`, the component reference page loads `panel_framework/js/alpine-components.js`, and `panels.py` has a new shared `table_region_context` function; keep them or ask for another approach
- [x] (user) Keep or delete `freedom_ls/qa_helpers/management/commands/qa_create_course_structure_variants.py`, a QA data command written during QA that builds QA Multi Page Course and QA Long Course; it is untracked, so commit it to keep it or delete the file
- [x] (cmd) Run the full test tier for commit 5db78f2d3 (panel button hit area, card spacing); skipped at the user's request
- [x] (user) Decide on two browser tests that fail since 5db78f2d3 (phone buttons are now 32px with an invisible 44px hit area, but these still measure the button box): `test_members_flow.py::test_phone_row_actions_and_toolbar_controls_meet_the_touch_target` and `test_learner_import_flow.py::test_import_a_file_with_errors_then_download_the_error_rows`; update them to measure the hit area, or change the buttons back

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, document the reason variants (`reason_required`, `reason_choices`), `show_as_of`, row detail, child rows, per-row templates, sequence-backed tables, `DEFAULT_PAGE_SIZE` and `compact` (spec "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, add `childRows` to the component inventory and drop `courseOutline` (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [x] (cmd) PR #251 review fix: a row-template row keeps the bulk-selection and row-detail cells (review finding 1)
- [x] (cmd) PR #251 review fix: sequence rows come from `DataTablePanel.get_row_sequence`; `get_queryset` is QuerySet-only; `_require_queryset` removed; sequence validation runs once at class creation; bulk-action bans check unpermitted actions too (review findings 2, 3, 6, 8, 9)
- [x] (cmd) PR #251 review fix: the course outline shows on one page and its footer counts content rows only (review finding 4)
- [x] (cmd) PR #251 review fix: `show_as_of` with `as_of=None` draws no stamp (review finding 5)
- [x] (cmd) PR #251 review fix: extract the child-rows chevron partial; the outline card includes the title partial (review finding 7)
- [x] (cmd) PR #251 review fix: rename `DEFAULT_PAGE_SIZE` to `PANEL_TABLE_PAGE_SIZE` (review finding 10)
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
