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

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Update `docs/api.md` for the `attribution-touches` and `conversions` endpoints: intro, scope table, Referral data intro, Incremental syncs checkpoint rows, Deletions, one section per resource, the example's `PATHS`, and the No conversion uploads caveat (spec section "Documentation and downstream", `docs/api.md` bullets)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
