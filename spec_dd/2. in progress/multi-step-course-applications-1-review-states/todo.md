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
- [ ] (cmd) Run `/sdd:document`: in `freedom_ls/audit_log/README.md`, add `application.approved` and `application.rejected` (group Applications, audit-only, no webhook) to the audit actions table and note that the applicant's own submit and withdraw write no entry (spec "Audit and glossary")
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add the noun `application`, add it to the "Changes" noun list, add verb rows `approved` (not `accepted`, `admitted`) and `rejected` (not `declined`, `denied`), and add the **withdraw** row to "Words that are already taken" (spec "Audit and glossary")
- [ ] (cmd) Run `/sdd:document`: in `docs/api.md`, add `state`, `organisation_id`, `decided_at` and `withdrawn_at` to the course-applications field table and example payload (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
