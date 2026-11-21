# Research: UX patterns for a slow-test ranking

Audience: developers and Claude Code agents reading a terminal or markdown. Decisions already taken: committed ranking file, refreshed by hand with one command, report only (no failing limit).

## How pytest prints slow tests (the run output)

- `--durations=N` prints the N slowest phases at the end of the run; `--durations=0` prints all. `--durations-min=S` drops entries under S seconds. By default entries under 0.005s are hidden unless `-vv`. Source: https://docs.pytest.org/en/stable/how-to/usage.html
- Each line is `<time>s <phase> <nodeid>`, where phase is `setup`, `call` or `teardown`. So pytest already ranks per phase, not per test. (Format from pytest's terminal reporter; the usage page does not describe it.) A fixture-heavy test shows as a `setup` line separate from its `call` line, so a ranking built from this output must sum phases per node id to get "cost per test".
- Pattern: a short top-N printed every run (for example `--durations=20 --durations-min=1.0`) in `addopts` keeps the next slow test visible without a command. It adds output to every run, so for report-only use it is optional. The committed file is the durable ranking.

## Ranking file format

- Markdown table: readable in the terminal, in a PR and in an agent's context; diffs line by line. Best default for a human/agent audience. Columns that matter: rank, total seconds (setup+call+teardown), share of total, cumulative share, test id.
- JSON: best for tooling, worse to read; one-key-per-line pretty-printing with sorted keys diffs acceptably. CSV: compact and diffs per row, but no alignment and awkward in markdown viewers.
- Pattern fit here: one generated file, markdown, with the machine-readable detail only if a script needs it. Avoid two committed formats that can drift.
- Top-N vs full list: the idea says every test's duration is measured (19,507 tests). A full list is thousands of lines and churns on every refresh. Common pattern: commit the top N (for example 100-200) plus rollups, and keep the full per-test data uncommitted (generated, in `.gitignore` or a scratch dir). Cumulative share tells the reader where the top-N cutoff stops being useful.
- Rollups: per-app and per-file rollups answer "where is the time" faster than a test list, because count is a poor guide (1,400 shuffle cases under a minute). Put rollups first (small table, about 10-20 rows), then the top-N tests.
- Grouping parametrized cases: group by function (node id with `[...]` stripped) and show case count, total seconds and mean per case. Otherwise one parametrized test floods the top-N with near-identical rows and hides distinct slow tests. Show the single slowest case only when it is an outlier.
- Setup/call/teardown split: show the three as columns only for the top rows, or just a "setup share" column. It tells the developer whether to fix the test body or the fixture, which is the main follow-up action. Skip it for rollups.
- Cumulative share of total: one column ("top 50 = 38% of CPU time") is the single most useful number for deciding how far down to prune, and ties to the spec's CPU-time target.

## Diff-friendliness of a committed file

- Timings are noisy, so each refresh changes every row. Mitigations: round seconds (1 decimal, or 2 for sub-second), round shares to whole percent, sort by time then node id for stable tie order, one row per line, no timestamps in rows.
- Keep volatile metadata in a short header (date, commit, test count, total CPU seconds, machine note) so the noise stays in a few lines.
- Top-N plus rollups limits the diff to a bounded size; a full list would produce thousands of changed lines.
- Do not gate on the file in CI (report-only decision), so noise cannot break anything. A reader judges change by rank movement, not exact seconds.
- Use CPU time (as the spec target does) rather than wall time, and note whether the run was serial or `-n`, since parallel runs distort per-test times.

## Making the next slow test easy to spot

- Sort descending by cost; rank 1 first. Put the rollup and top-10 within the first screen of the file.
- Mark tests not yet reviewed or already pruned (a status column or a separate "done" section) so work goes down the list without rereading. Keep this optional; it adds hand-edited content to a generated file, which the refresh would overwrite. Better: the spec records pruned tests, the file stays purely generated.
- Full node ids, copy-pasteable into `pytest <id>` (use the function id for grouped rows).

## How docs tell a developer to refresh it

- Pattern: one fenced command in the testing skill (`claude_plugins/fls-dev/skills/testing/SKILL.md`, named in the idea's resources) under a "Refreshing the slow-test ranking" heading, with when to run it (after pruning work, or when the suite feels slower), the expected run time, and what the file contains.
- Wrap the multi-step process (run with durations, aggregate, write the file) in a single script or `pytest` plugin hook so the doc is one command. A single command with no flags avoids agents reconstructing arguments.
- The generated file should start with a "Generated by `<command>`; do not edit by hand" line, so anyone opening the file finds the refresh command.
- State that nothing fails on slowness; the existing 300s pytest-timeout is unchanged.

## Recommendation summary

- One generated markdown file: header (date, commit, count, total CPU), per-app/file rollup, top-N functions with parametrized cases grouped, columns for seconds, share, cumulative share and setup share.
- Full per-test data not committed.
- Optional `--durations` in `addopts` only if wanted; not required.
- Refresh command documented in the testing skill and in the file header.

Sources:
- https://docs.pytest.org/en/stable/how-to/usage.html

status: ok
