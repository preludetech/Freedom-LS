# Research: known complaints about re-running only failed tests

Question: what goes wrong with `pytest --lf` style re-runs, and which of those pitfalls hit this
project's batches?

Versions checked: pytest 9.0.3, pytest-xdist 3.8.0, pytest-randomly 4.1.0 (`uv pip list`).
Mechanics below come from reading `_pytest/cacheprovider.py` in the project venv and from a
throwaway experiment in the scratchpad (a two-file suite run with `-p no:randomly -o addopts=""`).

## How `--lf` decides what to run (pytest 9.0.3, `_pytest/cacheprovider.py`)

- `cache/lastfailed` is a JSON dict of node ids in `<rootdir>/.pytest_cache`. An entry is removed
  only when that test runs and passes or is skipped (`pytest_runtest_logreport`, lines 354-358).
  A test that is not run in a session keeps its entry, true or stale.
- Selection (`pytest_collection_modifyitems`, lines 370-419) has three branches:
  1. Some collected item matches an entry: run only the matches ("rerun previous N failures").
  2. Entries exist but none match the collected items: run **every** selected item, reporting
     "N known failures not in selected tests" (lines 387-392).
  3. No entries at all: with the default `--lfnf=all`, run every item; with `--lfnf=none`,
     deselect all and exit 5 (lines 410-417).
- The cache is written once, in the controller's `pytest_sessionfinish` (lines 421-429), with a
  plain `path.open("w")` and no lock (`Cache.set`, lines 172-197). Workers never write it.

## Complaints and pitfalls, with what each means here

### 1. "No previously failed tests" silently runs everything
Default `--lfnf=all` turns an empty or missing cache into a full run. Experiment: empty
lastfailed + `--lf` printed `run-last-failure: no previously failed tests, not deselecting items`
and ran all tests. pytest documents this as intended
(https://docs.pytest.org/en/stable/how-to/cache.html, `--lfnf`).
Here: `test_tiers.md` lines 97-103 prescribe `uv run pytest --lf --no-cov` with no paths and no
`--lfnf`, so an empty cache turns the "failed only" re-run into a whole-suite run, the very cost
this spec removes. `--lfnf=none` instead exits 5 with nothing run (experiment: `exit=5`); the
runner reports a non-zero exit without a crash as `RESULT FAIL`
(`claude_plugins/django-stack/scripts/run_tests.py` lines 662-667), so an agent would see a
failure, not a false pass.

### 2. Stale entries (renamed, deleted, re-parametrised tests) also run everything
A renamed test's old node id never runs again, so it is never removed. Experiment: after renaming
`test_a` to `test_a_renamed`, lastfailed still held `test_x.py::test_a`; `--lf --lfnf=none`
printed `1 known failures not in selected tests` and ran the whole suite. `--lfnf` does not help,
because the dict is not empty (branch 2 above). The same holds when a fix renames the failing test
or changes a parametrize id: the new id is not in the cache, so the re-run either skips it (if
another entry matches) or runs everything (if none does). Node-id mismatches against the cache are
a long-standing xdist/pytest complaint (pytest-xdist issue #445,
https://github.com/pytest-dev/pytest-xdist/issues/445; pytest PR #5333 "Fix regression with --lf
and non-selected failures", https://github.com/pytest-dev/pytest/pull/5333).
Here: batch fixes routinely rename tests (review fix batches apply a test standard). Stale entries
accumulate in the feature worktree's `.pytest_cache` for the life of the branch.

### 3. Failures the cache never saw
- `-x` / `--maxfail`: later failing tests never run, so they are never recorded. Experiment with
  two failing tests and `-x`: only the first entered lastfailed.
- A killed controller (OOM kill of the pytest parent) never reaches `pytest_sessionfinish`, so
  that attempt's failures are not written. The runner's retry then runs only the unfinished tests
  (`run_tests.py` lines 627-631, `--ds-only-nodeids`, `ds_run_record.py` lines 34-46), so failures
  that finished in the killed attempt reach `run: summary (merged)` but not `cache/lastfailed`.
  A later `--lf` misses them (or, if nothing else is cached, runs everything, pitfall 1).
- Tests left unfinished after the last retry (`RESULT INCOMPLETE`) have no entry.
- An xdist worker that dies *between* tests has no crash item (`xdist/dsession.py`
  `worker_errordown`, lines 238-248), so nothing is recorded for it.
- Covered: a worker that dies *while running* a test gets a synthetic failed report
  (`dsession.py` `handle_crashitem`, lines 432-446), which reaches lastfailed. So the settled
  rule "a test that crashed its worker on every attempt still counts as failed" holds for `--lf`
  too, but only when the controller survived to write the cache.
- Collection errors are recorded by file id (experiment: `"test_z.py": true`), and `--lf` re-runs
  that module; fine, but the whole module re-runs, not one test.

### 4. One cache per rootdir, shared by every process in it
`.pytest_cache` sits at the rootdir (`pyproject.toml` lines 84-101 set no `cache_dir`;
`.gitignore` line 49). So:
- Each git worktree has its own cache (the rootdir differs), and a batch worktree under
  `.claude/worktrees/<name>` (`claude_plugins/sdd/commands/implement_plan.md` lines 70, 84) starts
  with none, since `.pytest_cache` is untracked. Cross-worktree leakage is not the risk.
- Inside one worktree the cache is shared. CLAUDE.md says several processes often work in the same
  worktree at once; a batch wave of one runs in the feature worktree (`implement_plan.md` line 76),
  alongside TDD single-test runs, `pytest --co` and any other agent's runs. Each session loads the
  dict at start and overwrites it whole at the end, so the last writer wins: a concurrent
  single-test GREEN run can erase the tier run's failures, or a RED run can add one. The write is
  not atomic, and a torn read yields an empty dict, which is pitfall 1 again.
- The integration targeted run (`implement_plan.md` line 88) runs in the feature worktree after
  cherry-picking; failures recorded inside the batch worktrees are gone with them, so a `--lf`
  there sees only the feature worktree's own history.

### 5. False confidence: passes in isolation, fails in the suite
The common complaint about failed-only reruns is that a test that failed because of another test
(shared state, ordering, load, a slow test timing out under parallel load) passes on its own.
Here pytest-randomly reorders every run and `--dist loadfile` (`pyproject.toml` line 92) groups
tests by module; a `--lf` run changes both the neighbours and the load. The idea itself notes
"under load the second run can fail on a different slow test". A green `--lf` proves the fixed
tests pass alone, not that the fix broke nothing else. This is why the idea keeps the whole-tier
gate at `implement_plan`'s final full run and the `finish_worktree` checkpoint, and why the
answers widen the re-run by the fix's own diff.

### 6. Coverage and addopts
`--lf` under `pytest-cov` fails a coverage threshold on the subset; the tier already passes
`--no-cov` (`test_tiers.md` line 100) and the runner adds it on retries (`run_tests.py`
lines 448-453). The `-m 'not ci_only ...'` addopts still apply, so a failure recorded under a
different marker selection is "not in selected tests" (pitfall 2).

## Implications for the spec

- Do not depend on `.pytest_cache` for the failed set. The runner already knows the failed node ids
  exactly, merged across attempts and including repeat crashers (`run_tests.py` lines 354-379,
  648-654); its record file survives a non-PASS run (lines 655-657). Printing the failed node ids
  in the verdict and re-running them by explicit node id avoids pitfalls 1-4.
- If `--lf` stays, add `--lfnf=none` so an empty cache fails loudly instead of running the suite,
  and accept that stale entries still trigger a full run.
- A renamed or re-parametrised failing test drops out of an id-based re-run; the fix diff widening
  in the answers (targeted selection of the files the fix changed) covers it.
- Keep the whole-tier gates as the backstop for order- and load-dependent failures.

## Sources

- pytest cache docs: https://docs.pytest.org/en/stable/how-to/cache.html
- pytest PR #5333, `--lf` with non-selected failures: https://github.com/pytest-dev/pytest/pull/5333
- pytest PR #10641, cache race between xdist workers (stepwise): https://github.com/pytest-dev/pytest/pull/10641
- pytest-xdist issue #445, cached node ids not matching collected tests: https://github.com/pytest-dev/pytest-xdist/issues/445
- pytest-xdist "When tests crash": https://pytest-xdist.readthedocs.io/en/stable/crash.html
- pytest-dev thread, other plugins breaking lastfailed recording: https://mail.python.org/archives/list/pytest-dev@python.org/thread/OZ6UCTGVJ76ARNJ5Z72UKSZRLPY5BB26/

status: ok
