# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [ ] (human) Decide whether to fix the existing underscore-named autouse fixtures in `freedom_ls/conftest.py` (`_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides`, `_clear_*`): `from freedom_ls.conftest import *` skips underscore names, so concrete projects never get them. Found by the spec review; outside this spec's scope.

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/testing/SKILL.md`, "Fixture placement", add `fast_password_hasher` to the autouse list and name `production_password_hashers` as the opt-in (spec, "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: write `timings.md` in this spec directory with test-body times, before and after, for `freedom_ls/course_access` and `educator_interface/tests/invariants/test_permission_matrix.py::test_can_matches_the_matrix`, measured as `spec_dd/1. next/faster-test-runs/research_test_timings.md` did. Take the before sample with a temporary `fast_password_hasher` that yields the configured list without overriding, then delete it (spec, "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
