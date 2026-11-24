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
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether the First Class button labels still need a fix: the measured test (`freedom_ls/educator_interface/tests/playwright/test_touch_targets.py`) found every label within 0.5px of centre in Chromium on Linux with DM Sans 4.004 and the fallback font, so no CSS changed. If you still see off-centre labels, note the browser and OS and run `/sdd:qa_fix` to apply the plan's `text-box: trim-both cap alphabetic` fix against that test; otherwise close this item
- [ ] (user) Check the DM Sans test fixture licence: `freedom_ls/base/tests/fonts/OFL.txt` was assembled from the copyright and OFL 1.1 declaration in the font's own name table plus the standard OFL 1.1 text; keep it, or replace it with the upstream DM Sans OFL.txt

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:document`: if the button-label fix ships the brand fonts or their `@font-face` metric overrides, update `docs/how tos/theme-fls.md` to say so (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
