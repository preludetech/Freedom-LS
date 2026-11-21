# Research: prior art (full-test-run-still-too-often)

Question: what has already been tried for "the SDD process still runs the full test suite far too
often", here or elsewhere, and what happened?

Limits: I had no shell, so no `git log` / `git log --stat`. The history below comes from the done
specs under `spec_dd/3. done/` and the current files. Paths are relative to the repo root.

## 1. Here: the earlier specs

### 1.1 `2026-10-09_09:03_make-sdd-more-efficient` (the test tiers)

What it changed:

- It replaced "run the full suite" with three named tiers, `none`, `targeted` and `full`, defined
  once in `claude_plugins/django-stack/resources/test_tiers.md`. Commands name a tier and never copy
  pytest flags.
- `claude_plugins/django-stack/scripts/select_tests.py` (wrapper `.claude/ds/scripts/select_tests.sh`)
  picks the tier from changed paths. Rules apply first-match-wins per path: `none` globs, then a
  changed test file, then escalation globs (migrations, `conftest.py`, factories, fixtures,
  `urls.py`, middleware, signals, `apps.py`, `pyproject.toml`, `uv.lock`), then the owning app's test
  directory plus its importers (from `docs/app_structure.md`), then tooling paths. An unmapped
  tracked path is `full`; a missing app map is `full`.
- FLS values live in `[tool.test_tiers]` in `pyproject.toml`: `none` = `spec_dd/**` and
  `*.jsx`; `escalation` = `config/**`, `site_aware_models/**`, `content_base/**`; `tooling` maps
  plugin scripts, templates and markdown to `tests/`.
- A `Test tiers` key under `## Test Hooks` in `.claude/sdd/config.md` points sdd at the tier file;
  blank falls back to a plain `uv run pytest`.
- `rebase_main.md` Step 9 became two selections: the branch's diff `origin/main..HEAD` (`none` means
  stop) and main's diff `$OLD_BASE..origin/main` plus post-replay fix-ups, with the branch's own
  tests joined without raising the tier. Partial runs got `--no-cov`; targeted and full got `-n auto`.
- Per-site table: batches targeted, implement final full, QA fix targeted with one full after the
  last fix, PR review targeted, `ds:commit` targeted.

Decisions it made, with the reasons, that this work should respect:

- The escalation list is an explicit glob list, not judgment, because "a model follows a list; it
  does not reliably follow 'use judgment'". Any change here should stay a list or a script output.
- Generic plugins stay generic: Django-generic globs ship in `ds`, FLS globs live in
  `[tool.test_tiers]`. Nothing FLS-specific goes into `ds` or `sdd`.
- Unknown means full. An unmapped tracked path, a missing app map, a failing selector all escalate.
  Skipping on doubt was rejected. (`full_run_record.py` repeats this: a selector that fails or prints
  no tier counts as full.)
- CI is the backstop, not the gate; the guaranteed local full run stays at the milestones.
- pytest-testmon was rejected for now: it disables its data collection when coverage is on, does not
  track templates or static files, is unverified with xdist/pytest-randomly/pytest-django, and starts
  cold in every worktree. It was left open as "can be trialled later as a refinement of the targeted
  tier".
- The four-worker cap on `-n auto` stays (shared dev Postgres).
- "A rebase that brought in nothing the branch's code can interact with runs no tests. CI already
  proved main." This is the idea this work extends; it was stated as settled but implemented only
  through main's diff, not through the branch/main intersection (see gaps).

Gaps it left:

- Main's diff drives the second selection on its own. If main touched an escalation path, the result
  is `full` even when the branch's code never touches that area. The research said the targeted run
  should be "the intersection: the branch's tests plus tests of the files main changed that the branch
  also touches or depends on"; the implementation did not do that intersection.
- The rebuild before tests (dependency sync, npm install, Tailwind build, database init) was left out
  of scope. It still runs on every rebase.
- Making individual tests faster was left to `research_suite_timing.md`.
- Names a "full run after the last QA fix" and "finish worktree, the rebase before landing = one full"
  as fixed milestones. Three full runs a cycle was the designed floor.

### 1.2 `2026-11-19_16:16_spec_dd_efficiency_and_docs` (the "upgrade" the idea refers to)

Its `research_codebase.md` section 1.3 counted 2 to 7 full runs per cycle and section 1.4 listed why
a spec-only diff still triggered a full run. This spec fixed those. What it changed:

- A `checkpoint` tier for `claude_plugins/sdd/commands/protected/run_test_tier.md`, resolved by
  `claude_plugins/sdd/scripts/full_run_record.py` (`read`, `start`, `resolve`, `write`). The record is
  `.sdd-work/full_run_record_<branch>.txt`, the SHA of the last passing full run on a clean tree.
  Resolve order: branch diff `origin/main..HEAD` plus working tree selects `none` gives `none`; no or
  stale record gives `full`; otherwise the selector over `<record>..HEAD`. A record is written only
  when HEAD and the tracked tree did not move during the run.
- Two full-run points: `implement_plan` Step 3 and `finish_worktree` Step 1. QA and `qa_fix` fix
  runs became `targeted` over the fix commits. The `implement_plan` fix loop no longer repeats the
  full run.
- `finish_worktree` passes `<tier>: none` to its rebases, so each pass tests once. The main-moved
  loop runs `checkpoint` after each rebase. The "Step 0's rebase reported `tier: full`" shortcut went.
- `pre-commit` runs on `--from-ref origin/main --to-ref HEAD`, not `--all-files`.
- `pre_step_rebase.md` passes an auto-resolve list (`claude_plugins/sdd/resources/rebase_auto_resolve.md`)
  and skips the upstream-change review pause when every incoming path is a spec-only change.
- Self-recovery in `finish_worktree`, flaky-test diagnosis (3 reruns, two fix attempts, 10 passes),
  `address_pr_review` removed, token trim, draw.io diagrams.

Decisions to respect or deliberately reverse:

- Success criterion that is still the target: "A spec-only branch runs no pytest in any pre-step
  rebase, even when main brought in `pyproject.toml` or migration changes." Today this holds only
  when the branch diff selects `none` (rebase Step 9 item 1). A branch that holds any code change does
  not get it.
- Open question, answered "yes" as an assumed default: "Should main's escalating changes (a migration,
  `uv.lock`) make the checkpoint tier resolve to `full` on a branch with code changes? Yes: the
  branch's code has not run against them. Overrule by editing the Checkpoint tier definition." The
  new answers.md (Q2) deliberately reverses this: branch-related only, with dependency files
  (`pyproject.toml`, `uv.lock`) still escalating. The spec text for the checkpoint definition and
  `rebase_main.md` Step 9 are what must be edited.
- `finish_worktree` Step 1 keeps `<tier>: full` and always runs `Pre-test rebuild`. Answers.md Q1
  reverses this: Step 1 becomes a checkpoint run. Q3 keeps `implement_plan` Step 3 unconditional full.
- Escalation globs are the one list in `select_tests.py` plus `[tool.test_tiers]`; the checkpoint
  tier reuses it ("the selector's escalation globs still force full, including ones main brought in").
- No pull-request check in `finish_worktree`; CI on the PR is the backstop. Keep.
- A failed run, a `RESULT INCOMPLETE`, a skip or a dirty-tree run writes no record. A skip must never
  read as a pass (a `none` summary never contains "passed"). Keep.
- Flaky-test handling and the memory-aware runner (`2026-11-13_14:59_claude-ram-usage`) are in place;
  do not redo.

Gaps it left (candidate causes of "still too often"):

1. Main-diff escalation drives full runs even when the branch is unrelated. The rebase second
   selection (`rebase_main.md` Step 9 item 2) and the checkpoint resolver both use whole-repo escalation
   globs. Records from the main-moved loop pay for other specs' migrations, `conftest.py` edits and
   `pyproject.toml` bumps.
2. `finish_worktree` Step 1 is a full run even when `implement_plan` Step 3's full run passed and only
   `spec_dd/` changed since (the first answer in answers.md). The record exists but Step 1 does not
   read it.
3. `resolve` skips only on `none`. It cannot say "the branch has code, but main's changes do not meet
   it", because it diffs `<record>..HEAD` as a tree diff. After a rebase that tree diff contains main's
   changes, so main's escalating files appear as changes since the record.
4. The record is per worktree and gitignored; any commit by another process during a run, or a dirty
   tracked tree at start, leaves no record, so the next checkpoint is a full run. This was accepted as
   safe but costs time when several processes commit to one worktree.
5. The rebuild (`rebuild_after_rebase.sh`: dependency sync, npm, Tailwind, database init) before a
   test run was out of scope twice and is still unsolved.
6. `fls-dev` `update_*` commands and other `pre_step_rebase` callers still default to `targeted`
   through `rebase_main.md`; whether each of them also hits escalation is not recorded.
7. An unmapped tracked path is `full`. A new top-level file or directory the globs do not know (for
   example a new tooling directory) triggers a full run. The generic `none` list has no `spec_dd/**`
   entry; a project without `[tool.test_tiers]` gets full for spec files (FLS has it, so this does
   not explain the FLS symptom).
8. The record logic and `rebase_main.md` live in two different plugins (`sdd` and `ds`); `ds` cannot
   read the sdd record. A branch/main intersection in the rebase must be passed in or computed by the
   selector, not by reading the record.

### 1.3 Other specs that touched the same machinery

- `2026-09-26_20:24_git-rebase-safety`: rewrote `rebase_main.md`, added the lost-change check,
  `pre_step_rebase.md`, the upstream-change scan and `finish_worktree`'s rebase use. Decision:
  the rebase runs inside the `ds` command, so any key it needs is a `ds` key; `sdd` hooks point at
  it. The test step was left as a full run at that time.
- `2026-11-13_14:59_claude-ram-usage`: memory-gated test runner (`run_tests.sh`), crash retry of the
  unfinished tests only, `oom_score_adj`. Reason: parallel full runs crashed on RAM. Full runs also
  cost RAM, not just time.
- `2026-10-01_09:40_database-keeps-going-down` (`research_test_run_sites.md`): inventory of test run
  sites in the context of Postgres failures; ties full runs to the shared dev database load.
- `2026-11-08_12:35_sdd-improvements-combine-steps`: no test-tier decisions found in its spec.
- `spec_dd/0. maybe/better-finish-worktree-command/idea.md`: several worktrees finishing at once all
  run tests at once and crash for RAM. Out of scope of the efficiency spec; the user's remedy was a
  "ready to finish" marker and one main-side command.

## 2. Elsewhere: what teams report after adopting change-based test selection

- Google TAP. Presubmit runs tests "directly relevant" to the change; a periodic run of everything
  near HEAD catches what selection missed. Running everything before submission is not feasible.
  https://research.google/pubs/what-breaks-google/
  https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/
- Facebook predictive test selection (ICSE 2019). A learned model halves testing infrastructure cost
  while catching more than 95% of individual test failures and more than 99.9% of faulty changes, at
  about a third of the transitively dependent tests. The selection is a cost trade, not a guarantee.
  https://ar5iv.arxiv.org/html/1810.05286
  https://engineering.fb.com/developer-tools/predictive-test-selection/
- Nx affected. Maps files to projects through a project graph and runs only affected projects. A
  lockfile change marks everything affected "in case Nx misses a project"; touching a widely used
  project can still affect most of the workspace. This is the same shape as `uv.lock` and
  `pyproject.toml` escalating here, and it is why Q2's "dependency files still escalate" is standard.
  https://nx.dev/docs/features/ci-features/affected
- Datadog Test Impact Analysis. Documented skip-misses: library dependency changes, compiler options,
  external services and data files are invisible to coverage-based selection. The default branch is
  excluded so every test runs before production; a `ITR:NoSkip` commit-message override forces a full
  run for risky changes; the first enabled run skips nothing because coverage must be collected first;
  very large commits and very wide tests are not skipped; squash-merge loses the branch history that
  made earlier skips safe.
  https://docs.datadoghq.com/tests/test_impact_analysis/troubleshooting/
- pytest-testmon. Selects by executed code blocks via coverage.py; reliability is bounded by
  coverage.py; non-Python inputs (templates, data) are likely not tracked. Already rejected here for
  those reasons.
  https://testmon.org/blog/determining-affected-tests/
- Agent-loop reports (from this repo's earlier `research_known_complaints.md`): an eight-minute build
  with the full suite in nearly every agent round became the bottleneck; remedy is ordering checks by
  speed, targeted tests on the affected unit inside the loop, the full suite on merge or on a schedule
  or when build/CI config changes or the selector errors, and always running new and changed tests.
  https://devops.com/fast-code-slow-feedback-fixing-ci-for-the-age-of-ai-agents
  https://tianpan.co/forum/t/our-test-suite-became-the-bottleneck-moving-from-run-all-tests-to-intelligent-test-selection/3454
  https://julien.danjou.info/blog/your-ci-pipeline-wasnt-built-for-this/
- GitHub merge queue. Checks run on the combined state (target plus queued changes), so a local
  full run after a rebase is not the only verification.
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- Fowler, Continuous Integration. Local pre-push build is the fast commit build; slower suites run in
  a secondary build.
  https://martinfowler.com/articles/continuousIntegration.html

What the sources agree on:

- Selection saves large cost and misses a small, known class of inputs (dependency files, config,
  shared fixtures, templates, data). Every tool pairs selection with a failsafe: escalation globs, a
  periodic or branch-level full run, or a manual force-full override.
- The failsafe belongs at a gate (merge/CI/postsubmit), not at every local step. This repo already has
  the gate: CI on the PR.
- No source I found prescribes a full local run after every rebase. I found no source on the specific
  "ignore escalation inputs that came from an already-green main" rule; that is an inference (main
  passed CI, so only the branch/main interaction is unproven).
- Skipping needs a visible reason: the sources that work (Datadog, Nx) print what was skipped and why,
  which the selector's `why:` lines and the checkpoint's `why:` line already do.

## 3. Summary for the spec

- The tiers, the selector, the record and the checkpoint tier exist and work. The remaining full runs
  are not selector bugs; they are call sites and one design choice: (a) `finish_worktree` Step 1 always
  full, (b) main-originated escalation inflating rebase and checkpoint runs, (c) the one remaining
  unconditional full in `implement_plan` Step 3 (kept by Q3).
- The new work reverses two earlier decisions on purpose: "main's escalation forces full for the
  branch" and "Step 1 is always full". Edit those spec definitions explicitly.
- Keep: unknown means full, dependency files escalate, a skip is never reported as a pass, escalation
  is a glob list, generic plugins stay generic, CI is the backstop.
- Likely design pressure: the branch/main intersection needs the set of apps the branch touches and the
  apps main changed that those apps depend on, which `select_tests.py` can compute (it already builds
  importers from `docs/app_structure.md`). The record resolver in `sdd` should call the selector, not
  duplicate its rules.

status: ok
