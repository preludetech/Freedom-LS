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

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Manual run in a sandbox clone with a local bare origin: `/sdd:finish_worktree` with main moved twice during the run; it lands without stopping and reports both passes
- [ ] (user) Manual run: `/sdd:finish_worktree` with a dirty spec file in the main worktree, once per answer ("Commit and push them to main for me", "I'll commit main, then continue")
- [ ] (user) Manual run: `/sdd:finish_worktree` with a spec-only rebase conflict; it resolves without asking and reports the paths
- [ ] (user) Manual run: `/sdd:finish_worktree` with a denied force-push; it returns `paused` with the exact command and continues after you run it
- [ ] (user) Manual run: `/sdd:finish_worktree` with a deliberately order-dependent test; a sub-agent fixes it and the report lists the commit
- [ ] (user) Manual run: one pre-step rebase of a spec-only branch; no pytest runs and pre-commit checks only the branch's files
- [ ] (user) Check every `claude_plugins/sdd/docs/diagrams/*.drawio.svg` opens in draw.io and renders in GitHub's preview of `claude_plugins/sdd/commands/README.md`

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Document the rebase's `<auto-resolve>` argument, its `none` tier and the pre-commit run scoped to the branch's changes in `claude_plugins/django-stack/README.md` and `claude_plugins/django-stack/resources/test_tiers.md` (spec section "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [x] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
