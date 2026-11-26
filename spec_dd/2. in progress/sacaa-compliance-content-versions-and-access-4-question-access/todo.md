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
- [ ] (user) Decide whether to fix tests/test_select_tests.py::test_malformed_remote_entry_exits_2_naming_the_key: its 3 cases fail whenever DS_TEST_REMOTE=off is set (as the local full-suite run sets it) because the test does not clear that variable; it is unrelated to this spec and also fails on main. A one-line monkeypatch.delenv in the test would fix it.

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`: add the noun `question` ("question detail of one or more quizzes, read rather than changed") to the Changes noun list, extend the `viewed` row with `question.viewed`, and add "question bank viewer" and "question detail" as the spec's Terminology defines them (spec: Requirements, Audit action)
- [ ] (cmd) In `freedom_ls/audit_log/README.md`: add a row for `question.viewed` to the action table, with its target, subjects and `details` per surface (spec: Requirements, Audit action)
- [ ] (cmd) In `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` and `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`: record that a quiz row of the course outline shows a disabled Preview with its reason to a viewer without the question bank viewer role, the one exception to "a row the viewer cannot act on leaves its buttons cell empty" (spec: Decisions, Disabled Preview on quiz rows)
- [ ] (cmd) In `docs/how tos/theme-fls.md`: drop the `confusions` empty-state slot and the `data-subhead="wrong-answers"` hook from the list of `reports/partials/` hooks, since the PDF no longer draws them (spec: Requirements, Cohort report PDF)
- [ ] (cmd) In `spec_dd/1. next/sacaa-compliance-content-versions-and-access-5-answered-version-review/idea.md` and the effort's notes in `spec_dd/1. next/roadmap.md`: say the attempt review is gated and logged by this spec, and that spec 5 reuses `can_view_course_questions`, `record_question_view` and the Paper panel gate and adds only the answered-version display (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
