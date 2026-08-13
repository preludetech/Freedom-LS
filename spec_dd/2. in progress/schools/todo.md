# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `claude_plugins/sdd/commands/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/sdd:improve_idea` to research and refine the idea
- [x] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to generate the spec
- [x] (user) Review the spec carefully and edit where needed
- [x] (cmd) Run `/sdd:spec_review` to sanity-check the spec
- [x] (user) Address any issues raised by the review


## 4. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 6. Plan structure review

- [x] (cmd) Run `/fls-dev:plan_structure_review` to check for new cross-app dependencies
- [x] (user) Address any structure concerns raised in the plan
- [x] (user) Resolve structure concern: student_interface --> organisations edge for get_default_organisation (plan §0.1)

## 7. Implementation

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [x] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues
- [x] (user + cmd) Fix QA bug: Duplicate Organisation name returns a 500 IntegrityError instead of a validation error (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Duplicate cohort name in an organisation returns a 500 with no user feedback (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Non-UUID cohort id segment returns a 500 ValidationError instead of a 404 (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: `#scope-announcer` live region is destroyed and recreated on every switch (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Educator Interface header link gated on `is_staff`, hidden from organisation educators (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Switcher trigger is last in the tab order and arrow keys do not move between options (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: `organisation_staff` cannot create or delete cohorts, so QA §6 is not performable by its named persona (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Mobile/tablet nav drawer stays open after switching organisation (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Educator interface pages render an empty `<title>` (TDD — failing test first, then fix)
- [x] (cmd) Use the `fls-dev:qa-data-helper` agent to create missing data for QA §7.6 (learner in the player with no registration), then re-run `/fls-dev:do_qa`
- [ ] (user) Decide on QA §7.6: the player's "no organisation" branch is unreachable in the browser (the player redirects away without a registration, and every registration carries a non-nullable Organisation FK) — either drop the test from the plan, or suppress the Site's own default organisation in the co-branding chip
- [ ] (user) Correct QA plan §6: Northside already has a seeded "Year 9 Maths", so step 3 as written must fail — use a fresh cohort name created in both organisations to prove the narrowed constraint
- [ ] (user) Correct QA plan §7.3: switching `FLS_THEME` also requires `npm run tailwind_build`, or both themes render identically

## 10. Product documentation

- [x] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Upgrade notes

- [x] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes

## 12. Template repo

- [ ] (cmd) Run `/fls-dev:update_template_repo` to update the template repo for new projects
- [ ] (user) Review and commit the template repo changes (if any)

## 13. Author plugin sync

- [ ] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 14. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 15. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
