# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [x] (user) Decide keep-or-remove for each line of unused_step_candidates.md
- [ ] (user) Choose where `/sdd:commit_quickly` moves to out of sdd (e.g. the productivity plugin), and whether that is this spec or its own

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Manual run in a sandbox clone with a local bare origin: `/sdd:finish_worktree` with main moved twice during the run; it lands without stopping and reports both passes
- [x] (user) Manual run: `/sdd:finish_worktree` with a dirty spec file in the main worktree, once per answer ("Commit and push them to main for me", "I'll commit main, then continue")
- [x] (user) Manual run: `/sdd:finish_worktree` with a spec-only rebase conflict; it resolves without asking and reports the paths
- [x] (user) Manual run: `/sdd:finish_worktree` with a denied force-push; it returns `paused` with the exact command and continues after you run it
- [x] (user) Manual run: `/sdd:finish_worktree` with a deliberately order-dependent test; a sub-agent fixes it and the report lists the commit
- [x] (user) Manual run: one pre-step rebase of a spec-only branch; no pytest runs and pre-commit checks only the branch's files
- [x] (user) Check every `claude_plugins/sdd/docs/diagrams/*.drawio.svg` opens in draw.io and renders in GitHub's preview of `claude_plugins/sdd/commands/README.md`
- [ ] (user) Run the full test tier: the run at the end of `/sdd:implement_plan` was killed under low system memory and then cancelled at your request, so no full run has passed on the finished branch and no full-run record exists; `/sdd:finish_worktree` Step 1 runs the full tier before it lands
- [x] (user) Decide what the second full-run point is: the spec says there are two and names only `implement_plan` Step 3; the overview diagram and `claude_plugins/sdd/commands/README.md` (section "When the full suite runs") label it as a checkpoint that resolves to full, where CI on the pull request is the other reading. Then have the overview label and that section adjusted if needed
- [x] (user) Decide whether the diagrams should share one layout: `document`, `rebase`, `start`, `spec_from_idea` and `plan_from_spec` are single horizontal strips of five lanes (`rebase` is about 8,300 px wide); `implement_plan`, `do_qa`, `qa_fix` and `finish_worktree` are stacked bands about 2,500 px wide that repeat their lanes. Redrawing either set follows
- [x] (user) Confirm the stale-lease change in `finish_worktree.md`: a main-moved loop pass entered before Step 7 (from Step 0 or Step 0.5) stops after its rebase and continues at Step 0.5, so nothing lands before the PR check and close-out; the plan's wording ran the whole pass, which ends in `land`
- [x] (user) Decide what to do about `tests/test_run_tests.py::test_memory_that_becomes_sufficient_ends_the_wait_with_the_sized_count`: it failed once in a full run while the machine was under load and passes alone; fix its timing sensitivity or leave it
- [x] (user) Decide what to do about `plan_from_spec.md` Step 5, which tells the plan to reference the QA file as a final step while the same command says a plan never mentions QA; the trim left it because removing it changes behaviour
- [x] (user) This spec has no `3. frontend_qa.md`, so `/sdd:do_qa` has no plan to run: decide whether to write one or tick the `/sdd:do_qa` and `/sdd:qa_fix` items as not applicable

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Document the rebase's `<auto-resolve>` argument, its `none` tier and the pre-commit run scoped to the branch's changes in `claude_plugins/django-stack/README.md` and `claude_plugins/django-stack/resources/test_tiers.md` (spec section "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
