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
- [ ] (user) Run QA Test 4.5 with VoiceOver or NVDA on the Interactive Widgets Audio reveal: activating the reveal control announces the word once, the auto-hide announces nothing (see qa_report.md)
- [ ] (user) Run QA Test 10 on a real iPhone (Safari) and Android phone (Chrome): tap B's eye-closed space, the clip plays on the first tap and again after the auto-hide
- [x] (user) Decide whether to update 1. spec.md, 2. plan.md and 3. frontend_qa.md to the reveal button's current name 'Reveal answer for <symbol>' (changed in commit c5a791f9a)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Update `claude_plugins/fls-dev/resources/markdown_content.md`: add `c-audio-reveal` to the widget list, make the allow-list copy match `config/settings_base.py` (including `symbol` on `c-audio` and `c-grid`), and say slot widgets emit their slot as-is (spec "Documentation and downstream")
- [x] (cmd) Update `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`: add an `audioReveal` row to the component inventory (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
