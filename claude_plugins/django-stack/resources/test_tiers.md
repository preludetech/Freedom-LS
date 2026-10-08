# Test tiers

Before running pytest, name a tier (`none`, `targeted` or `full`) and follow this file. A step that
runs pytest names its tier; the flags live here and nowhere else.

## The tiers

- **none.** No pytest. The step reports `tier: none` and moves on.
- **targeted.** (written when the targeted wrapper exists)
- **full.** The whole suite, in parallel, with whatever `addopts` in `pyproject.toml` adds
  (coverage, the threshold, browser tests):

  ```
  uv run pytest -n auto
  ```

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

`--no-cov` makes the exit code mean pass or fail. With coverage on, any run smaller than the whole
suite fails the coverage threshold in `pyproject.toml`, whatever the test did. The same flag applies
to `pytest --co` and to any other partial run.

## Reporting

Report the tier that ran as `tier: none|targeted|full` and quote the final pytest summary line. The
step is done when that line shows no failures.

## When a targeted run or full run fails

This section addresses the agent that owns the change, never a mechanic briefed only to run a tier.
Fix the failure, then re-run only the failures with `uv run pytest --lf --no-cov` (append `-n auto`
for a targeted or full run). Once that is green, re-run the whole tier as it first ran. The gate is
the whole tier, not the `--lf` subset.
