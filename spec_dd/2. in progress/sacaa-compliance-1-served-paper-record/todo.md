# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [ ] (user) Confirm the source and status of the SACAA 141.07.1 "E-Learning system" text quoted in `research_prior_art.md` section 2 before the effort relies on it
- [ ] (user) Confirm or overrule the four assumed defaults under `## Open questions` in `1. spec.md`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide what to do about QA bug: two concurrent quiz starts create two sittings and score one as abandoned. Decide whether a second concurrent start reuses the open sitting or is rejected, and whether one open sitting per learner and item is enforced by a partial unique constraint (needs a migration) or by row locking; then fix it TDD: failing test first, then fix (see qa_report.md, B3)
- [ ] (user) Check the downloadable cohort report PDF for the QA Served Paper Cohort with the background task worker running: learner A's quiz section shows 3 of 4 with Q3 listed as wrong, and learner B's section lists no removed or moved question (QA checked only the on-screen report; see qa_report.md test 11.1)

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
