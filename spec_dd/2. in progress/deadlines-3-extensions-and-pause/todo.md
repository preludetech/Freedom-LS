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
- [ ] (cmd) Add the three audit codes (course.paused, course.resumed, deadline.extended) and the "Course progress" group to freedom_ls/audit_log/README.md, from the spec's Documentation and downstream section
- [ ] (cmd) Add the Terminology terms, the CoursePause and DeadlineExtension models, and the new noun (deadline), verbs (paused, resumed, extended) and group (Course progress) to the Changes section of claude_plugins/fls-dev/skills/domain-glossary/SKILL.md, from the spec's Terminology and Documentation and downstream sections
- [ ] (cmd) Update the Deadlines section of spec_dd/1. next/roadmap.md (record shapes and shift rule resolved) and name pause_course, resume_course, announce_planned_resume, extend_deadline, CourseDeadlines.pause and the limit fields in the ideas of deadlines specs 4 to 7, from the spec's Documentation and downstream section
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
