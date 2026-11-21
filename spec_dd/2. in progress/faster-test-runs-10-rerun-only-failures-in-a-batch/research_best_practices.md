# Research: best practices for re-running only failed tests

Question: what are the established practices for re-running only the failed tests after a fix
(`--lf`, `--ff`, the lastfailed cache, xdist, crashed workers), compared with re-running the whole
suite, in CI and in local agent loops?

Versions checked in this worktree: pytest 9.0.3, pytest-xdist 3.8.0 (`uv run python -c ...`).

## 1. The common pattern: iterate narrow, gate wide once

- pytest's own docs present `--lf` and `--ff` as the edit-fix loop: run the failures, fix, then
  run everything. `--ff` ("failures first, then the rest") exists so the whole run still happens
  but feedback on the failures arrives first.
  https://docs.pytest.org/en/stable/how-to/cache.html
- At scale (Google TAP, Bazel/Buck test-impact pipelines, pytest-testmon), the same split shows
  up: pre-merge iteration runs the affected or failed subset, and one wide gate runs before the
  change lands. Nobody runs the wide gate after every fix inside an iteration loop.
  https://testmon.org/ , https://bazel.build/docs/user-manual#test
- GitHub Actions and GitLab both offer "re-run failed jobs" as a separate action from re-running
  the pipeline. That is job-level, not test-level, but it follows the same idea: re-run what
  failed, and keep the full run as a distinct, deliberate gate.
  https://docs.github.com/en/actions/managing-workflow-runs/re-running-workflows-and-jobs
- What the established practice adds to a failed-only re-run is **widening by the fix's own
  diff**. Test-impact tools re-select tests from the changed files, not only from the failure
  list. That is what answer 1 settled: failed tests plus the targeted selection for the files the
  fix changed. The spec's settled design matches the common pattern: failed-only (plus the fix
  diff) inside a batch, whole tier at `implement_plan`'s final run and at the `finish_worktree`
  checkpoint.

## 2. How `--lf` actually behaves (pytest 9 source)

Source: `_pytest/cacheprovider.py` in the project venv, `LFPlugin`, lines 354-430.

- **The cache is cumulative, not "the last run's failures".** `pytest_runtest_logreport` (l.354)
  removes a node id when it passes or skips and adds it when it fails. Tests a run did not select
  keep their old entry. `pytest_sessionfinish` (l.421) writes the merged dict. So after a narrow
  run, `cache/lastfailed` still holds failures from any earlier, wider run in the same rootdir
  that were never re-run. `--lf` with no path arguments re-runs all of them.
- **Silent fallback to everything, case A: empty cache.** With no recorded failures,
  `--lfnf`/`--last-failed-no-failures` defaults to `all` and runs the whole selection (l.410-417).
  `--lfnf none` deselects everything and exits 0 instead.
- **Silent fallback to everything, case B: failures outside the selection.** When the cache has
  failures but none of them are in the collected, marker-filtered items, the status line reads
  "N known failures not in selected tests" and **no item is deselected** (l.388-393): the whole
  selection runs. `--lfnf none` does not cover this case. The hook is a `tryfirst` wrapper whose
  code runs after `yield`, so `-m` deselection has already happened when it checks.
- **Collection errors are recorded** under the module's node id (`pytest_collectreport`, l.360),
  and `--lf` re-collects that module, so an import error fixed by the batch is re-checked.
- **Writes happen only at session finish.** A controller killed before `pytest_sessionfinish`
  leaves the cache from the previous run, so stale entries remain.
- **Under xdist**, workers collect and filter with `--lf` themselves (they read the same cache
  dir), and only the controller writes (`hasattr(config, "workerinput")` guard, l.423). `--lf`
  and `-n` combine safely.

## 3. Crashed workers

- xdist reports a test whose worker died as a failed `TestReport` ("worker 'gwN' crashed while
  running ...", `xdist/dsession.py` `handle_crashitem`, l.432-441). That report goes through
  `LFPlugin.pytest_runtest_logreport`, so a crashed test **lands in `cache/lastfailed`** like any
  failure. https://pytest-xdist.readthedocs.io/en/stable/crash.html
- The runner (`claude_plugins/django-stack/scripts/run_tests.py`) passes `--max-worker-restart=0`
  (l.445), then retries only the unfinished tests with `--ds-only-nodeids` (l.447-448, 600-643).
  A test that crashed in an early attempt and passed in a later one is popped from the cache by
  that later attempt. A test that crashed in every attempt (two or more) is counted as failed by
  the runner (`crashed_every_attempt`, l.368-381; l.646-652) and xdist has recorded it as failed
  in each attempt. So the settled rule ("crashed on every attempt still counts as failed") and
  the cache agree, and `--lf` picks it up.
- Risk: if the final attempt's controller is killed (`RESULT INCOMPLETE`, l.669-670), the cache
  was not written by that attempt. `test_tiers.md` l.90-91 already says INCOMPLETE is "blocked on
  memory, not a failure to fix", so no failed-only re-run should follow it. The spec should
  say a failed-only re-run follows `RESULT FAIL` only.

## 4. Hazards in the current rule in this repo

`claude_plugins/django-stack/resources/test_tiers.md` l.97-103 tells the agent to re-run with
`uv run pytest --lf --no-cov` (plus `-n auto`), then the whole tier.

1. **Marker mismatch hides failures.** Tiers run with `-m 'not ci_only and not weasyprint'`
   (`pyproject.toml` `[tool.test_tiers] markers`, l.125-128), while the bare `--lf` command
   inherits `addopts`' `-m '... and not dev_tooling'` (`pyproject.toml` l.92). A failing
   `dev_tooling` test (for example
   `freedom_ls/qa_helpers/tests/test_qa_create_report_fixtures.py` l.28, plus everything under
   `tests/` that tests plugin scripts) is deselected on the re-run. If it was the only failure,
   case B in section 2 applies and the re-run becomes the whole default-marker suite. If other
   failures were in the cache too, the `dev_tooling` one drops out silently and the re-run goes
   green without it. Today the follow-up whole-tier run catches this. Once the spec removes that
   run, the re-run must carry the tier's `-m` expression.
2. **Stale entries widen the re-run.** Because the cache is cumulative (section 2), an earlier
   full or wider run in the same worktree leaves failures that a later targeted run never
   touched. The failed-only re-run then runs them too and can fail on something the batch never
   changed. Batch worktrees in a parallel wave are fresh (`.claude/worktrees/...`,
   `implement_plan.md` l.84), but a wave of one, a fix batch and the integration run all share
   the feature worktree's `.pytest_cache` (`.gitignore` l.49), across batches.
3. **Silent fallback to a full run** (section 2, cases A and B) costs the time the spec is meant
   to save and reports a "PASS" that was not the re-run anyone intended.
4. **Order-dependent failures may not reproduce.** pytest-randomly (`pyproject.toml` l.68)
   reshuffles and reseeds each run. A failure that depends on order or shared state can pass on
   a narrow re-run. `-p randomly --randomly-seed=last` reuses the seed, but the order in a
   narrow run differs anyway. Flaky tests are out of scope; `implement_plan`'s final full run is
   the backstop.

## 5. Recommended shape for the spec

Drawn from the above; for the spec author to accept or reject.

- **Re-run by explicit node ids from the failed run, not by bare `--lf`.** The runner already
  merges per-test outcomes across attempts (`RunState.outcomes`, crash-every-attempt promoted to
  `failed`, l.646-650). Listing the failed node ids gives exactly the failed set: no stale
  entries, no marker filter, no fallback to everything. Common CI practice does the same: parse
  JUnit XML or a report for failed ids, then re-run those. If `--lf` is kept, use it with
  `--lfnf none`, the tier's own `-m` expression and the tier's own path arguments, and accept that
  stale entries can still widen it.
- **Widen by the fix's diff** (answer 1): add the targeted selection for the fix's files
  (`select_tests.sh --working-tree` or `--range <before-fix>..HEAD`). A fix that touches an
  escalation path (`pyproject.toml` `[tool.test_tiers] escalation`) then escalates to `full` by
  the existing rules, which is the right outcome.
- **Apply it to `RESULT FAIL` only**, never to `RESULT INCOMPLETE` (memory) or to a pytest that
  exited before its session started (usage or conftest import error). The import error is better
  re-run as the original tier, since nothing ran.
- **Size xdist to the re-run.** With 46 of 79 failed runs at three or fewer failures, a narrow
  re-run that starts four workers, each building a test database, can cost more in setup than in
  tests. `--dist loadfile` also puts one file's failures on one worker. The runner already treats
  `-n` as a ceiling; the rule could leave `-n` off below a small count.
- **Keep one wide gate.** `implement_plan`'s final `full` and the `finish_worktree` checkpoint
  are the established "gate wide once" step. `--ff` on those runs would get feedback on known
  failures sooner without narrowing the gate, but it is optional.

status: ok
