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

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [x] (user) Update `spec_dd/1. next/admin-dashboard-signal-cards/idea.md`: its course registrations card links to the `LearnerCourseRegistration` admin changelist, which this branch removes; point it at the educator interface instead
- [x] (user) Update `spec_dd/2. in progress/sacaa-compliance-content-versions-and-access-2-retire-removed-content/idea.md`: its "Open until the spec" section recommends a retired filter and column on the content admin changelists and lists the Django admin changelists as a surface for the retired mark; those admins no longer exist
- [x] (user) In the `sacaa-compliance-content-versions-and-access-2-retire-removed-content` worktree, before Slice 13 is built: cut `RetiredListFilter` and the `retired_at` column from its spec's "Django admin" section and from plan Slice 13 steps 1-2 (the content and form admins they target are deleted by this branch); keep step 3, the Retired marker on the admin answers page
- [ ] (user) Review the code and the QA report
- [x] (user) Decide what to do about QA bug: admin changelist cards at 375px break field labels mid-word ('Learn er', 'Cours e'); unfold's mobile card layout, shared by every admin changelist, predates this branch (TDD: failing test first, then fix)
- [x] (user) Look at the guardian object-permissions page screenshot in qa_report.md (it rendered correctly under unfold) and, if satisfied, resolve the @claude comment on OrganisationAdmin in freedom_ls/organisations/admin.py
- [ ] (user) Update claude_plugins/fls-content/skills/content-types/resources/form-files.md line 468: "the admin shows it on the question" is stale now that the FormQuestion admin is gone; say where the value is visible instead, or drop the clause

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/resources/admin_interface.md`, replace the `TopicAdmin` and `CohortAdmin` examples with surviving admins and name `ReadOnlyAdminMixin` (`freedom_ls/site_aware_models/admin.py`) as the view-only pattern (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/admin-interface/SKILL.md`, replace the `CourseReferencePartInline` (`content_engine/admin.py`) inline example with `CoursePauseInline` in `freedom_ls/deadlines/admin.py` (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: in `docs/app_conventions.md`, drop `freedom_ls/learner_management/forms.py` from the `ConstraintValidationFormMixin` worked examples, leaving `freedom_ls/organisations/forms.py` (the file is deleted with the learner_management admin)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [x] (cmd) Fix the /code-review 288 findings: resume action on the pause admin, learner pickers by email, shared cohort-registration picker, ReadOnlyAdminMixin on the pause and extension admins
- [ ] (user) Try the new admin flows: resume an open pause from its CoursePause page, and add a learner deadline config and learner messaging config by typing the learner's email

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
