# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Fix `test_reference_parts_sharing_an_order_are_numbered_in_creation_order` (fails 3/3: `content_preview.py` breaks order ties by UUID4 `pk`, not creation order), then re-run `/sdd:finish_worktree`
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [x] (user) Force-push the branch after its rebase onto main (the force-push was not permitted in the /sdd:qa_fix session): `git push origin reference-material-content-3-educator-reference --force-with-lease --force-if-includes`
- [x] (user) Review the code and the QA report
- [x] (user) Decide what to do about QA bug: Course content and Reference outline tables do not share column positions — whether stacked outline panels must share fixed column widths (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: outline tables stay tables at 768 instead of cards (pre-existing; the panel-framework rule switches to cards only when columns do not fit, the visual checklist says cards at 768) — pick which rule wins, then fix the code or the checklist line (TDD: failing test first, then fix)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, "Course outline and content previews": add the Reference panel after "Course content" (reference parts as group rows with topic rows, numbered within the panel, no details row, its own footer count, "No reference material in this course yet." when empty, the same withheld note and preview), narrow the "course details are the first row" rule to "Course content", and add the matching "Visual checklist" line (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [x] (cmd) Fix the six PR 284 review nits (outline # column width, upgrade-notes card switch, reference part order tie-breaker, query-count test, Playwright Reference checks)

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
