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
- [x] (Spec|user) Decide how to handle form-attempt identity for (ANSWERED, Question): FormProgress.id, a new tracker-issued UUID, or caller-supplied UUID
- [x] (Spec|user) Decide how to handle per-site IP-capture toggle (global setting only for now, or add a per-site override model in scope)
- [x] (Spec|user) Decide how to handle the `Event` model redeclaring `SiteAwareModel`'s `site` FK to null/SET_NULL — confirm the override is acceptable or choose an alternative

## 3. Threat model

- [x] (cmd) Run `/threat-model` against the spec
- [x] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [x] (cmd) Run `/plan_from_spec` to generate the implementation plan and QA plan
- [x] (user) Review both plans and edit where needed

## 5. Plan security review

- [x] (cmd) Run `/plan_security_review` to check the plan for insecure design choices before implementation
- [x] (user) Address any concerns raised in the plan
- [x] (user) Resolve plan security concern: erasure DB credential storage and TLS
- [x] (user) Resolve plan security concern: migration 0002 superuser revoke no-op

## 6. Plan structure review

- [x] (cmd) Run `/plan_structure_review` to check for new cross-app dependencies
- [x] (user) Address any structure concerns raised in the plan
- [x] (Plan structure review|user) Resolve structure concern: `experience_api` now depends only on `accounts` and `site_aware_models`. Outgoing edges to `content_engine`, `role_based_permissions`, and `student_management` were removed by moving snapshot helpers, the erasure blocker, and (now) role handling out of `experience_api`. Remaining new edges are `experience_api --> accounts`, `experience_api --> site_aware_models`, `student_interface --> experience_api`, `student_progress --> experience_api`. Regenerate `docs/app_structure.md` via `/app_map` after implementation lands.

## 7. Worktree

- [x] (cmd) Run `/start_worktree` to create an isolated worktree for this spec

## 8. Implementation

- [x] (cmd) Run `/implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 9. Code security review

- [ ] (cmd) Run `/security-review` on the pending changes
- [ ] (user) Address any issues raised

## 10. QA

- [ ] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues
- [ ] (user) No QA needed — feature has no frontend changes

## 11. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 12. Cleanup

- [ ] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
