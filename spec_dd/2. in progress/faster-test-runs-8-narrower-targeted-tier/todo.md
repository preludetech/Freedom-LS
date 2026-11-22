# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [x] (cmd) Run `/sdd:document` In `claude_plugins/django-stack/resources/test_tiers.md`, targeted bullet only: describe the `narrow` key, the `mode: narrow` line and `--wide` by shape, with no project names (spec "Documentation and downstream"; the checkpoint `--wide` instruction is already there)
- [x] (cmd) Run `/sdd:document` In `claude_plugins/django-stack/README.md`: add `narrow` to the `[tool.test_tiers]` keys `scripts/select_tests.py` reads, and `--wide` to its flags (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:document` In `claude_plugins/fls-dev/resources/testing.md`: say FLS sets `narrow = true`, what it narrows, what it leaves to the full run (the spec's Decisions list), and the `demo_content/**` tooling rule (spec "Documentation and downstream")
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether the selector's run time with `narrow` on (median 6.0s, max 8.2s against the 10s target; one loaded run took 9.5s, see `replay.md`) needs a cache for the module graph; if so, a follow-up spec adds one — decided: no cache. About 3s on a quiet machine against about 40 min saved per batch; a stale cache would silently drop tests. Revisit if it regularly passes 10s, trying parallel parsing first.

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
