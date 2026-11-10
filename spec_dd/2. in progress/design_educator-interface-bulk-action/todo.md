# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items and the two PR commands. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Fix the tests the full run after the QA fixes left failing: freedom_ls/learner_interface/tests/views/test_dashboard.py::test_in_progress_query_count_does_not_grow_with_cards_carrying_deadlines (71 queries vs a limit of 70; it fails the same way on main, so it is pre-existing and likely date-dependent)

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, rewrite the "Selection bar" section, the partial list line that names `table_selection_bar` and the visual-checklist line that names the selection bar to match the spec's Decisions (bar above the table from `lg`, fixed to the bottom below `lg`, ghost text-only buttons, More menu, Select all / Deselect all / Clear), from spec section "Documentation and downstream"
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, update the `tableSelection` row to say the component lives on the table region and covers the toolbar, the bar and the table, from spec section "Documentation and downstream"
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
