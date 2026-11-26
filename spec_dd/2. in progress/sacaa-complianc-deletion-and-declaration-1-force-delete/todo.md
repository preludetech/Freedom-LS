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
- [ ] (user) Decide whether to fix the admin user change page (/admin/freedom_ls_accounts/user/<pk>/change/) scrolling sideways at 375px width; the post-rebase front-end check saw it, and main's changes in that rebase touched no template, so it predates the rebase
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether to fix freedom_ls/learner_interface/tests/playwright/test_course_browse_flow.py::test_learner_browses_a_course: it failed once in the remote full run after the rebase onto main (the replayed pronunciation button stayed aria-pressed="false" at line 471) and passed when re-run locally. It is main's audio test, untouched by this branch, so it looks like a timing flake in main
- [x] (user) Decide whether to fix tests/test_select_tests.py::test_malformed_remote_entry_exits_2_naming_the_key: its three cases fail whenever DS_TEST_REMOTE=off is set in the environment (as local full runs set it), because the variable leaks into the test; they pass with it unset. Not caused by this branch; a fix would clear the variable in the test (monkeypatch.delenv).
- [x] (user) Decide whether the force delete confirmation page should hide Django's auto-created many-to-many join rows (it now lists 'Questionanswer-questionoption relationships', the links between a quiz answer and its chosen options) or show them under a readable name, then fix the page with a failing test first (QA bug B3 in qa_report.md)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: in `docs/api.md`, add `last_active` to the user API's field table and say it does not move `updated_at` (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: in `freedom_ls/audit_log/README.md`, add `user.deleted` and `learner.removed` to the action table with label, group, target, subjects and details (spec "Audit log" and "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add the two codes under "Changes" and define "force delete" and "last active" (spec "Terminology" and "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
