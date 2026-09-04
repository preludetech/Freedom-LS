# SDD Todo

This branch was worked interactively rather than through the SDD workflow, so it has no spec, no
plan and no security or structure reviews. The checklist below carries only the steps that still
apply, keeping the standard section numbering so the SDD commands find their headings.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (user) Implement the items in the idea file directly

## 9. QA

- [x] (cmd) Write the QA plan for the changes on this branch
- [ ] (cmd) Run `/fls-dev:do_qa` to execute `3. frontend_qa.md` (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) Decide what to do about the deleted `visual_polish` spec folder — two of its three sub-ideas are unimplemented and four research documents were removed rather than archived (see `3. frontend_qa.md` §13.1)
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)

## 13. Pull request

- [ ] (user) Open a pull request
- [ ] (user) Merge the PR once approved

## 14. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
