# Research: reference implementations of failed-only re-runs and change-widened re-runs

Question: how do other tools re-run only the failed tests, and widen that run by changed files?
The tools covered are pytest `--lf` (with xdist), pytest-rerunfailures, pytest-testmon,
Bazel/Pants test caching, GitHub Actions "re-run failed jobs", and Jest `--onlyFailures` /
`--changedSince`. The findings are mapped onto this spec's three open questions, which
`answers.md` has now settled.

## What the project does today

- The tier definition's failure rule is at `claude_plugins/django-stack/resources/test_tiers.md:97-103`.
  It says: fix, re-run with `uv run pytest --lf --no-cov` (plus `-n auto`, behind
  `.claude/ds/scripts/run_tests.sh` when that is installed), then "re-run the whole tier as it first ran. The gate
  is the whole tier, not the `--lf` subset." This spec removes that last sentence for batches.
- Installed: pytest 9.0.3, pytest-xdist 3.8.0, pytest-randomly, pytest-timeout. Not installed:
  pytest-rerunfailures, pytest-testmon (`uv pip list`). `addopts` uses `--dist loadfile`
  (`pyproject.toml:89-92`).
- The runner `claude_plugins/django-stack/scripts/run_tests.py` already has an explicit node-id
  channel. When a crash retry happens, it writes the unfinished node ids to a file
  (`write_only_file`, :577-584) and passes `--ds-only-nodeids=<file>` (:448). The
  `ds_run_record` plugin then deselects everything else
  (`claude_plugins/django-stack/scripts/ds_run_record.py`, `pytest_collection_modifyitems`).
  The plugin also writes a per-test `outcome` event to a JSONL record. That record is
  deleted only on PASS (`run_tests.py:657-658`), and its path is printed as `run: record <path>`
  (:744). So after a FAIL, the failed node ids sit in a file the runner owns. One gap: a
  test counted as failed because it crashed its worker on every attempt is added to the
  in-memory `state.outcomes` only (:644-650). It is never written back to the record.
- The selector `claude_plugins/django-stack/scripts/select_tests.py` takes changed paths in three
  ways: positional paths, `--working-tree`, and `--range <rev>..<rev>` (:713-760). It composes
  `uv run pytest -n auto --no-cov <paths>` (:95, :683-700). `implement_plan.md:133` already runs
  a fix sub-agent's targeted run with `--range <sha before the fix>..HEAD`, which is the
  "widen by the fix's diff" input in another place.

## pytest `--lf` (cacheprovider), with xdist

Source: `.venv/lib/python3.13/site-packages/_pytest/cacheprovider.py` (pytest 9.0.3);
docs: https://docs.pytest.org/en/stable/how-to/cache.html

- **Failures are recorded per node id.** In `pytest_runtest_logreport` (:354-358), a passing
  `call` or a skip pops the id and a failure adds it. Collection errors are recorded at file
  level (:360-367). An xdist "worker crashed while running X" report is a failed report, so
  it also lands in `lastfailed`.
- **`--lf <paths>` does not form a union.** In `pytest_collection_modifyitems` (:370-419), if no
  known failure lies inside the selected paths, the status is "N known failures not in selected
  tests" and *every* selected item runs (:388-392). If some do, only those run and the rest of
  the paths are deselected (:395-397). So `pytest --lf <failed apps> <apps the fix touched>`
  cannot express "failures plus the fix's targeted selection". The answer in `answers.md`
  (widen by the fix's diff) needs the failed node ids passed as explicit arguments next to
  the selector's paths, or two invocations.
- **An empty cache runs everything.** `--lfnf` / `--last-failed-no-failures` defaults to `all`,
  which "runs all tests (the full test suite)" (docs; :410-417). A lost or emptied
  `lastfailed` therefore turns the "narrow" re-run into a silent full run of whatever paths
  were given (the whole suite when none were). `--lfnf=none` deselects all, and pytest exits
  5 (no tests ran), which the runner reports as `RESULT FAIL` (`verdict`, `run_tests.py:661-664`).
  That fails loudly, not falsely green.
- **The cache is shared and last writer wins.** `lastfailed` is read once at plugin init
  (:327) and written whole at `pytest_sessionfinish` by the controller only. Workers skip the
  write (`hasattr(config, "workerinput")`, :421-432). It lives in `<rootdir>/.pytest_cache`,
  so every pytest in a worktree shares it. CLAUDE.md says several processes often work
  in one worktree at once, and TDD single-test runs (`test_tiers.md:75-82`) also write it. A
  run that starts before a tier run ends and finishes after it overwrites the tier's failures
  with its stale copy. A batch's RED run also adds its own intentionally failing test. In
  either case `--lf` then re-runs the wrong set. Batch worktrees under `.claude/worktrees/` each
  have their own rootdir, which shrinks but does not remove this risk.
- **Speed.** With `--lf`, pytest also skips collecting files with no recorded failure
  (`LFPluginCollSkipfiles`, :301-311; `get_last_failed_paths`, :338-347). The re-run
  therefore costs about what its failed files cost, plus worker startup.
- **xdist.** `--lf` works under `-n`: workers read the same cache file during collection, and
  the controller writes it. The runner's own crash retries use `--ds-only-nodeids`, and
  deselected items do not touch `lastfailed`, so a retried crasher that then passes is popped.

## pytest-rerunfailures

https://github.com/pytest-dev/pytest-rerunfailures

- It re-runs a failing test *inside the same session*, up to `--reruns N` times, with optional
  `--reruns-delay`, `--only-rerun <regex>` and `--rerun-except`. A test that fails every attempt is
  reported failed. Fixtures that have already been set up stay cached at their scope. It is
  documented as incompatible with xdist's `--looponfail`. It recovers from hard crashes only
  under xdist ≥ 2.3.
- It exists to absorb flakes, with no code change between attempts. That is out of scope here
  (the idea defers flakes to the flaky test guide). It would also overlap with the runner's
  crash retry and blur its "crashed on every attempt counts as failed" rule
  (`test_tiers.md:56-58`). It is not a model for "fix, then re-run".

## pytest-testmon

https://testmon.org/

- Testmon records which code each test executed (via Coverage.py) in `.testmondata`. On the
  next run it selects tests whose recorded dependencies changed. "Testmon always re-executes tests
  which failed last time." This is the closest prior art to the settled answer: **last
  failures plus tests affected by the change, as one union**.
- Its documented limits: it over-selects on some edits (a renamed parameter widens to the
  module hierarchy), it does not track non-Python files or external services, and a varying test
  set exposes order dependencies between tests. It needs a full seeding run first. It is a
  coverage-based alternative to `select_tests.py`'s app-graph selection, and adopting it belongs
  to `faster-test-runs-8-narrower-targeted-tier`, not this spec.

## Bazel and Pants test caching

- **Bazel** (https://bazel.build/docs/user-manual): with `--cache_test_results=auto` (the
  default), Bazel re-runs a test only when the test or its dependencies changed, it is
  `external`, `--runs_per_test` asks for it, or "the test failed". A passed, unchanged test is
  served from cache. The unit is the test *target*. `--test_filter` narrows inside a target but
  still builds all targets. `--flaky_test_attempts` (max 10) is the flake mechanism, reported as
  `FLAKY`, and is kept apart from caching.
- **Pants** (https://www.pantsbuild.org/stable/docs/python/goals/test,
  https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection): each test file
  runs as its own process for "fine-grained caching". When a file changes, "only tests that
  depended on that changed file will need to rerun". `--force` bypasses the cache.
  `--changed-since=<rev>` with `--changed-dependents=direct|transitive` widens from changed files
  to their dependents. `[test].attempts_default` is a separate flake retry.
- **Pattern:** both tools get "failed plus affected by the change" for free, because the cache
  key is the inputs' hash and a failure is never a cache hit. Neither tool has a separate
  "only failures" mode. Correctness rests on hermetic, declared inputs. This project
  approximates that with `select_tests.py`'s app graph plus the whole-tier gates kept at
  `implement_plan`'s final run and the `finish_worktree` checkpoint.

## GitHub Actions "re-run failed jobs"

https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/re-running-workflows-and-jobs

- It re-runs the failed jobs "and the jobs that depend on them". Jobs that are not re-run keep
  their earlier outputs. The re-run uses "the same `GITHUB_SHA` … and `GITHUB_REF`". It is
  limited to 30 days and 50 re-runs per workflow run.
- The unit is a job, and the code cannot change between attempts. It is a flake/infra retry,
  not a fix-verify loop. Its one transferable idea is that the re-run widens by
  *dependents* of what failed. That matches the settled widening, which is the selector's
  importer/runtime closure (`select_tests.py:197-246`) applied to the fix's own diff.

## Jest `--onlyFailures` / `--changedSince`

https://jestjs.io/docs/cli

- `--onlyFailures` (`-f`): "Run tests that failed in the previous execution". It uses Jest's
  per-project results cache, which is pytest `--lf`'s equivalent.
- `--changedSince <branch|sha>`: "Runs tests related to the changes since the provided branch or
  commit hash". `--onlyChanged` (`-o`) uses uncommitted changes, and `--lastCommit` uses the last
  commit. All three need a static dependency graph. `--findRelatedTests <files>` runs the
  tests related to an explicit file list, the closest match to `select_tests.py <paths>`.
- Jest offers these as separate modes. The docs describe no union of failures and the
  change's related tests. Like pytest, a caller that wants the union composes it.

## Implications for this spec

1. **Widening by the fix's diff (settled: yes).** No reference tool composes "previous failures
   ∪ tests for the fix's diff" from `--lf` plus paths. pytest's own semantics forbid it
   (cacheprovider :388-397). Testmon and Bazel/Pants get the union only because a failure is
   never cached. The direct pytest form is one command that names the failed node ids
   *and* the selector's paths for the fix's diff. The diff comes from `select_tests.py --range
   <sha before the fix>..HEAD`, or `--working-tree` before the commit, the input
   `implement_plan.md:133` already uses. When the fix only touches the failing tests' own files, the
   selection adds nothing, and the run is just the failures.
2. **Where the failed set comes from.** `.pytest_cache/v/cache/lastfailed` is shared by every
   pytest in the worktree, last writer wins, and defaults to a full run when empty. The runner
   already keeps the failed run's outcomes in its record file after a FAIL and already has a
   node-id channel. The record lacks only the crash-counted failures (`run_tests.py:644-650`),
   and the settled rule "a test that crashed its worker on every attempt still counts as failed"
   needs them. If the spec stays with `--lf`, it should add `--lfnf=none` so that a lost cache
   fails loudly instead of quietly running everything.
3. **Flake retries stay separate.** Every reference tool keeps flake retries
   (rerunfailures, `--flaky_test_attempts`, `attempts_default`, GH re-run) apart from the
   fix-verify loop. This spec should not adopt pytest-rerunfailures. The runner's crash retry
   stays as it is.
4. **Whole-run gates elsewhere.** Bazel/Pants rely on hermetic inputs for safety. This project
   relies on the kept whole-tier gates: `implement_plan`'s final full run, the `finish_worktree`
   checkpoint, and a `full` rebase run that keeps its gate. Together these play the role of the
   cache-miss safety net.

status: ok
