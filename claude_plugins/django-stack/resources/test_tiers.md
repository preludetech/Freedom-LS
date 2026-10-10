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
  its tier. An untracked file no rule knows is `none`; a tracked one is `full`. Read the `tier:` line: it is the tier that applies, and `none` means there is
  nothing to run. Then run the `command:` line exactly as printed. The `why:` lines are the
  selection's reasons; quote them when reporting. The generic `none` and escalation lists are the
  two glob tuples at the top of `${CLAUDE_PLUGIN_ROOT}/scripts/select_tests.py`; the project's own
  are in `[tool.test_tiers]` in `pyproject.toml`. The script applies them, so nobody applies them
  by hand. Done when every `why:` line is accounted for and the printed command exits zero.
- **full.** The whole suite, in parallel:

  ```
  uv run pytest -n auto
  ```

  plus `-m '<expression>'` when `[tool.test_tiers]` in `pyproject.toml` sets `markers`. That
  `-m` replaces the one in `addopts`, so tests the default run deselects still run in a tier.
  The wrapper prints the exact line for a `tier: full` result. Coverage and its threshold run
  wherever the project puts them: in `addopts`, or in CI only.

## How to run a tier

Run `targeted` and `full` with the Bash tool's `run_in_background: true` and wait for the completion
notification. Run one tier at a time per worktree. Run the bare command and let it finish; a full
run can take more than ten minutes. The one hard guardrail: no `ps` or `pgrep` polling loops and no
`timeout` wrapper.

## A single test run

The TDD RED and GREEN runs of one test:

```
uv run pytest <file>::<test> -x --no-cov
```

`--no-cov` makes the exit code mean pass or fail. In a project whose `addopts` turns coverage on,
any run smaller than the whole suite fails the coverage threshold, whatever the test did. The same
flag applies to `pytest --co` and to any other partial run.

## Reporting

Report the tier that ran as `tier: none|targeted|full` and quote the final pytest summary line. The
step is done when that line shows no failures.

## When a targeted run or full run fails

This section addresses the agent that owns the change, never a mechanic briefed only to run a tier.
Fix the failure, then re-run only the failures with `uv run pytest --lf --no-cov` (append `-n auto`
for a targeted or full run). Once that is green, re-run the whole tier as it first ran. The gate is
the whole tier, not the `--lf` subset.
