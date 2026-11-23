# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [x] (user) Decide what to change after reading upstream_change_review.md, then edit the idea, spec or plan it names
- [ ] (user) Write the follow-up idea for an educator-interface screen that edits learner HR attributes (they lose their only edit screen with Learner admin)
- [ ] (user) Update `spec_dd/1. next/sacaa-complianc-deletion-and-declaration-1-force-delete/idea.md`: its `LearnerAdmin` target no longer exists
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
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/resources/admin_interface.md`, replace the `TopicAdmin` and `CohortAdmin` examples with surviving admins and name `ReadOnlyAdminMixin` (`freedom_ls/site_aware_models/admin.py`) as the view-only pattern (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/admin-interface/SKILL.md`, replace the `CourseReferencePartInline` (`content_engine/admin.py`) inline example with `CoursePauseInline` in `freedom_ls/deadlines/admin.py` (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:document`: in `docs/app_conventions.md`, drop `freedom_ls/learner_management/forms.py` from the `ConstraintValidationFormMixin` worked examples, leaving `freedom_ls/organisations/forms.py` (the file is deleted with the learner_management admin)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
