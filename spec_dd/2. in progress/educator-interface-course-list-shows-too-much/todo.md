# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Force-push the rebased branch: `git push origin HEAD --force-with-lease --force-if-includes` (auto mode blocked it; the remote still holds the pre-rebase history)
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Decide whether the cohort Report tab's course completion table should name the owner of a shared course (it still shows the bare title, so Harbour's and Northwind's Workplace Safety Essentials read alike there)
- [ ] (user) Decide whether the educator CSV exports should name the owner of a shared course (they still carry the bare title)
- [ ] (user) Look at two Playwright tests that failed in the full parallel run after the QA fixes and passed when re-run alone: freedom_ls/educator_interface/tests/playwright/test_learners_list_flow.py::test_a_background_bulk_run_keeps_the_reader_on_the_table_until_it_finishes and freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer (likely flaky under load)
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether to keep QUERY_BOUND = 60 in freedom_ls/educator_interface/tests/invariants/test_course_shares.py (raised from the measured 54 because a cold per-process cache adds a query or two to the first request under some test orders), or pin it tighter by warming the cache with one request before measuring; then tick this
- [x] (user) Decide what to do about QA bug: two courses with the same title (Harbour's own and Northwind's shared Workplace Safety Essentials) are indistinguishable in the educator Courses list, course filters and register pickers — decide how to tell them apart, e.g. show the owning organisation beside a shared course (TDD: failing test first, then fix)
- [x] (user) Keep or discard the edits the QA data helper made to .claude/agent-memory/sdd-qa-data-helper/reference_empty_db_baseline.md and reference_org_course_registration.md (left unstaged; CLAUDE.md says not to use memory): `git checkout -- .claude/agent-memory/` to discard
- [x] (user) Fix the QA plan 3. frontend_qa.md: 1.1 step 4 searches a Courses list that has no search box, its URLs omit the organisations/ segment, and 2.2 names a 'Course registrations' panel that is the learner Overview's 'Registrations' panel
- [ ] (user) Look at freedom_ls/referral_tracking/tests/test_models.py::test_the_touch_code_lookup_uses_the_upper_index (from main, not this branch): it failed once in the full parallel run after the rebase (the planner picked another index) and passed 3 of 3 when re-run alone

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add "owning organisation" and "course share" and qualify the `peer` row's "a course is not owned by one" (spec: Documentation and downstream, glossary bullet)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
