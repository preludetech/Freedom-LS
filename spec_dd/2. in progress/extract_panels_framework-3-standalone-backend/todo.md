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
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, document the `PANEL_FRAMEWORK_SITE_RESOLVER` setting, `BulkActionRun.objects.for_request` and `for_site`, `site=` on create, the `freedom_ls_panel_framework.W001` `TASKS` warning, the import guard and the bulk-run scoping guard (spec section "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/multi-tenant/SKILL.md` and `claude_plugins/fls-dev/resources/multi_tenant.md`, note that `BulkActionRun` is not a `SiteAwareModel` and takes an explicit `site` (spec section "Documentation and downstream")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/testing/SKILL.md`, document the standalone run command and the `needs_fls_host` marker (spec section "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
