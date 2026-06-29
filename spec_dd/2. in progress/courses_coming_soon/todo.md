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


## 4. Plan

- [x] (cmd) Run `/plan_from_spec` to generate the implementation plan and QA plan
- [-] (user) Review both plans and edit where needed

## 5. Plan security review

- [-] (cmd) Run `/plan_security_review` to check the plan for insecure design choices before implementation
- [-] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [x] (cmd) Run `/plan_structure_review` to check for new cross-app dependencies
- [x] (user) Address any structure concerns raised in the plan
- [x] (user) Resolve structure concern: new course_interest app and its inbound/outbound cross-app edges (Task 1.2 callout) — DECISION: accept & document. App stays as designed (mirrors course_applications); regenerate docs/app_structure.md via /app_map after implementation.
- [x] (user) Resolve structure concern: course_access→course_interest reverse() URL-name coupling — record as a graph edge or not (Task 2.2 callout) — DECISION: record a dashed loose edge `course_access -.-> course_interest`. NOTE: /app_map only detects Python imports, so this reverse()-by-name edge must be added manually when regenerating docs/app_structure.md.

## 7. Implementation

- [ ] (cmd) Run `/implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [ ] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `fls:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues

## 10. Product documentation

- [ ] fls:sdd:update_claude_plugin_fls_content
- [ ] (cmd) Run `/update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 12. Cleanup

- [ ] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
