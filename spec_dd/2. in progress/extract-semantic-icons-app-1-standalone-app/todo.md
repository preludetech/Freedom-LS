# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed
- [ ] (user) Force-push the branch, which was rebased onto main before planning and declined by the permission check: `git push origin HEAD --force-with-lease --force-if-includes`

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide what `data-icon` a literal (authored) glyph such as `heroicons:scale` should carry: the glyph name (it can collide with semantic names like `check`), `<set>:<glyph>`, or none. Then either make `_render_literal` in `freedom_ls/icons/render.py` pass it (TDD: failing test first, then fix), or change Test 2 in `3. frontend_qa.md` and the course-icon step in `2. plan.md` to check the path body as the shipped test does. See bug B1 in `qa_report.md`

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Update `claude_plugins/fls-dev/skills/icon-usage/` (SKILL.md, `resources/configuring-icons.md`, `resources/custom-icon-backend.md`): the `SEMANTIC_ICONS_*` names, `SEMANTIC_ICONS_ICONIFY_DIR`, the bundled-data lookup and overlay, and the standalone command (spec: Documentation and downstream)
- [x] (cmd) Update `claude_plugins/fls-dev/skills/testing/SKILL.md`: the icons standalone command `uv run pytest -c freedom_ls/icons/tests/standalone_pytest.ini freedom_ls/icons/tests` beside the panel framework's, and `SEMANTIC_ICONS_ICONIFY_DIR` (spec: Documentation and downstream)
- [x] (cmd) Update `claude_plugins/fls-dev/resources/testing.md`: rename `FREEDOM_LS_ICON_SET` to `SEMANTIC_ICONS_SET` in the pinned-config rule, add the icons standalone command, and add the generator's `[[tool.test_tiers.tooling]]` entries (spec: Documentation and downstream)
- [x] (cmd) Update `claude_plugins/fls-dev/skills/app-settings/SKILL.md`: the standalone-app copy rule, the `SAME_SOURCE` invariant, and that `required_settings_errors` is not copied (spec: Documentation and downstream)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
