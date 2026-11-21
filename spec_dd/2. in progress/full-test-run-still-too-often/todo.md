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

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/sdd/commands/README.md`, section "When the full suite runs" and the diagram paragraph near the top: "Two steps" and "the two full test runs" become one (`implement_plan` Step 3); the fix-sub-agent sentence says the checkpoint in `finish_worktree` covers the fixes; the checkpoint's third rule says upstream escalation globs are scoped to the related apps and dependency files still force `full`; "Step 1's full run wrote the record" names the last passing full run (spec section "Documentation and downstream", first bullet)
- [x] (cmd) Add `--upstream-range` and `dependency_files` wherever the selector's flags or `[tool.test_tiers]` keys are listed: `claude_plugins/django-stack/README.md` (it lists neither today) and `claude_plugins/django-stack/resources/testing.md` (the paragraph on `select_tests.py`, which also says `pyproject.toml`/`uv.lock` behaviour lives in the escalation list) (spec section "Documentation and downstream", second bullet)
- [x] (cmd) Update the diagrams under `claude_plugins/sdd/docs/diagrams/`: `finish_worktree.drawio.svg` (Step 1 takes the checkpoint fill, no longer red; its note "Step 1's full run wrote the record it reads" is reworded), `overview.drawio.svg` (one red full-run box), `rebase.drawio.svg` (Step 9.2 wording); `tests/test_check_diagrams.py` must pass (spec section "Documentation and downstream", third bullet)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
