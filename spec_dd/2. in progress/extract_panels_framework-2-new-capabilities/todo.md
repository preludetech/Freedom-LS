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
- [ ] (user) Decide whether to stabilise `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`: it timed out on a visibility check in two full runs on a loaded machine and passes when run alone
- [ ] (user) Review three changes made beyond the plan: `modal/confirm.html` takes an optional `title_id`, the component reference page loads `panel_framework/js/alpine-components.js`, and `panels.py` has a new shared `table_region_context` function; keep them or ask for another approach
- [x] (user) Keep or delete `freedom_ls/qa_helpers/management/commands/qa_create_course_structure_variants.py`, a QA data command written during QA that builds QA Multi Page Course and QA Long Course; it is untracked, so commit it to keep it or delete the file

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, document the reason variants (`reason_required`, `reason_choices`), `show_as_of`, row detail, child rows, per-row templates, sequence-backed tables, `DEFAULT_PAGE_SIZE` and `compact` (spec "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, add `childRows` to the component inventory and drop `courseOutline` (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
