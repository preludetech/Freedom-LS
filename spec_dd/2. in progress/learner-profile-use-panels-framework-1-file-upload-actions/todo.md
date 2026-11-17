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
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether to chase the order-dependent failure of freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details (TypeError: 'Mock' object is not iterable): it failed once in a full run on this branch, passed on re-run and in every later full run, and the branch does not touch audit_log; if it recurs, find the test that leaks the Mock
- [ ] (user) Check the change to freedom_ls/educator_interface/forms.py: eight educator forms now accept a files argument, because the panel framework now passes files to every form action; the plan had expected no host changes
- [ ] (user) Decide whether to keep the QA data helper's 4-line addition to .claude/agent-memory/sdd-qa-data-helper/reference_dev_org_baseline_command.md (it notes that qa_create_dev_org_baseline creates QA cohort A); it is left uncommitted: commit it or discard it with git checkout

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Add a "Forms with a file field" section to `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, and `widgets.py` to its list of modules, from the spec's "Documentation and downstream" section: what the host owns (the storage alias per `fls-dev:file-storage`, size and type validators in the form, a reverse-proxy body limit at or above the largest allowed file) and the `requestConfig.panelErrorShown` contract for a host's own error handling
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
