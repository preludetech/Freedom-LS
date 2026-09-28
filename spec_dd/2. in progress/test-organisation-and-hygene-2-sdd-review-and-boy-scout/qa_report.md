# QA report: SDD review and boy-scout for test organisation

Run with `/fls-dev:do_qa` on 2026-09-28 against `3. frontend_qa.md`.

## Methodology

This feature changes the `sdd` plugin, not the web app. The test plan says so itself: nothing runs
in a browser and no dev server is needed. So this run used no Playwright, started no dev server and
took no screenshots. There is no `screenshots/` directory.

Workflows 1 and 3 need `/sdd:implement_plan` run in a separate interactive Claude Code session. A
tester presses Esc partway through and answers `AskUserQuestion` prompts. `do_qa` cannot drive that
kind of session. The user chose to have this run cover the checks it can make directly and hand
Workflows 1–3 to a human. Everything below was run from the feature worktree on the feature branch.
No throwaway branch was created.

Pre-step rebase: the branch already contained `origin/main`, so nothing was rebased.

## Diff scoping

Class: **FULL** (rule 4 fallback: the changed files are Markdown, shell, JSON and one Python test,
with no templates or static files). The class doesn't matter much here. There is no web surface to
test, so the desktop, mobile and tablet browser passes were not run.

Changed files: `.claude/sdd/config.md`, `.claude/settings.json`, `claude_plugins/sdd/README.md`,
`claude_plugins/sdd/agents/sdd-boy-scout.md`, `claude_plugins/sdd/agents/sdd-implementer.md`,
`claude_plugins/sdd/agents/sdd-worker.md`, `claude_plugins/sdd/commands/README.md`,
`claude_plugins/sdd/commands/implement_plan.md`, `claude_plugins/sdd/commands/init.md`,
`claude_plugins/sdd/commands/protected/pre_step_rebase.md`,
`claude_plugins/sdd/scripts/batch_scope_check.sh`,
`claude_plugins/sdd/skills/claude-code-authoring/resources/model_tiering.md`, the spec directory's
own files, and `tests/test_batch_scope_check.py`.

## Smoke gate

Not run. There is no page to load.

## Results

| Check | Result | Notes |
|---|---|---|
| Workflow 1: full run, interrupted and resumed | NOT RUN | Needs an interactive session with Esc and `AskUserQuestion` answers |
| Workflow 2.1: boy-scout budget count | NOT RUN | Needs the QA branch Workflow 1 produces |
| Workflow 2.2: `batch_scope_check.sh 2 <parent>` on real boy-scout commits | NOT RUN | Needs the QA branch. `tests/test_batch_scope_check.py` covers the script's behaviour (12/12 pass) |
| Workflow 2.3: `batch_scope_check.sh 2 nope` | PASS | Exit 64 and the line `Usage: … <batch-number> <from-ref> [<to-ref>]` |
| Workflow 3: blank `## Testing Skills` turns the feature off | NOT RUN | Needs an interactive `/sdd:implement_plan` run |
| Workflow 4.2: `/sdd:init` re-run | PASS | Every step was a no-op. `git diff .claude/sdd/config.md` is empty, and the `ds:testing` and `fls-dev:testing` values survive. Step 6 of `init.md` tells the user to name their Testing Skills |
| Workflow 4.3: `init.md` Step 2 template | PASS | `## Testing Skills` comes after `## Vocabulary Sources` with an empty `-` list |
| Workflow 4.4: `make_pr_quickly.md` unchanged | PASS | `git diff main -- claude_plugins/sdd/commands/make_pr_quickly.md` is empty |

## Bug status

No bugs found in the checks that ran.

## General notes

- The key behaviours of this feature are still unverified by QA. That means resume after an
  interrupt, the review-fix commits, the flagged-item question, the boy-scout move and edit
  commits, `boy_scout_record.md`, and the off switch. They need a human to run Workflows 1–3
  in a separate Claude Code session, following the plan's Setup and Cleanup sections.
- This test plan isn't a browser plan, but `todo.md` sends it through `/fls-dev:do_qa`. For
  plugin-only specs, the QA item in the todo could point at a manual run rather than `do_qa`.

status: ok
reason: report rendered; 4 checks passed, Workflows 1–3 need a human run; no screenshots (no browser surface)
