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
- [ ] (user) Run `/sdd:roadmap` to add the two new ideas (`bulk-run-audit-summary`, `audit-log-describe-test-flake`) in `spec_dd/1. next/` to the roadmap
- [ ] (user) Review the code and the QA report
- [x] (user) Run `uv run manage.py check` with DEBUG=False and TASKS on the immediate backend (expect freedom_ls_panel_framework.W001) and `uv run manage.py check --settings=config.settings_prod` (expect no W001); the security-guard hook blocked both during implement_plan
- [x] (user) Review the standalone test run's departures from the plan: the test app has no apps.py (label `standalone_app`, because the app-map generator broke lint-imports with one), its User has a nullable `site` FK for `make_staff_user(site=...)`, and `_panel_test_tables` in `freedom_ls/panel_framework/tests/conftest.py` changed beyond the guarded import so it works under --nomigrations; keep them or say what to change
- [x] (user) Decide whether to fix the test-order flake in `freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details` (failed in two loaded full runs, passes alone; this branch does not touch audit_log) and the xdist-only failures of the `needs_fls_host` tests in `freedom_ls/panel_framework/tests/test_reference.py` that reload `config.urls` (DRF 'basename user already registered'); a separate idea is the likely home
- [x] (user) Decide what to do about QA bug: bulk runs write no audit-log run summary and no shared run_id (pre-existing; no production code calls `record_run_summary`). Decide where the hook lives, given the panel framework may not import FLS's audit_log, and whether the bulk confirmation gets the reason input the audit-log spec asks for (TDD: failing test first, then fix)
- [x] (user) Start Docker (Postgres and the pooler on 127.0.0.1:6543 were down after a reboot), then re-run the full test tier: the full run after the QA fix 3ebf5c197 was unusable, with 8976 connection errors and 7 failures under that load (test_course_player query count, test_permission_matrix assign_cohort_viewer other_organisation, test_dashboard started-course ranking, two webhooks TestFireWebhookEventWithoutRequest tests, mail test_backends database task backend, tests/test_playwright_fixtures.py). Fix any that still fail

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, document the `PANEL_FRAMEWORK_SITE_RESOLVER` setting, `BulkActionRun.objects.for_request` and `for_site`, `site=` on create, the `freedom_ls_panel_framework.W001` `TASKS` warning, the import guard and the bulk-run scoping guard (spec section "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/skills/multi-tenant/SKILL.md` and `claude_plugins/fls-dev/resources/multi_tenant.md`, note that `BulkActionRun` is not a `SiteAwareModel` and takes an explicit `site` (spec section "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/skills/testing/SKILL.md`, document the standalone run command and the `needs_fls_host` marker (spec section "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
