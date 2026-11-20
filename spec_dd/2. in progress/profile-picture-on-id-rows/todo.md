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
- [x] (user) Allow deleting Gone Learner's CourseProgress (efb2ba71-…) and Learner (fc1c44ac-…) in the dev DB, which the permission system blocked during QA, then re-run QA Test 6.3–6.4 (a cached row whose Learner is gone shows initials); or accept the unit-test coverage and tick this

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Document `panel-attention-row`'s new `picture_url` attribute with an example in `freedom_ls/panel_framework/templates/panel_framework/reference/_examples.html` (spec: "Documentation and downstream")
- [x] (cmd) Document `panel-attention-row`'s `picture_url` (passed bound, empty shows initials) in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (spec: "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [x] (user) Fix the failing test `freedom_ls/educator_interface/tests/test_views.py::test_a_bulk_run_entry_by_the_runs_own_actor_names_them_without_a_second_avatar` (a bulk-run audit entry by the run's own actor still renders a second avatar span; fails 3/3 on its own, so not flaky), then re-run `/sdd:finish_worktree`
- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
