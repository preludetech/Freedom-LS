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
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: add `EditableListPanel`, `EditableListSummary`, `get_form_class()`, `derive_capability` and the three editable-list actions to "What it is"; narrow the rule "An ordered list with an action on each entry is a data table" (Tables, and the visual checklist line) to numbered lists such as the course outline, and name `EditableListPanel` as the shape for a short editable list; add the focus targets and the announcements ("Added <title>.", "Saved <title>.", "Removed <title>.") after add, edit and remove; add the new `aria_label` invariant to "What enforces it" (spec: Documentation and downstream, first bullet)
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, Adding and editing records: name `ADD_ANOTHER_BUTTON`, `wants_add_another` and `add_another_response` as the one way to build "Add and add another", with the "Added <name>." status message, in place of "`CreateInstanceAction.submit_buttons` is the shape" (spec: Documentation and downstream, first bullet)
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: say that `get_hidden_fields` now lives on `PanelAction` and that `modal/form.html` renders it, and that `<c-panel-table>` takes `cards_when_narrow` (spec: Requirements, Actions and Templates)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
