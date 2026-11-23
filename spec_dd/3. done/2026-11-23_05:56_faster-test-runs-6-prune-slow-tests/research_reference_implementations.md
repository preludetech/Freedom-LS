# Research: reference implementations for a committed per-test duration ranking

Question: how do other tools record a per-test duration ranking and keep it current, and how do large projects prune slow tests? Scope for FLS: a committed file, refreshed by hand with one command, report-only.

## pytest-split (closest match: committed duration file)
- File: `.test_durations`, default path in the working directory, changed with `--durations-path`. README says it "should be stored in the repo".
- Format (from `plugin.py`): JSON object, key = pytest `nodeid` string as reported (so parametrized ids are kept verbatim, e.g. `path::test[param]`), value = float seconds, unrounded. Written with `json.dump(sort_keys=True, indent=4)`: sorted keys give stable, diff-friendly commits. Old list-of-lists format is converted on load.
- Duration per key = sum of the setup + call + teardown reports for that nodeid. Negative durations are skipped. Setup/teardown above 600s are skipped (freezegun workaround).
- Refresh: `pytest --store-durations` on a complete run. Without `--clean-durations` it loads the old file and overwrites only the keys run this session (keeps keys not run, so deleted tests linger). `--clean-durations` discards the old content and writes only this run's tests.
- Unknown tests are assigned the average of stored durations, so the file need not be refreshed on every change. README advises re-running after major suite changes.
- `slowest-tests` CLI command lists the slowest tests from the stored file: a ready-made "ranking view" over the JSON.
- xdist: README names xdist only as an alternative. The writer reads `terminalreporter.stats` at session finish, with no xdist-specific code visible. Under xdist the controller's terminal reporter receives the workers' reports, so that likely works, but I did not verify it.
- Sources: https://github.com/jerry-git/pytest-split , https://raw.githubusercontent.com/jerry-git/pytest-split/master/src/pytest_split/plugin.py

## pytest `--durations` (built in)
- `runner.py`: `pytest_terminal_summary` gathers every report in `terminalreporter.stats` that has a `duration`, sorts descending, prints `{duration:02.2f}s {when} {nodeid}`. Setup, call and teardown are separate rows (not summed), so fixture cost shows up separately from test body.
- `--durations=N` (0 = all). `--durations-min` hides entries under a threshold (default 0.005s, 0 with `-vv`).
- Report-only, nothing persisted. xdist: the controller aggregates the workers' reports, so the output covers the whole run (xdist not covered in the file I read).
- Source: https://raw.githubusercontent.com/pytest-dev/pytest/main/src/_pytest/runner.py

## Django test runner
- `manage.py test --timing` (database setup and total time) and `--durations N` (N slowest test cases, 0 = all). Report-only, console output, no stored file.
- Docs do not say how `--durations` behaves under `--parallel`. Parallelism is per test class, one DB per process. Not applicable directly: FLS uses pytest.
- Source: https://docs.djangoproject.com/en/stable/ref/django-admin/

## Knapsack (Ruby, GitLab-style rspec splitting)
- File: `knapsack_rspec_report.json`, committed. Granularity is per test file, not per example. Path via `KNAPSACK_REPORT_PATH`.
- Refresh: `KNAPSACK_GENERATE_REPORT=true bundle exec rspec spec` on one CI node (local timings differ from CI), then copy the JSON and commit it by hand.
- Missing files ("leftovers") are distributed by name. Entries for removed files are ignored. Regenerate only after many new or changed slow tests, prompted by a time-offset warning at the end of a run.
- The format is not described on the README page I fetched.
- Source: https://github.com/KnapsackPro/knapsack (README)

## GitLab
- Docs point to rspec `--profile` (top 10 slowest examples) and an "Unhealthy tests" page for the slow-test process. The truncated fetch did not confirm their slow-test report mechanics. Treat as unverified.
- Source: https://docs.gitlab.com/development/testing_guide/best_practices/

## Not verified (no fetch done)
- pytest-test-groups, pytest-timer, pytest-profiling, Sentry, Zulip, Saleor and Wagtail slow-test practice. I recall that none of them commits a per-test ranking. Treat this as unconfirmed memory, not a finding.

## Takeaways for the FLS spec
- Precedent for a committed, hand-refreshed duration file exists in pytest-split and Knapsack. Both refresh by one flag on a full run and commit the result.
- Design choices to copy from pytest-split: key by full nodeid (parametrized ids preserved), sum setup+call+teardown or store them separately, `sort_keys` JSON for clean diffs, a `--clean-durations` equivalent so deleted tests drop out, and a small "slowest N" view of the file.
- Design choice to decide: per-test cost for a 1,400-case parametrized test is high in count but low in total, so the ranking should also aggregate by test function (nodeid with `[...]` stripped) and by file.
- Per-file (Knapsack) versus per-nodeid (pytest-split): per-nodeid is needed here because the aim is test-by-test pruning.
- All the tools above are report-only except for splitting. None fail a test on slowness beyond a pytest-timeout style limit, which matches the "report only" answer.
- Checks needed in the spec: confirm under xdist that the report stats include worker results, and which of `--durations=0` output or a small conftest plugin writes the file. A pytest-split dependency could be reused only with `--store-durations`, but it adds splitting plugin behaviour the project does not need.

status: ok
