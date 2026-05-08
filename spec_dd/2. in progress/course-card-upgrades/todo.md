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

## 7. Implementation

- [x] (cmd) Run `/implement_plan` to execute the implementation plan
- [x] (user) Spot-check the changes

## 8. Code security review

- [x] (cmd) Run `/security-review` on the pending changes
- [x] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues
- [x] (user + cmd) Fix QA bug: Multi-line `{# ... #}` template comments leak as visible text and corrupt the DOM (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Dashboard `<title>` is empty (no `head_title` block set) (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: Modal-vs-page parity — Start button in not-started modal footer is outside the `{% with is_registered=... %}` scope, so it always renders (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: `content_save` rejects valid `icon: drone` + `icon_fallback: phosphor:drone` because validator requires every variant of `icon` to exist in the active set (TDD — failing test first, then fix)
- [ ] (user + cmd) Fix QA bug: Not-started preview (modal + page) is missing the `Start` button (TDD — failing test first, then fix)
- [ ] (user + cmd) Fix QA bug: Card focus ring does not visibly wrap the whole card (TDD — failing test first, then fix)

## 10. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 11. Cleanup

- [ ] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
