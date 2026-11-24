# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [ ] (user) Confirm or overrule the three assumed defaults under `## Open questions` in `1. spec.md` (audit entry, admin `answer_groups`, time taken)
- [ ] (user) Write the follow-up idea for the deferred quiz-attempt export (served order and seed for inspectors) in `spec_dd/1. next/`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether educators need their own route to download a learner's file-upload answer on the attempt review: the Paper panel reuses form_engine/inputs/file_upload.html, whose Download button points at own_question_answer_file, which appears to serve the file owner only, so the link may fail for an educator (no test covers it); if so, add an educator-side file route and a test
- [ ] (user) Decide whether the quiz attempt quick view keeps both links to the attempt review page (the quick-view chrome's standard 'Open full page' icon and the body's 'Open full review' link), drops the body link, or hides the chrome link for this section, then make that change test first (QA bug B4 in qa_report.md)

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, add the Placement table row "A learner's Courses tab quiz attempts table | The attempt number opens the attempt (quick view; full attempt review page)" (spec section "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, add one short paragraph each on `in_menu` (with `is_in_menu`), `get_back_link` and the `"datetime"` kind of `detail_row` (spec sections "Panel framework" and "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add **attempt review** as a page term, pointing at the existing `FormProgress` / `CourseFormAttempt` entry for "attempt" (spec sections "Terminology" and "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
