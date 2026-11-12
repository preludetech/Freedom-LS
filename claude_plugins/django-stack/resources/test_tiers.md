# Test tiers

Before running pytest, name a tier (`none`, `targeted` or `full`) and follow this file. A step that
runs pytest names its tier; the flags live here and nowhere else.

## The tiers

- **none.** No pytest. The step reports `tier: none` and moves on.
- **targeted.** Run the wrapper with the step's diff:

  ```
  .claude/ds/scripts/select_tests.sh <diff arguments>
  ```

  The diff arguments are the step's own: `--working-tree` for uncommitted and untracked files,
  explicit paths, `--range <rev>..<rev>` (repeatable) for the files a git range changed, and
  `--tests-changed-in <rev>..<rev>` for test files that join a targeted run without ever raising
  its tier. An untracked file no rule knows is `none`; a tracked one is `full`. Read the `tier:` line:
  it is the tier that applies, and `none` means there is nothing to run. Then run the `command:` line exactly as printed. The `why:` lines are the
  selection's reasons; quote them when reporting. The generic `none` and escalation lists are the
  two glob tuples at the top of `${CLAUDE_PLUGIN_ROOT}/scripts/select_tests.py`; the project's own
  are in `[tool.test_tiers]` in `pyproject.toml`. The script applies them; never apply them by hand. Done when every `why:` line is accounted for and the printed command exits zero.
- **full.** The whole suite, in parallel:

  ```
  uv run pytest -n auto
  ```

  plus `-m '<expression>'` when `[tool.test_tiers]` in `pyproject.toml` sets `markers`. That
  `-m` replaces the one in `addopts`, so tests the default run deselects still run in a tier.
  The wrapper prints the exact line for a `tier: full` result. With the test runner installed,
  that line starts with `.claude/ds/scripts/run_tests.sh`; run it as printed. Coverage and its threshold run
  wherever the project puts them: in `addopts`, or in CI only.

## How to run a tier

Run `targeted` and `full` with the Bash tool's `run_in_background: true` and wait for the completion
notification. Run one tier at a time per worktree. Run the bare command and let it finish; a full
run can take more than ten minutes. A crash retry happens inside that one background run. The one hard guardrail: no `ps` or `pgrep` polling loops and no
`timeout` wrapper.

## Memory-aware runs

The test runner, `.claude/ds/scripts/run_tests.sh`, wraps one pytest command. It sizes the xdist
worker count to the memory that is free, and waits a bounded time when memory is short. It
retries a crashed pytest attempt for the tests that never finished. It prints one verdict.

Each setting comes from its environment variable, then from `[tool.test_tiers.memory]` in
`pyproject.toml`, then from the default. A wrong type or an unknown key exits 2 and names the key.

| Key | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `per_worker_mb` | `DS_TEST_PER_WORKER_MB` | 1024 | Memory one xdist worker needs |
| `reserve_mb` | `DS_TEST_RESERVE_MB` | 2048 | Memory left free for everything else |
| `max_workers` | `DS_TEST_MAX_WORKERS` | `os.cpu_count()` | Ceiling on `-n` |
| `psi_some_avg10_limit` | `DS_TEST_PSI_LIMIT` | 10.0 | Wait while `some avg10` in `/proc/pressure/memory` is above this |
| `wait_timeout_s` | `DS_TEST_WAIT_TIMEOUT_S` | 600 | Longest wait before running with 1 xdist worker |
| `max_retries` | `DS_TEST_MAX_RETRIES` | 2 | Crash retries after the first pytest attempt |
| `oom_score_adj` | `DS_TEST_OOM_SCORE_ADJ` | 500 | Set on the pytest child; 0 skips |

`DS_TEST_MEMORY_GUARD=off` runs the command unchanged: no gate, sizing, retry or extra lines.

## A single test run

The TDD RED and GREEN runs of one test:

```
uv run pytest <file>::<test> -x --no-cov
```

`--no-cov` makes the exit code mean pass or fail: in a project whose `addopts` turns coverage on,
any run smaller than the whole suite fails the coverage threshold whatever the test did. The same
flag applies to `pytest --co` and any other partial run.

## Reporting

Report the tier that ran as `tier: none|targeted|full`.

With the test runner, quote `run: summary (merged)` and `run: RESULT ...`, not pytest's own last
line. The step is done at `RESULT PASS`. `RESULT INCOMPLETE` means tests were left unfinished
after the retries: report it as blocked on memory, not as a failure to fix.

Without the runner, quote the final pytest summary line. The step is done when that line shows no
failures.

## When a targeted run or full run fails

This section addresses the agent that owns the change, never a mechanic briefed only to run a tier.
Fix the failure, then re-run only the failures with `uv run pytest --lf --no-cov` (append `-n auto`
for a targeted or full run). When the runner is installed, put `.claude/ds/scripts/run_tests.sh`
in front of that command. Once that is green, re-run the whole tier as it first ran. The gate is
the whole tier, not the `--lf` subset.
