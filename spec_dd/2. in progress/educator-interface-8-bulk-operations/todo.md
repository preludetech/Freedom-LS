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
- [x] (user) Decide what to do about QA bug: Bulk confirmations use passive wording ('2 learners will be added to Cohort C.') where spec R1.3's example and the QA plan say 'Add 2 learners to Cohort C.' (TDD: failing test first, then fix)
  - Decision: fix it. Every bulk sentence becomes imperative; access and impact sentences move to consequence lines.
- [x] (user) Decide what to do about QA bug: A stale keys-mode selection is skipped per row instead of refused with 'The selection changed since you opened this.' as QA plan §6.12 expects; spec R1.4 only refuses when the count changes (TDD: failing test first, then fix)
  - Decision: keep spec R1.4 and the code; fix the QA plan.
- [x] (user) Decide what to do about QA bug: Picker bulk actions (add/remove cohort, register/unregister) cannot be confirmed with JavaScript off, because the picker sits outside the confirm form and only the htmx refresh enables Confirm (TDD: failing test first, then fix)
  - Decision: write a no-JS test first, fix only if it fails. It passed: the noscript "Show what changes" button re-posts with refresh=1 and enables Confirm, so this was a QA-procedure miss.
- [x] Make the bulk confirmation sentences imperative in educator_interface/actions.py (TDD: tests updated first and seen failing) and reword spec R1.3 to match
- [x] Rewrite QA plan's 'Stale selections' bullet and step 6.12 to match spec R1.4 (keys mode skips a changed row; a count change gives the 422)
- [x] Add a no-JS test for confirming a picker bulk action, and add the picker steps to QA plan step 6.13
- [x] Re-run QA steps 6.12 and 6.13 (picker, JS off) against the updated QA plan

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
