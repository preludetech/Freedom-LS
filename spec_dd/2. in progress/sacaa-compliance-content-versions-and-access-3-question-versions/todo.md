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
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether `content_save` should print the `Question versions: N new, M revised, K unchanged` line on a run that saves no questions (it now prints only when at least one question was saved, because printing it always broke an existing post-transaction output test); if yes, make it unconditional and update that test
- [ ] (user) Decide whether an unanswered row on check-your-answers for a quiz-scored application form should show the live wording (spec) or the pinned served version (current behaviour, since a quiz sitting's served paper pins every question); if live, change `application_check_answers` in `course_applications/views.py` to use the live question for unanswered rows

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: add `FormQuestionVersion` and pinned version to `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` (spec, "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
