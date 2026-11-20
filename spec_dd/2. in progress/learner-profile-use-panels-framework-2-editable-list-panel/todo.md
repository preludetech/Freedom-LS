# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Fix test_wrapped_dialog_footer_keeps_its_actions_at_the_right_edge in freedom_ls/educator_interface/tests/playwright/test_create_cohort_add_and_add_another.py (main's test looks for a Save button; this branch renamed the create dialog's primary button to Add), then re-run `/sdd:finish_worktree`
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Review the departures from the plan and keep or revert each: `modal-trigger.html` forwards extra attributes with `:attrs` because cotton does not expand `{{ attrs }}`; the editable-list browser flow uses a separate parent per capped, add-another and table tab because all four stub panels share one entry model; `StubEntry` gained `verbose_name_plural`; the component-reference browser test's section count went from 19 to 20. No action is needed if all four stand.
- [x] (user) Decide whether to look into a 404 on `/test-panel/framework/stubs/1/__tabs/entries/__actions/edit_entry` that showed up once in a heavily loaded full run of `test_editable_list_flow.py`. It has not shown up since the focus-race fix (`97b5aeeb4`); if it comes back, open a bug for it.
- [x] (cmd) Editable list: Edit and Remove sit in an item footer under each list row and card (a `footer` slot on `<c-panel-list-row>` and `<c-panel-table-card>`), and the desktop table's actions column keeps the pair on one line; QA plan Test 1 checks it
- [x] (cmd) Re-checked the editable list item footer at 375/768/1920 (Edit and Remove on one row, label width, in `[data-item-footer]`); screenshots in `screenshots/fixed/`; QA plan Test 1 step 6 makes it a blocking measured check
- [x] (user) Decide whether to move `learner_registrations.html`'s Deactivate/Reactivate button from the list row's trailing slot into the row's item footer, as the new panel-framework rule says
- [x] (user) Decide whether to fix `test_saving_one_entry_twice_announces_both_saves`: under `-n 4` load it fails about one run in three (announcer reads `['Saved Alpha.', '']`), on the committed code before the item-footer change too
- [x] (user) Decide whether to keep or delete the untracked QA data command `freedom_ls/qa_helpers/management/commands/qa_create_learner_registrations_panel.py` (builds a learner with active, inactive and cohort registrations for the Registrations panel; re-runnable as a reset; no test)
- [x] (user) Decide whether to fix the learner Overview tab's Cohorts table at 768px: its columns don't fit, so it scrolls sideways and hides Joined and the Remove/Move buttons, where the panel-framework rule says a table that doesn't fit shows as cards (`cards_when_narrow`). It predates this branch, which does not touch that panel

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: add `EditableListPanel`, `EditableListSummary`, `get_form_class()`, `derive_capability` and the three editable-list actions to "What it is"; narrow the rule "An ordered list with an action on each entry is a data table" (Tables, and the visual checklist line) to numbered lists such as the course outline, and name `EditableListPanel` as the shape for a short editable list; add the focus targets and the announcements ("Added <title>.", "Saved <title>.", "Removed <title>.") after add, edit and remove; add the new `aria_label` invariant to "What enforces it" (spec: Documentation and downstream, first bullet)
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, Adding and editing records: name `ADD_ANOTHER_BUTTON`, `wants_add_another` and `add_another_response` as the one way to build "Add and add another", with the "Added <name>." status message, in place of "`CreateInstanceAction.submit_buttons` is the shape" (spec: Documentation and downstream, first bullet)
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: say that `get_hidden_fields` now lives on `PanelAction` and that `modal/form.html` renders it, and that `<c-panel-table>` takes `cards_when_narrow` (spec: Requirements, Actions and Templates)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [x] (cmd) Code review PR 262: read the entry's title and focus target from the entry itself, so add and edit announce and focus correctly when there is no Edit trigger
- [x] (cmd) Code review PR 262: a slow refresh from an earlier "Add and add another" must not be taken for the answer to a later Add
- [x] (cmd) Code review PR 262: announce an identical change again (clear the live region before setting it)
- [x] (cmd) Code review PR 262: E009 requires `refresh_events` on every `EditableListPanel` subclass
- [x] (cmd) Code review PR 262: Remove and Delete refuse a row a RESTRICT foreign key still points at, in place of a 500
- [x] (cmd) Code review PR 262: `reference.py` builds its entries with the panel's own helpers in place of repeating them
- [x] (cmd) Code review PR 262: the reference example's table header reads the singular noun ("Contact")
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
