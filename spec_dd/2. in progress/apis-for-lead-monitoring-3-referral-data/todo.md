# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items and the two PR commands. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Update `docs/api.md` from the spec's "Documentation and downstream" section: the intro and scopes table (four referral endpoints, `FirstTouchCount` in the `referral_data` row, drop "Only `users` has an API endpoint so far"), Pages ordering by the endpoint's ordering field then `id`, the Incremental syncs table with the full-pull, checkpoint and lookback recipes, Deletions (pruned hits, erased users), one section per referral resource in the Users layout with the "Not returned" line on signup attributions, the "Known data caveats" subsection, and a first-touch-count lookback Python example that reuses `get_page` (no documentation hook covers `docs/api.md`)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
