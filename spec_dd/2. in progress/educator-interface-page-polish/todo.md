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

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, add the dashboard rule ("anything the dashboard names, the educator can reach in one click, and a named learner or cohort opens its quick view") with a Visual checklist line; say the learner Settings tab's Name panel opens with an Email row; describe the learner Courses tab as a table (one row per registration) followed by per-course sections (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, remove the dialog-footer full-size exception (Triggers text and table row: full size only from `md` up; the "What enforces it" test names and Playwright line; the Visual checklist line); add the spaced course rows exception to the list-value spacing rule; document the dialog `running` lock; document `<c-panel-progress-bar size="small">`; add the exception that a quick view trigger may sit in `<c-panel-list-row>`'s trailing slot (spec "Documentation and downstream", §5, §6, §7)
- [ ] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, add to the `appModal` inventory row that `running` locks Cancel, the close button and Esc during an in-request bulk run (spec §6)
- [ ] (cmd) Run `/sdd:document`: in `freedom_ls/panel_framework/HOST_CONTRACT.md`, replace the 44px dialog-footer height rule with the small-on-a-phone button rule (spec §7 and "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
