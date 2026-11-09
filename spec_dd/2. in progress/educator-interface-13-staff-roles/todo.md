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
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: add glossary rows to `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` for `StaffMember`, `organisation_staff_viewer`, `organisation_staff_roles_viewer`, `staff_member.added`, visible staff, pickable staff, `target` of a role and may edit own roles, and the "Remove from cohort" exception in the "removed" row (spec: Documentation and downstream, Terminology)
- [ ] (cmd) Run `/sdd:document`: in `.claude/skills/brand-guidelines/visual.md` "Placement", note that the cohort Settings row names Change role and Remove from cohort per person, and the Staff row names Add role (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: add `staff_member.added` to the action table in `freedom_ls/audit_log/README.md` (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
