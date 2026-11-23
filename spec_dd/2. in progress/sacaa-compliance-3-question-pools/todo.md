# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Re-run the full test tier when no other worktree is running tests: the first full run had 414 unfinished tests and 8 flaky failures that passed on re-run, and the second was stopped at about 33% for low memory. If it is green apart from the two audio clip tests, the branch is verified.
- [x] (user) Decide what to do about `learner_interface/tests/playwright/test_audio_clip_flow.py::test_transcript_opens_at_once_with_reduced_motion` and `::test_transcript_toggle_lines_up_with_the_clip_title`: both fail the same way on origin/main, so they are not this branch's, but they keep every full run at FAIL until fixed on main.
- [x] (user) Review the bundled validator re-sync in `claude_plugins/fls-content/validate/` (schema.py, validate.py, tests): it went in with the demo course commit instead of in the documentation step, because the demo course failed the bundled validator's demo test without it. `/sdd:document` should find it already synced; the `form-files.md` docs are still to do there.

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
