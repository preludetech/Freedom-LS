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
- [ ] (user) Force-push the rebased branch: `git push origin multi-step-course-applications-1-review-states --force-with-lease --force-if-includes` (the branch was rebased onto main and the automated force-push was refused by the permission check)
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether a withdrawn draft's check-your-answers page should hide its Edit links: today it still shows them, though every write redirects to the status page (`application_check_answers` keeps `submitted = app.is_submitted`); if yes, gate the links on `can_submit` too
- [x] (user) Decide whether the dashboard panel's rejected-row "Apply again" button should show below the `sm` breakpoint: it is `hidden sm:inline-flex` like "View my application", so on phones the applicant taps the row, reaches the status page and applies again from there (`course_applications/partials/dashboard_applications.html:66`)
- [x] (user) Keep or delete `/tmp/claude-1000/-home-sheena-workspace-lms-freedom-ls-worktrees-multi-step-course-applications-1-review-states/74fc48a3-b38e-43d7-92a9-c45b9d3ada94/scratchpad/stray_0008_learnerimport.py`: a `learner_management` migration an old `git stash pop` (stash "educator-interface-8-bulk-operations") dropped into this worktree; it was moved out because it broke the migration graph, and the stash entry itself is unchanged

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
