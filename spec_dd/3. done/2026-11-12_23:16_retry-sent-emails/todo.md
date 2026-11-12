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
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: mobile outbound email changelist clips multi-line values, including Last error, because Unfold's card cells are fixed-height with overflow hidden (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: fls_run_housekeeping always exits with a CommandError in dev because prune_db_task_results rejects the ImmediateBackend task backend (TDD: failing test first, then fix)
- [x] (user) Decide whether outbound email row retention measures from created_at (spec field table) or from last_attempt_at (spec section 8 and the code), then make the spec agree with itself and give the QA plan's row G a matching last_attempt_at

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `spec_dd/1. next/user-communication-2-notification-email/idea.md`, change the reference `spec_dd/1. next/retry-sent-emails/1. spec.md` to this spec's final location under `spec_dd/3. done/` (spec section "Documentation and downstream", last bullet)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
