# Answers: claude-ram-usage

Asked by `/sdd:start` before the spec was written.

- Q: What should the RAM work cover: test runs only, tests plus SDD fan-out, or everything the workflow spawns (dev servers and Playwright browsers too)? → A: Tests + SDD fan-out: gate pytest runs, and cap how many SDD batches or subagents start when RAM is low (asked up front)
- Q: Should the fix coordinate across worktrees with a machine-wide limit on concurrent heavy runs, or only check free RAM inside each run? → A: Per-run RAM check only: each run checks free RAM and waits or shrinks its own worker count, with no cross-worktree lock (asked up front)
- Q: When a run dies from an out-of-memory error (an xdist worker crash or OOM kill), how much should be retried automatically? → A: Retry crashed tests only: tell a worker crash apart from a test failure, back off, rerun only the tests that never finished with fewer workers, at most 2 retries, and never retry real failures (asked up front)
- Q: Where should the RAM thresholds (RAM per xdist worker, limits) come from, given the django-stack plugin stays generic? → A: Measured defaults + pyproject: the plugin ships defaults, the project overrides them in a `[tool.*]` table in pyproject.toml, and an env var overrides them per machine (asked up front)
- Q: Now that a crash reruns only the tests that never finished, should the suite still be split into checkpointed sections? → A: Drop sectioning; the crash-only rerun is the resume (asked up front)
- Q: If free RAM stays too low even for the minimum worker count, what should a run do after the maximum wait? → A: Run with 1 worker after the wait limit (e.g. 10 minutes) and say so in the output (asked up front)
