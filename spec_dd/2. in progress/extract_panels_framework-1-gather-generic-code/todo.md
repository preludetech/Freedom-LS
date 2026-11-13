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
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: component reference page has no panel-notice examples (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: learners table mixes '—' (Cohorts) and '-' (Courses, learner_courses.html) for empty cells (TDD: failing test first, then fix)
- [x] (user) Decide what a disabled bulk confirm's reason says when no selected row qualifies (e.g. Resend setup email with only set-up learners), then show it beside the button and name it with aria-describedby
- [x] (user) Decide what a bulk dialog's disabled confirm says beside it before a picker choice is made (e.g. Add to cohort with no cohort chosen), then show it and name it with aria-describedby
- [x] (user) Decide whether to keep `freedom_ls/qa_helpers/management/commands/qa_create_dev_org_baseline.py` (written by the QA data helper to seed the dev organisation; uncommitted), then commit or delete it
- [x] (user) Decide whether the learner import error section is an error notice (as the QA plan says) or stays a warning notice so its role=alert does not announce the whole error table, then align the template or the QA plan

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`: the `sidePanel` and `refreshTimer` rows name `shell-components.js`, `listRefresh` and `headerRefresh` become `eventRefresh`, and the menu item's count-events mechanism is added (spec "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: "What it is" lists the reason dialog, `ConfirmAction` and `refusal_response`, lazy panels, `PermittedBulkAction` and the registry, `ToggleFilter`, `PeriodFilter`, the sweeps, the new components and cells, `row_param` and the `__all__` rule; "Dialogs, sheets and the quick view" states the three dialog shapes and the footer's own Cancel; the Cancel rule and the tone rule from the spec's Decisions are added; "What enforces it" lists the new invariants (spec "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` line 30: `AuditPeriodFilter` becomes `PeriodFilter` (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
