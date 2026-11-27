# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [ ] (user) Decide whether to add freedom-ls-concrete-template to the concrete-project list in .claude/fls-dev/config.md so /fls-dev:update_concrete_projects applies this spec's upgrade notes to it (spec Open questions)

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Put `UV_NO_SYNC=1` in your shell profile and in the `env` block of `.claude/settings.local.json`, so `uv run` and the pre-commit hook keep a linked package worktree (spec Requirements §4)
- [ ] (user) Decide whether migration educator_interface 0004 may stop with ProtectedError on a database where an audit_log AuditLogEntry points at the old freedom_ls_panel_framework content type (AuditLogEntry.target_content_type is PROTECT). Check production for such rows before deploying, then either keep the migration or have it handle those rows
- [ ] (user) Decide whether FLS needs its own scan for private panel_framework imports. The package dropped test_hosts_import_only_public_names, which scanned FLS, so no guard now stops FLS importing a private framework name. If yes, add an FLS invariant test that imports only names from the package's public lists
- [ ] (user) Decide whether to keep htmx.config.defaultSettleDelay = 0 in the package's Playwright conftest (django-panel-framework tests/playwright/conftest.py). It stops test_editable_list_flow failing about 1 run in 5 on SQLite, where a click inside htmx's 20ms settle window was dropped. If not, find why htmx drops that request and fix it in the package

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
- [ ] (user) Rebuild and publish the `fls-base` image from `/home/sheena/workspace/lms/freedom_ls_infra/fls-base/Dockerfile` before deploying any FLS commit that carries the `django-panel-framework` pin (spec Requirements §6). The plan checks only stage 2's dependency install; a whole `docker build` is not run because stage 1 fails on FLS's own `package.json`
