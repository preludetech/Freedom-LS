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
- [ ] (user) Decide whether the CPU target is met, from "Result after the second pass" in `timings.md`: after a second pruning pass the ranking run measured 1081.9 CPU s against the 1185.3 target, on a quieter machine than the first run and with 296 more tests from a rebase onto main. Brought to the first run's load, it is about 1268 CPU s against an adjusted target of at most 1291.7, and the pruned tests alone save about 185 CPU s of the 192.9 needed. Accept it, or ask for more pruning: what is left above the 7.28 s threshold is listed under "Candidates left unchanged" in `pruned_tests.md`
- [ ] (user) Run the full tier before the pull request: the branch was rebased onto main (125 commits) after the last full run, and since then only the targeted tier and the ranking run (whole suite, no Playwright tests) have run. the command is the full tier in `claude_plugins/django-stack/resources/test_tiers.md`
- [ ] (user) Push the rebased branch: the force-push after the rebase onto main was blocked by the permission check, so run `! git push origin HEAD --force-with-lease --force-if-includes`

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/testing/SKILL.md`, add a section "The test-cost ranking" with the command (`uv run python scripts/rank_test_costs.py`), when to run it (after pruning, or when the suite feels slower), its run time from the last ranking run in `timings.md`, what `test_organisation/test_cost_ranking.md` holds, and that nothing fails on slowness (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
