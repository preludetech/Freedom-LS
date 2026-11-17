# SDD Todo

Checklist for finishing the PR #224 review fixes. Commands tick their own item; you tick `(user)`
items. See `claude_plugins/sdd/commands/README.md`.

## 1. Implementation and QA

- [x] (cmd) Fix the PR #224 review findings
- [x] (cmd) Open PR #247 and review it
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the QA report and decide the unresolved items
- [x] (cmd) Fix B2: the validator header counts errors as files ("Validation failed for 2 file(s)" for one file)
- [x] (cmd) Fix B3: the override picker labels two placements of one child identically
- [x] (cmd) Fix the failing `content_engine/tests/test_signals.py::test_signal_names_the_children_a_load_moved`, once it is decided whether a row outside the load's own collections counts as moved

## 2. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Confirm PR #247 is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 3. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
