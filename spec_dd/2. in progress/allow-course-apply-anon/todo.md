# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `claude_plugins/sdd/commands/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/sdd:improve_idea` to research and refine the idea
- [ ] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to generate the spec
- [ ] (user) Review the spec carefully and edit where needed
- [x] (cmd) Run `/sdd:spec_review` to sanity-check the spec
- [ ] (user) Address any issues raised by the review
- [ ] (user) Decide how to handle the defaults the review added to spec §8: the upload cap answering 422 in the widget, the start cap reusing `429.html`, a page-less form giving anonymous apply a 404, and a signed-in user reading a session-held unclaimed application

## 3. Threat model

- [ ] (cmd) Run `/ds:threat-model` against the spec
- [ ] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 5. Plan security review

- [ ] (cmd) Run `/fls-dev:plan_security_review` to check the plan for insecure design choices before implementation
- [ ] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [ ] (cmd) Run `/fls-dev:plan_structure_review` to check for new cross-app dependencies
- [ ] (user) Address any structure concerns raised in the plan

## 7. Implementation

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues
- [ ] (user + cmd) Fix QA bug: submitted anonymous application's read-only check-your-answers still shows 'Submit it to keep it' notice (TDD — failing test first, then fix)
- [ ] (user) Decide what a submitted but unclaimed application's check-your-answers page should say instead of the browser-only 'Submit it to keep it' notice (hide it, or new wording), then update spec 5.9 and the template
- [ ] (user + cmd) Fix QA bug: handoff toast says 'Create an account or log in' when signups are closed (TDD — failing test first, then fix)
- [ ] (user) Decide the handoff toast wording when signups are closed and the visitor is sent to login, then update spec and the handoff message

## 10. Product documentation

- [ ] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Upgrade notes

- [ ] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes

## 12. Author plugin sync

- [ ] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 13. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (cmd) Once review feedback is addressed, re-run `/fls-dev:update_upgrade_notes` to re-verify the notes against the final code
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward (merging it on GitHub first is also fine)

## 14. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it

## Part 2: the About you page

Spec `1b. spec.md`. Plan and QA files take the `2b` suffix: `2b. plan.md`, `3b. frontend_qa.md`.
Sections 10 to 14 above run once, after part 2 is implemented.

- [x] (user) Write the part 2 spec (`1b. spec.md`)
- [ ] (user) Review the part 2 spec and edit where needed
- [ ] (cmd) Run `/sdd:spec_review` on `1b. spec.md`
- [ ] (user) Address any issues raised by the review
- [x] (cmd) Run `/sdd:plan_from_spec` on `1b. spec.md` with suffix `2b`
- [ ] (user) Review both plans and edit where needed
- [ ] (cmd) Run `/fls-dev:plan_security_review` on `2b. plan.md`
- [ ] (cmd) Run `/fls-dev:plan_structure_review` on `2b. plan.md`
- [ ] (cmd) Run `/sdd:implement_plan` on `2b. plan.md`
- [ ] (user) Spot-check the changes
- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (cmd) Run `/fls-dev:do_qa` with `3b. frontend_qa.md`
- [ ] (user) Review the QA report and fix any bugs with TDD
