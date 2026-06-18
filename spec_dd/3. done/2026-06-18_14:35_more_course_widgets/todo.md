# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `fls-claude-plugin/commands/sdd/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/improve_idea` to research and refine the idea
- [x] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/spec_from_idea` to generate the spec
- [x] (user) Review the spec carefully and edit where needed
- [x] (cmd) Run `/spec_review` to sanity-check the spec
- [x] (user) Address any issues raised by the review

## 3. Threat model

- [x] (cmd) Run `/threat-model` against the spec
- [x] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [x] (cmd) Run `/plan_from_spec` to generate the implementation plan and QA plan
- [x] (user) Review both plans and edit where needed

## 5. Plan security review

- [x] (cmd) Run `/plan_security_review` to check the plan for insecure design choices before implementation
- [x] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [x] (cmd) Run `/plan_structure_review` to check for new cross-app dependencies
- [x] (user) Address any structure concerns raised in the plan
- [x] (user) Resolve structure concern: new icons edges (student_interface --> icons, content_engine --> icons)

## 7. Implementation

- [x] (cmd) Run `/implement_plan` to execute the implementation plan
- [x] (user) Spot-check the changes

## 8. Code security review

- [x] (cmd) Run `/security-review` on the pending changes
- [x] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `fls:qa-data-helper` agent)
- [x] (user + cmd) Fix QA bug: Flashcard template comments leak as visible text (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: checklist admonition renders literal `[ ]` instead of checkboxes (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: accordion `open` attribute ignored — pre-opened accordion renders closed (TDD — failing test first, then fix)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues

## 10. Product documentation

- [x] (cmd) Run `/update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 12. Cleanup

- [ ] (cmd) Run `/app_map` to regenerate `docs/app_structure.md` with the new `icons` edges (`student_interface --> icons`, `content_engine --> icons`) and the now-documented `content_engine --> base` edge
- [ ] (user) Review and commit the updated dependency diagram
- [x] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
