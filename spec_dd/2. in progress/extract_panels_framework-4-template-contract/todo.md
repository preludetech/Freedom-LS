# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Push the rebased branch: run `git push origin HEAD --force-with-lease --force-if-includes` (the permission system blocked it for Claude)
- [x] (user) Decide what to change after reading upstream_change_review.md, then edit the idea, spec or plan it names
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether `boolean_true` and `boolean_false` join `REQUIRED_ICON_NAMES` in `freedom_ls/panel_framework/checks.py`: `_details_value.html` picks them inside an `{% if %}`, so the icon check misses them (HOST_CONTRACT.md lists them by hand); if yes, add them there and to the extra names in `freedom_ls/panel_framework/tests/invariants/test_icon_names.py`
- [x] (user) Decide whether to amend the spec's success-criteria greps: `_base\.html` matches the framework's own `_main_base.html`/`_panel_base.html` (the invariant uses `(?<![\w])_base\.html`), and the `FREEDOM_LS_PACKAGE_DIR` grep matches the invariant's own regex in `test_templates.py`
- [x] (user) `freedom_ls/webhooks/tests/test_admin.py::TestWebhookEndpointFormTransformation::test_saving_endpoint_with_transformation_fields` resolves example.com over DNS and failed once in the full run (passes on rerun); decide whether to make it network-free (unrelated to this branch)
- [x] (user) Decide what to do about QA bug: FLS wrappers make the minimal-shell reference page unstyled (TDD: failing test first, then fix). Under FLS settings the FLS `panel-*` wrappers replace every framework primitive, so the minimal shell shows `btn`/`chip` classes that `reference.css` does not style; decide whether §4 of `3. frontend_qa.md` is checked only in the framework's standalone run, or FLS's wrappers step aside in the minimal shell
- [x] (user) Decide whether the reference page should render a navigation toggle in the minimal shell: it sets no page title or menu groups, so `3. frontend_qa.md` §4's 375-wide bottom-sheet check had nothing to open; then amend the QA plan or the page
- [x] (user) Run `3. frontend_qa.md` §1's before/after comparison against a `main` server: QA skipped it because the `main` worktree was in use by another session and its database held no demo data
- [x] (user) Decide how to exercise `3. frontend_qa.md` §2.4.3 (a confirm dialog whose reason is required): no FLS action in the demo data requires a reason, and the reference page's `reason_required` example does not validate; amend the plan or name an action

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Update the `fls-dev` skills that name moved or renamed things, from the spec's "Documentation and downstream" section: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (the `c-panel-*` primitive names, the stylesheet at `freedom_ls/panel_framework/css/panel_framework.css`, the drift guard's new copies: `pagination_suffix`, the Playwright helpers and `panelDropdownMenu`), `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` (add `panelDropdownMenu`), `claude_plugins/fls-dev/skills/icon-usage/SKILL.md` (`REQUIRED_ICON_NAMES` and its check), `claude_plugins/fls-dev/skills/testing/SKILL.md` and `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md` (the standalone run now covers the component and invariant tiers; the framework's own Playwright helpers). Generic plugins stay untouched
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
