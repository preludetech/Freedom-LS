# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items and the two PR commands. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: Resend setup email skip line reads '1 is account already set up' (TDD: failing test first, then fix)
  - Decision: fix it.
- [x] (user) Decide what to do about QA bug: Import stepper labels run together ('1. Upload2. Preview3. Result') (TDD: failing test first, then fix)
  - Decision: fix it, together with the stray bullets between the count links on the import preview.
- [x] (user) Decide what to do about QA bug: Bad-header error names only the first header problem (TDD: failing test first, then fix)
  - Decision: fix it.
- [x] (user) Decide whether a CSV header error should list every problem (unknown, repeated and missing headers) in one message or only the first, then align the spec, the QA plan and base/csv_import.py
  - Decision: list every problem in one message, then the accepted columns.
- [x] Fix B3 (TDD: failing test first): the resend setup email confirmation must read "1 account is already set up and will be skipped." instead of "1 is account already set up and will be skipped."
- [x] Fix B5 (TDD: failing test first): the import stepper must show Upload, Preview and Result as separate numbered steps, not "1. Upload2. Preview3. Result"
- [x] Remove the stray bullet markers between the count links on the import preview (same list-style cause as B5)
- [x] Fix B6 (TDD: failing test first): change `_check_headers` in base/csv_import.py so one error message lists every unknown, repeated and missing header, then the accepted columns
- [x] Reword the spec's header-check sentence (1. spec.md, "a missing `email`, an unknown header or a repeated header rejects the file...") to say the error lists every header problem
- [x] Re-run QA test 2.badhead and confirm it passes against the existing QA plan expectation

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
