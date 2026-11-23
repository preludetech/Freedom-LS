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
- [x] (user) Decide whether the 5.8 MB `.test_durations` file stays committed at the repository root: the implementation excluded it from the `check-added-large-files` and `detect-secrets` pre-commit hooks in `.pre-commit-config.yaml`. Keep it, or move the durations elsewhere and drop the exclusions

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/testing/SKILL.md`, describe the remote full run, `DS_TEST_REMOTE=off`, how to read a remote failure (`run: failed` lines and the `.sdd-work/remote_full_run_<branch>.txt` log), and the `.test_durations` regeneration commands; rewrite "What runs where" for the new CI jobs (unit groups, browser groups, `standalone-tests`, `coverage`, `test-verdict`; `-m "not playwright"` and `-m playwright`) and drop "CI on the PR" from `claude_plugins/fls-dev/resources/testing.md` (spec "Documentation and downstream")
- [x] (cmd) In `claude_plugins/django-stack/README.md`, document the optional `[tool.test_tiers.remote]` table, the remote command contract and `DS_TEST_RECORD_PATH`, with no FLS value (spec "Documentation and downstream")
- [x] (cmd) In `claude_plugins/sdd/README.md`, document how a full tier runs a remote command and records it, with no FLS value (spec "Documentation and downstream")
- [x] (cmd) In `.claude/settings.json`, add allow rules for `uv run python claude_plugins/fls-dev/scripts/remote_full_run.py`, `gh workflow run`, `gh run view`, `gh run download` and `gh run cancel` (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [x] (cmd) Fix the five PR 282 review findings (start timeout ignores skipped jobs, standalone re-run command, local outcome ranking in the record plugin, name an unlisted dispatched run, specific exceptions in main)
- [x] (cmd) Add a `.claude/ds/config.md` switch (`## Test Tiers` → `- Remote full run: on|off`, `config.local.md` wins, `DS_TEST_REMOTE=on|off` overrides) to turn the remote full run off without removing `[tool.test_tiers.remote]`
- [x] (cmd) Add `tests/test_sdd_portability.py`: no file under `claude_plugins/sdd` names a test runner, language tool, framework, CI service or another plugin's path
- [x] (cmd) Move the test-run helper and `full_run_record.py` out of `claude_plugins/sdd` into `claude_plugins/django-stack` (`resources/test_runner.md`, `scripts/full_run_record.py`, record under `.ds-work/`)
- [x] (cmd) Replace `run_test_tier.md` with `commands/protected/run_tests.md`: the `Test runner` hook, the five requests (`change`, `everything`, `before landing`, `one test`, `failed`), `status: blocked` on a blank hook; rewrite every SDD caller to it
- [x] (cmd) Remove the remaining tool names from `claude_plugins/sdd` (pytest, node IDs, `uv run`, `manage.py`) and rewrite its README, command README and diagrams in request words
- [x] (cmd) Add the SDD portability rule to `CLAUDE.md` and `claude_plugins/fls-dev/resources/plan_review_structure.md`; update this spec, its plan and the `faster-test-runs-11`, `-12`, `-13` ideas to the new paths
- [ ] (user) Decide how SDD's screenshot scripts (`compress_screenshots.sh`, `design_screenshots.sh`) get pillow and playwright without `uv run --with`: they are the portability guard's only exceptions
- [ ] (user) Decide whether `/sdd:do_qa`'s dependence on the Playwright MCP becomes a hook too
- [ ] (user) Decide what happens to the "Step 9 of the Rebase command" chart in `claude_plugins/sdd/docs/diagrams/rebase.drawio.svg`: it draws django-stack's tier logic (`Tier is full?`, the test selector) inside an SDD diagram. Redrawing it needs draw.io
- [ ] (user) Review the new plan-review brief `claude_plugins/fls-dev/resources/plan_review_plugin_portability.md`, wired under `## Plan Review Hooks`: it replaced the planned edit to `plan_review_structure.md`, which only checks app-graph edges

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [x] (user) Upgrade `gh` to 2.87.0 or later (this machine has 2.46.0); until then every remote full run falls back to a local run
- [ ] (user) Add `"Bash(gh run list:*)"` beside `"Bash(gh run view:*)"` in `.claude/settings.json`: the remote full run now finds its run with `gh run list` (the auto-mode classifier blocked Claude from editing that file)
- [ ] (user) Once main has the workflow, dispatch `Tests` on a branch and confirm it passes with every test group under 12 minutes (spec "Testing")
- [ ] (user) On a dispatch, confirm `test-verdict` fails when one test group is given the wrong `--splits`, and `coverage` fails with `--fail-under` raised above the measured combined coverage (spec "Testing")
- [ ] (user) Report before and after times against `spec_dd/1. next/faster-test-runs/research_test_timings.md`: workflow wall time and a remote full run's wait, queue included (spec "Testing")
- [ ] (user) Remove the worktree and delete the branch once main has it
