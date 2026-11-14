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
- [x] (user) Decide whether main's course outline table (`educator_interface/templates/educator_interface/panels/course_content.html`) stays exempt from the hand-written-table invariant (`HAND_WRITTEN_TABLE_EXEMPTIONS` in `panel_framework/tests/invariants/test_templates.py`, added during the rebase), or moves onto `<c-panel-table>`/`<c-data-table>`
- [x] (user) Delete the local backup branch `extract_panels_framework-1-rebase-wip` (partial rebase progress) once you are happy with the rebase onto main
- [ ] (user) Decide whether a dialog always reserves its scrollbar track (the rule in the panel-framework skill) or its header and footer rules run the full width, then fix QA bug B3: dialog header and footer rules stop 16px short of the right edge (TDD: failing test first, then fix)
- [ ] (user) Decide where a disabled confirm's reason sits when it does not fit beside the button, and at what text size, then fix QA bug B4 (Move and bulk dialogs) (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug B5: secondary buttons are 2px taller than primary ones, on styles shared with learner pages (TDD: failing test first, then fix)
- [ ] (user) Decide what the refusal says when someone deactivates a cohort that is already inactive (QA bug B6: it now says to reactivate the cohort in order to deactivate it), then change the copy
- [ ] (user) Decide whether panel lists keep a rule between rows and course cards stay boxes inside a panel, or the brand checklist's 'no rule between list items, no box inside a box' wins (QA bug B8), then align the component or the checklist
- [ ] (user) Decide what to do about QA bug B9: the embedded conversation thread and composer do not line up with their panel or dialog and repeat a header; the partial is shared with learner message pages (TDD: failing test first, then fix)
- [ ] (user) Decide how educator navigation renders with JavaScript off (QA bug B11: there is none, same on main), then build it or record it as accepted
- [ ] (user) Decide whether static panel tables carry the data table's entry count, pager and height cap (QA bug B12: import preview Rows table has no entry count), then fix or record it as accepted
- [ ] (user) Decide which clock educator pages show, browser-local or server time (QA bug B13: the import result shows local time, the tables server time), then make them agree
- [ ] (user) Decide the focus style for a heading or notice that takes focus for screen readers (QA bug B14: a heavy black box on the import result heading and the upload error), then apply it
- [ ] (user) Decide whether an empty cohort name shows an error notice (as `3. frontend_qa.md` Test 11.3 says) or the inline field error other forms use (QA bug B15), then align the page or the QA plan
- [ ] (user) Decide between cards and a minimum name width for the cohort report tables at 375 and the learner tables at 768 (QA bug B16: names are clipped to one or three letters), then fix (TDD: failing test first, then fix)
- [ ] (user) Decide whether to keep `freedom_ls/qa_helpers/management/commands/qa_create_bulk_learners.py` and the changed notes under `.claude/agent-memory/sdd-qa-data-helper/` (written by the QA data helper during this run; uncommitted), then commit or delete them
- [ ] (user) Correct `3. frontend_qa.md` where this run found it out of date: Test 7.7 bulk action order, Test 7.6 notification threshold (250 rows, not 25), Tests 8.1 and 8.2 URL parameter names (`cohorts-inactive`, `audit_log-when`), Test 11.4 last-active column

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
