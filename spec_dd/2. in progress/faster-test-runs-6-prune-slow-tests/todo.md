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
- [ ] (user) Decide on the CPU target miss recorded in `timings.md`: the last ranking run measured 1680.1 CPU s against the 1185.3 target, under much higher load (load 15.9→32.6, CPU pressure 12.2→49.8, against 10.3→7.3 and 4.8→1.6 in the first run). Choose one: accept the pruning estimate (229.4 CPU s saved, 192.9 needed); rerun `uv run python scripts/rank_test_costs.py` on a quieter machine and update `timings.md`; or prune more, starting from `content_engine/tests/test_images.py::test_comparison_winner_on_each_side_of_the_lossy_wins_divisor` (14.8 s)
- [ ] (user) Push the rebased branch: the force-push after the rebase onto main was blocked by the permission check, so run `! git push origin HEAD --force-with-lease --force-if-includes`

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/testing/SKILL.md`, add a section "The test-cost ranking" with the command (`uv run python scripts/rank_test_costs.py`), when to run it (after pruning, or when the suite feels slower), its run time from the last ranking run in `timings.md`, what `test_organisation/test_cost_ranking.md` holds, and that nothing fails on slowness (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
