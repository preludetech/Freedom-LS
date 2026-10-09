# Research: where the SDD workflow runs pytest today

Scope: every place the Claude Code workflow runs pytest (or tells a model or agent to), the flags used, and how often that fires across one spec's lifecycle. Facts only, except section 3. All paths are relative to the worktree root. Read directly from the files named; nothing was executed.

## 1. Inventory

Every site that runs pytest in the workflow. "Full" means the whole `testpaths` (`freedom_ls`, `tests`, `claude_plugins/fls-content`, `pyproject.toml:82`) under the default `addopts` (section 4).

| # | Site (file:line) | Trigger | Command and flags | Scope | Background? | Notes |
|---|---|---|---|---|---|---|
| 1 | `claude_plugins/django-stack/commands/rebase_main.md:185` | Step 9 of the rebase command. It is the `Rebase command` in `.claude/sdd/config.md:10`, so the pre-step rebase runs it. Only reached if Step 3 (`rebase_main.md:57-67`) finds `origin/main` is not already an ancestor of HEAD. | `uv run pytest -x -q` | Full, stop at first failure | Not stated | "Run this until it passes". When green, `-x` has walked the entire suite, so it costs a full run. |
| 2 | `claude_plugins/django-stack/commands/rebase_main.md:191` | Same step, immediately after #1 passes. | `uv run pytest -q` | Full, no `-x` | Yes: `rebase_main.md:194-197` says `run_in_background: true`, wait for notification, no `ps`/`pgrep` polling, no `timeout`, "can take more than 10 minutes". | Up to 3 attempts after a failure (`rebase_main.md:206`). Followed at Step 10 by `uv run pre-commit run --all-files` (`rebase_main.md:211`). |
| 3 | `claude_plugins/sdd/commands/implement_plan.md:49` | Each implementation batch sub-agent (`general-purpose`, `model: "sonnet"`), after its last plan step, before its `[batch <id>]` commit. | `uv run pytest` | Full, no `-x` | Yes (`implement_plan.md:49`, same wording) | One per batch. "All tests must pass before moving to the next batch" (`implement_plan.md:68`). A `failed` batch is retried at most twice (`implement_plan.md:65`), each retry running it again. |
| 4 | `claude_plugins/sdd/commands/implement_plan.md:91` | Step 3 Final Verification, via `sdd:sdd-mechanic`, after all batches. | `uv run pytest` | Full, no `-x` | Yes (`implement_plan.md:91`) | Repeats "from step 1" if a success criterion is unmet and a sub-agent fixes it (`implement_plan.md:93`). The Design-check fix batches (`implement_plan.md:82`) are also batches and run #3. |
| 5 | `claude_plugins/fls-dev/agents/qa-bugfixer.md:77` | QA bug fixer, Step 2 (confirm RED). | `uv run pytest <file>::<test> -x` | Targeted, one test | Not stated | Carries the default `addopts` (`--cov` etc.). |
| 6 | `claude_plugins/fls-dev/agents/qa-bugfixer.md:92` | Step 4 (confirm GREEN). | `uv run pytest <file>::<test> -x` | Targeted, one test | Not stated | Same. |
| 7 | `claude_plugins/fls-dev/agents/qa-bugfixer.md:101` | Step 5, "Run the full suite". | `uv run pytest` | Full, no `-x` (`qa-bugfixer.md:109` says the missing `-x` is deliberate: the orchestrator skips re-driving the regression layer on the strength of this run) | Yes (`qa-bugfixer.md:104-107`) | One per QA bug fixed. `do_qa.md:495-496` caps it at 3 fixer spawns per run, 1 attempt per bug, "each one costs a full pytest suite plus a Playwright re-verify". |
| 8 | `claude_plugins/fls-dev/commands/protected/frontend_check.md:73-82` | Step 4 of the front-end check, run by the pre-step rebase (`pre_step_rebase.md:51-63`) after a rebase that changed front-end paths. | Spawns `fls-dev:qa-bugfixer` per failing page (max 3) | Each spawn runs #5-#7 | As #7 | The check itself runs no pytest; only its fixers do. Only when a page fails. |
| 9 | `claude_plugins/sdd/commands/address_pr_review.md:54` | Step 5 of `/sdd:address_pr_review`, after fixing review comments. | `uv run pytest -x -q` (the text above it says "run the full test suite") | Full, `-x` | Yes (`address_pr_review.md:57-60`) | One per review round. Step 6 runs `uv run pre-commit` (`address_pr_review.md:69`). The command's own Step 0 (`address_pr_review.md:3-5`) also fires a pre-step rebase, hence #1-#2. |
| 10 | `claude_plugins/django-stack/commands/commit.md:4` | `/ds:commit`, run by hand. Not called by any SDD command found by grep. | `uv run pytest` | Full | Not stated | The README line `claude_plugins/sdd/commands/README.md:144` describes it as the checkpoint-commit path. |
| 11 | `claude_plugins/fls-dev/commands/concrete/update_fls.md:148, 165, 212, 235` | The downstream-project updater, not part of the FLS spec lifecycle. | `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` | Portable subset | Not stated | Listed for completeness. Out of scope for the spec lifecycle. |
| 12 | `claude_plugins/django-stack/commands/tdd_implement.md:3,7` | `/ds:tdd_implement`. | No pytest command written; points at the testing skill. | n/a | n/a | Nothing fires from the file. |

Wrappers and plumbing that touch pytest but do not run it:

- `claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh:5` (header comment: "Run before the test suite so pytest-playwright or a browser never sees pre-rebase output"). It runs `uv sync`, `npm i`, `npm run tailwind_build`, `dev_db_init.sh` (`rebuild_after_rebase.sh:10-13`). It is the `Rebuild script` (`.claude/ds/config.md:30`), run at `rebase_main.md` Step 8 (`rebase_main.md:168-174`) before #1-#2. So every rebase also pays `uv sync`, `npm i`, a Tailwind build and a DB init.
- `claude_plugins/sdd/agents/sdd-mechanic.md:4` lists "running the test suite" as a chore. It is the agent used for #4. It contains no flags.
- `.claude/settings.json:15` and `claude_plugins/django-stack/templates/settings.json:15` allow `Bash(uv run pytest:*)`, so all variants run without a prompt.
- `claude_plugins/fls-dev/skills/testing/SKILL.md:136-139`, `claude_plugins/fls-dev/resources/testing.md:39-42` and `claude_plugins/django-stack/skills/testing/SKILL.md:45` document `uv run pytest -n auto` (xdist, opt-in) and the downstream marker expression. No workflow command above uses `-n`.

### When the pre-step rebase fires

- Every `(cmd)` item in `todo.md` is dispatched by `/sdd:next`, which does a pre-step rebase at Step 2.5 first (`claude_plugins/sdd/commands/next.md:28-37`).
- Run directly, each of these commands has its own Step 0 that follows the same helper: `improve_idea`, `spec_from_idea`, `spec_review`, `plan_from_spec`, `plan_security_review`, `plan_structure_review`, `implement_plan`, `do_qa`, `update_product_docs`, `update_upgrade_notes`, `update_claude_plugin_fls_content`, `address_pr_review`, `finish_worktree` (grep of `pre_step_rebase` in `claude_plugins/**/*.md`). `/ds:threat-model` and `/ds:security-review` have no Step 0 of their own; they get one only through `/sdd:next`.
- The helper (`pre_step_rebase.md:37-49`) runs the configured `Rebase command` (`.claude/sdd/config.md:10`: `rebase_main.md`). That command stops early with `rebased: no` (no tests) only when `origin/main` is already in the branch (`rebase_main.md:57-67`). If main has moved at all, even by a docs-only commit, Steps 5-10 run, including the tests at Step 9. Nothing in `rebase_main.md` or `pre_step_rebase.md` looks at which files main changed before running the suite.
- `finish_worktree.md:144-147` can run `rebase_main` once more on land-exit 7 (main moved after Step 0), which is another #1+#2.
- `finish_worktree.md:73` states "The rebase command has already run the test suite and pre-commit; there is nothing to re-run here", so finish_worktree adds no pytest of its own.

## 2. Worked count for one spec

`todo.md` has 14 stages and 16 `(cmd)` items: `improve_idea`, `spec_from_idea`, `spec_review`, `threat-model`, `plan_from_spec`, `plan_security_review`, `plan_structure_review`, `implement_plan`, `security-review`, `do_qa`, `update_product_docs`, `update_upgrade_notes`, `update_claude_plugin_fls_content`, `address_pr_review`, `update_upgrade_notes` (second time), `finish_worktree`. `address_pr_review` repeats once per review round.

Definitions:

- `R` = pre-step rebases where main had moved, so `rebase_main` got past its early exit.
- `N` = implementation batches, including any `design fix` batches.
- `B` = batch retries. Each retry re-runs the batch's suite.
- `M` = QA bugs fixed, at most 3 per run (`do_qa.md:495`).
- `P` = `address_pr_review` rounds.
- `E` = extra rebase on finish_worktree land-exit 7 (0 or 1).

Each rebase costs 2 full-length passes when green: #1 `-x` runs the whole suite to the end when nothing fails, then #2 runs it again. If something fails, add the partial runs and re-runs, up to 3 attempts.

```
rebase suite passes      = 2 * (R + E)
batch suite runs         = N + B
final verification       = 1  (+1 per unmet-criterion fix loop)
QA fixer full suites     = M
address_pr_review suites = P

total full-length passes = 2*(R+E) + N + B + 1 + M + P
```

Concrete example: 4 batches, 2 QA bugs, no batch retries, 1 PR round, no loops, and main moving before every one of the 16 `(cmd)` steps (the maximum for the `/sdd:next` path), so `R = 16`, `E = 0`:

```
rebase    2 * 16 = 32
batches   4
final     1
QA        2
PR        1
total     = 40 full-length passes
```

Other cases:

- `R = 16`, `E = 1` (finish_worktree retry): 42.
- Main moving only before the implementation-and-after steps, say `R = 8`: 16 + 4 + 1 + 2 + 1 = 24.
- Main never moves (`R = 0`): 0 + 4 + 1 + 2 + 1 = 8. This is the floor for this example, and every one of the 8 is a run the workflow asks for explicitly.
- Each added batch adds 1; each added QA bug adds 1 (max 3); each added review round adds 1 (plus its own rebase if main moved).

Of the 16 rebase-driven runs-per-step, 7 steps come before implementation exists (`improve_idea` through `plan_structure_review`), where the branch contains only `spec_dd/` files plus whatever main brought in.

Time basis: the briefs say the suite "can take more than 10 minutes" (`implement_plan.md:49`, `rebase_main.md:196`, `qa-bugfixer.md:106`). The idea says it takes "a very long time". I did not measure it.

## 3. Redundant versus load-bearing

Redundant with a neighbouring run (nothing relevant changed in between):

- **#1 followed by #2 on a green run.** `-x` and non-`-x` cover the same tests with the same code. When #1 passes it has already run every test, and #2 reruns them unchanged. One pass is the minimum that gives the "full suite is green" result (`rebase_main.md:185-191`).
- **Rebase test runs in pre-implementation stages.** From `improve_idea` to `plan_structure_review` the branch's own commits are `spec_dd/` docs, so the only code under test is what main brought in. Main's own CI (`tests.yml`) already ran that code on the PR/push to main, so re-running it on a branch that touches nothing executable proves nothing new.
- **Rebase test runs after docs-only steps** (`update_product_docs`, `update_upgrade_notes` x2, `update_claude_plugin_fls_content`) when the rebase brought in only docs or unrelated files. Nothing in `rebase_main.md` checks that.
- **#4 (final verification) after the last batch's #3.** If no commit landed between the last batch's suite and Step 3, the code is identical. The one difference is that a Design-check fix batch can run in between (#3 runs for it too), and `implement_plan.md:93` loops back.
- **#7 (QA fixer's full suite) against the following rebase run (#1+#2).** If main did not change between them, the rebase for the next step re-proves the same tree. `do_qa.md:526-528` already relies on #7 as the regression proof.
- **#9 `address_pr_review` `-x -q`** after the rebase that precedes it (`address_pr_review.md:3-5`): the rebase's suite and this one differ only by the review fixes.
- **The first rebase suite after the final batch.** The implement-plan run (#4) and the next step's rebase both prove the same tree unless main moved.
- **#5/#6 with the default `addopts`.** They are targeted, and are the test-first loop. They are cheap by selection, but see section 4 about coverage.

Load-bearing (a change happened that the earlier run did not see):

- **#3 per batch.** Each batch is new production code and tests. It is the gate before the `[batch <id>]` marker commit (`implement_plan.md:36,50,68`).
- **#2 after a rebase that brought in code that interacts with the branch.** Conflict resolution can silently break semantics. `rebase_main.md:151-166` guards against lost changes with diff checks, but only the suite catches behavioural breakage.
- **#7 after a QA fix.** It is the only regression proof for a fix that is often a template or JS change (`qa-bugfixer.md:109`).
- **#9 after review fixes**, since the review fixes are fresh code.
- **At least one full run before the PR and one before the land on main.** The final state going to main has to be proven once. The rebase before `finish_worktree` supplies it today (`finish_worktree.md:73`).

## 4. What the default `addopts` costs on every run

`pyproject.toml:83`:

```
--strict-markers -m 'not ci_only and not weasyprint' --disable-socket --allow-hosts=127.0.0.1,::1
--cov --cov-branch --cov-report=term-missing --cov-fail-under=73
--tracing=retain-on-failure --screenshot=only-on-failure
```

Other settings:

- `timeout = 300` (`pyproject.toml:90`). pytest-timeout is per test.
- `markers`: `playwright`, `ci_only`, `fls_internal`, `weasyprint` (`pyproject.toml:84-89`).
- `[tool.coverage.run] branch = true`, `source = ["freedom_ls"]`, with migrations, tests, conftest and `qa_helpers` omitted (`pyproject.toml:100-116`). `[tool.coverage.report] show_missing = true, skip_covered = false` (`pyproject.toml:118-120`).
- `pytest-randomly` (`pyproject.toml:64`) reorders and reseeds every run. `pytest-xdist` is installed (`pyproject.toml:66`) but not in `addopts`. The testing skill says "xdist is opt-in, not baked into `addopts`" (`claude_plugins/django-stack/skills/testing/SKILL.md:45`). None of the workflow commands pass `-n`.

What each part costs or does on every run:

- **`--cov --cov-branch`**: line and branch tracing of every Python line of `freedom_ls` on every run, on every one of the sites in section 1, including the single-test runs #5 and #6. I did not measure the overhead.
- **`--cov-report=term-missing`**: prints a per-file missing-lines table each run. That is a large block of output returned to the agent that ran it.
- **`--cov-fail-under=73`**: applies whenever `--cov` is active. A run of one test (#5, #6) measures coverage on a tiny slice, so by pytest-cov's behaviour it should report the threshold as unmet and exit non-zero even when the test passes. I did not run this to confirm. If true, it conflicts with the qa-bugfixer's reading of exit codes in Steps 2 and 4. Only the whole-suite runs (#1-#4, #7, #9) give a coverage figure the threshold can meaningfully judge.
- **Playwright tests included locally.** `-m 'not ci_only and not weasyprint'` leaves `playwright` and `fls_internal` selected. So every full local run drives a real browser through `live_server`. `claude_plugins/fls-dev/commands/do_qa.md:481-482` states this ("the project's Playwright tests run in the ordinary `uv run pytest` suite"). CI runs them as a separate job (section 5). `testing.md:39` states the choice is deliberate for FLS regression testing.
- **`--tracing=retain-on-failure --screenshot=only-on-failure`**: Playwright options. Cost on failure only (artefacts written to `test-results/`).
- **`--disable-socket`**: no cost to speak of; stops accidental network use.

Which runs actually need these:

- The coverage threshold is a whole-suite property. It is enforced in CI's `unit-tests` job (section 5), so no local site needs it in order to hold the line; the sites that print it locally are all full-suite runs.
- `-x -q` runs (#1, #9) read only pass/fail, so the term-missing table is output they do not use.
- The targeted runs #5, #6 need neither coverage nor Playwright unless the bug test is itself a `@pytest.mark.playwright` test (`qa-bugfixer.md:70-73`).
- The Playwright tests matter for runs that follow a front-end change. Front-end changes to templates and static files are what `frontend_check.md:24-33` classifies.

## 5. What CI and pre-commit already guarantee

### CI: `.github/workflows/tests.yml`

Triggers: `push` to `main` and `pull_request` to `main` (`tests.yml:3-7`), with `cancel-in-progress` per ref (`tests.yml:9-11`). So every PR push re-runs everything below.

| Job | Lines | What it runs |
|---|---|---|
| `lint` | 14-28 | `ruff check`, `ruff format --check`, `generate_app_map.py --check`, `lint-imports --config test_organisation/import_contracts.toml`, `check_test_mirroring.py` |
| `type-check` | 30-42 | `uv run mypy .` with `DJANGO_SETTINGS_MODULE=config.settings_dev` |
| `unit-tests` | 44-88 | Postgres 17, `npm ci`, `npm run tailwind_build`, then `uv run pytest -m "not playwright"` (10-minute job timeout) |
| `playwright-tests` | 90-145 | Postgres, `npm ci`, Tailwind build, `playwright install --with-deps chromium`, then `uv run pytest -m playwright --no-cov` (15-minute job timeout). Uploads traces on failure. |

Details that matter for what local runs need to prove:

- The CLI `-m` replaces the `-m` in `addopts`, so CI's `-m "not playwright"` does not exclude `ci_only` or `weasyprint` tests. The CI job therefore runs them, with the system libraries CI installs (`fls-dev/skills/testing/SKILL.md:136` says CI supplies the libraries needed to run the `weasyprint` set). Local runs deselect both.
- `unit-tests` keeps the default `--cov --cov-branch --cov-fail-under=73`, so the coverage threshold is enforced there on the non-Playwright set. The Playwright job passes `--no-cov`.
- CI never sees `-x`, `-n` or a targeted subset. It always runs the complete suite, split into two jobs.

### Pre-commit: `.pre-commit-config.yaml`

No hook runs pytest. Hooks:

- pre-commit-hooks: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-merge-conflict`, `check-added-large-files`, `check-ast`, `debug-statements`, `detect-private-key` (`.pre-commit-config.yaml:5-22`)
- `detect-secrets` (`:24-29`)
- `ruff-check` and `ruff-format` (`:31-36`)
- `bandit` (`:38-43`)
- `shellcheck` (`:45-48`)
- local: `mypy` (whole repo, `:58-66`), `app-map-fresh` (`:68-73`), `lint-imports` (`:74-79`), `test-mirroring` (`:80-85`)

So `uv run git commit` is a lint-and-type gate: ruff, mypy, bandit, shellcheck, secrets, import contracts, test mirroring, app map. `qa-bugfixer.md:134-136` and `do_qa.md:527-528` state the same ("they do NOT run pytest"). The pre-commit set matches CI's `lint` and `type-check` jobs (ruff, mypy, app map, lint-imports, test mirroring) plus bandit, shellcheck and secrets locally. Only the pytest results are not duplicated locally by a hook.

What is guaranteed where:

- Per commit locally: lint, types, import contracts, mirroring, app-map freshness, secrets.
- Per push or PR (CI): the same lint and type jobs, the non-Playwright suite including `ci_only` and `weasyprint` tests with the 73% branch-coverage gate, and the Playwright suite separately.
- Per local workflow step: only what section 1 lists.
- Rebase also runs `uv run pre-commit run --all-files` (`rebase_main.md:211`), a whole-repo lint pass, in addition to commit-time hooks.

## 6. Existing "do NOT run pytest" selectivity

- `claude_plugins/sdd/commands/commit_quickly.md:9-11, 23-33`. The speed contract: do not run pytest, ruff, mypy or any check proactively; the hooks are the gate; even after a hook failure only that one check may be re-run, "still no pytest". Contrast with `/ds:commit` (`django-stack/commands/commit.md:4`), which runs the full suite first. README: `claude_plugins/sdd/commands/README.md:144`.
- `claude_plugins/sdd/commands/protected/move_spec_to_in_progress.md:53-54`. "Do not run pytest now: we only moved files that are not under test, so running the tests would be a waste of time."
- `claude_plugins/fls-dev/commands/do_qa.md:526-528`. Trust the fixer's full run for the regression layer; do not re-drive what pytest covers.
- `claude_plugins/sdd/commands/finish_worktree.md:73`. The rebase has already run the suite and pre-commit; nothing to re-run.
- `claude_plugins/fls-dev/agents/qa-bugfixer.md:134-136`. Pre-commit hooks do not run pytest; the Step 5 suite run is the regression proof.
- `claude_plugins/sdd/commands/implement_plan.md:84-85`. Do not run the `frontend_qa` plan during implementation (about QA, not pytest).
- Smaller scopes already in use: the qa-bugfixer's single-test `-x` runs (#5, #6); the `-x` first pass in `rebase_main.md:185` and `address_pr_review.md:54`; the portable marker subset in `update_fls.md` (#11). Single `-n auto` use is documented but unused by commands.
- Gaps in selectivity (facts): no command inspects what changed (docs-only, `spec_dd/`-only) before choosing a scope. No command uses `-n`, `--no-cov`, `-m "not playwright"`, `--lf`, `--sw`, or a changed-files subset.

status: ok
