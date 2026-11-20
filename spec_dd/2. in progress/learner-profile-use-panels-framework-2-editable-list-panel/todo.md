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
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Review the departures from the plan and keep or revert each: `modal-trigger.html` forwards extra attributes with `:attrs` because cotton does not expand `{{ attrs }}`; the editable-list browser flow uses a separate parent per capped, add-another and table tab because all four stub panels share one entry model; `StubEntry` gained `verbose_name_plural`; the component-reference browser test's section count went from 19 to 20. No action is needed if all four stand.
- [x] (user) Decide whether to look into a 404 on `/test-panel/framework/stubs/1/__tabs/entries/__actions/edit_entry` that showed up once in a heavily loaded full run of `test_editable_list_flow.py`. It has not shown up since the focus-race fix (`97b5aeeb4`); if it comes back, open a bug for it.

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
