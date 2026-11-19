# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [x] (user) Start PostgreSQL on port 6543, then re-run `bash .claude/fls-dev/scripts/install_dev.sh` from this worktree: the worktree setup could not create the branch database or run migrations
- [ ] (user + cmd) Coordinate with extract_panels_framework-4-template-contract when the second of the two specs lands: its `panel-callout` primitive becomes the one this spec ships (token-utility default, no margin note), `panel-notice` leaves its non-primitive list, its HOST_CONTRACT.md row and contract-test row change, and its standalone dead-code list drops `cotton/callout.html`. See spec "Documentation and downstream".

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
- [ ] (cmd) Run `/sdd:document`: In `.claude/skills/brand-guidelines/visual.md`, change the components row "A callout in a page" to "A callout in a page, panel or dialog: `<c-callout tone=… title=…>`", say the `c-admonition` row is for course content only, and make the example snippet use `<c-callout tone=…>` (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, make the notice rule name `<c-panel-callout>` in framework templates and `<c-callout>` in FLS panel and dialog templates, replace every `c-panel-notice` mention, and list the new app-template guard and the no-`c-callout`-in-the-framework rule among the invariants (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: In `claude_plugins/fls-dev/resources/markdown_content.md`, say content widgets are for authored markdown only and app templates use `<c-callout>` (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add a "callout" row distinct from admonitions, `role="alert"`, toasts and notifications (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: In `docs/how tos/theme-fls.md`, rename the `.alert` family to the `.callout` family, add `.callout-warning` and `.callout-icon`, and say it styles `<c-callout>` (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: In `docs/how tos/landing-pages.md`, say `<c-callout>` takes `tone`, not `level` (spec, Documentation and downstream)
- [ ] (cmd) Run `/sdd:document`: Replace every remaining reference to `c-panel-notice` or `c-callout level=` outside `spec_dd/3. done/` (grep `claude_plugins`, `.claude`, `docs`) with `<c-callout tone=…>` or `<c-panel-callout>` as fits, so no skill, brand guideline or how-to offers the old API (spec, Documentation and downstream; Success criteria)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
