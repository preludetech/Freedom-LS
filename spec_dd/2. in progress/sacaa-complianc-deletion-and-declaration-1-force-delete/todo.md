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
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether to fix tests/test_select_tests.py::test_malformed_remote_entry_exits_2_naming_the_key: its three cases fail whenever DS_TEST_REMOTE=off is set in the environment (as local full runs set it), because the variable leaks into the test; they pass with it unset. Not caused by this branch; a fix would clear the variable in the test (monkeypatch.delenv).

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: in `docs/api.md`, add `last_active` to the user API's field table and say it does not move `updated_at` (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:document`: in `freedom_ls/audit_log/README.md`, add `user.deleted` and `learner.removed` to the action table with label, group, target, subjects and details (spec "Audit log" and "Documentation and downstream")
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add the two codes under "Changes" and define "force delete" and "last active" (spec "Terminology" and "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
