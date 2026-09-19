# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `claude_plugins/sdd/commands/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/sdd:improve_idea` to research and refine the idea
- [ ] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to generate the spec
- [ ] (user) Review the spec carefully and edit where needed
- [ ] (cmd) Run `/sdd:spec_review` to sanity-check the spec
- [ ] (user) Address any issues raised by the review

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

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues
- [x] (user + cmd) Fix QA bug: course page stats-strip Price value overflows its fixed-width cell into the Enrolment cell (TDD — failing test first, then fix)
- [x] (user) Decide how the course page's Price stat cell should hold long prices (let the cell grow past w-48, or let the price wrap), then fix the overflow
- [x] (cmd) Re-run `/fls-dev:do_qa` to cover the open-ended range price ("From X"), the new pricing demo courses, and the widened stats strip
- [x] (user) Decide what a registered learner should see on a priced application-gated course page: the Price cell now sits beside the inherited 'Free · open' / 'One click. No credit card.' copy. Then hide the Price cell for registered learners or change that copy
- [x] (user + cmd) Fix QA bug: admin price validation messages use internal field names and raw kind values (e.g. 'currency is not used by a on_request price') (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: ragged divider lines in the stacked course-page stats strip on mobile when the Price cell is wider than the others (TDD — failing test first, then fix)

## 10. Product documentation

- [x] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Upgrade notes

- [x] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes

## 12. Author plugin sync

- [x] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 13. Pull request

- [x] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (cmd) Once review feedback is addressed, re-run `/fls-dev:update_upgrade_notes` to re-verify the notes against the final code
- [ ] (user) Merge the PR once approved

## 14. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
