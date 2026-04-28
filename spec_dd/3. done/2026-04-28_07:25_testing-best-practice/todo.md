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

## 7. Worktree

- [x] (cmd) Run `/start_worktree` to create an isolated worktree for this spec

## 8. Implementation

- [x] (cmd) Run `/implement_plan` to execute the implementation plan
- [x] (user) Spot-check the changes

## 9. Code security review

- [x] (cmd) Run `/security-review` on the pending changes
- [ ] (user) Address any issues raised

## 10. QA

- [x] (user) No QA needed — feature has no frontend changes
- [x] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `qa-data-helper` agent)
- [x] (user) Review the QA report
- [x] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [x] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues

## 11. Pull request

- [x] (user) Open a pull request
- [x] (cmd) Run `/address_pr_review` as review feedback comes in
- [x] (user) Merge the PR once approved

## 12. Cleanup

- [x] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
