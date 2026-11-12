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

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`: the `sidePanel` and `refreshTimer` rows name `shell-components.js`, `listRefresh` and `headerRefresh` become `eventRefresh`, and the menu item's count-events mechanism is added (spec "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: "What it is" lists the reason dialog, `ConfirmAction` and `refusal_response`, lazy panels, `PermittedBulkAction` and the registry, `ToggleFilter`, `PeriodFilter`, the sweeps, the new components and cells, `row_param` and the `__all__` rule; "Dialogs, sheets and the quick view" states the three dialog shapes and the footer's own Cancel; the Cancel rule and the tone rule from the spec's Decisions are added; "What enforces it" lists the new invariants (spec "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` line 30: `AuditPeriodFilter` becomes `PeriodFilter` (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
