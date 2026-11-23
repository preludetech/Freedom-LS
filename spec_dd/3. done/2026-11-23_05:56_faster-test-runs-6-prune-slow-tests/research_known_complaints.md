# Research: known complaints about per-test durations and pruning slow tests

Question: what do developers commonly complain about when measuring per-test durations and pruning slow or redundant tests? Context: 19,507 tests, pytest + pytest-django + xdist + coverage, shared loaded dev machine.

Evidence level: the first group is web-sourced where a URL is given. The rest is general practitioner knowledge, not verified against a source in this pass, and marked "(experience)".

## Measuring

- **Noisy under load and xdist.** Wall-clock durations on a shared machine vary run to run, and xdist workers compete for CPU, so a test can look 2x slower for reasons unrelated to it. (experience)
  - Implication: take CPU time (user+sys) rather than wall time where possible. Compare several runs, or use a median.
  - Implication: rank by order of magnitude, and treat small differences as noise.
- **First test per worker absorbs DB setup.** pytest-django creates the test database on first need, with one database per xdist worker (suffixes `gw0`, `gw1`, ...). The first DB test on each worker therefore shows a large setup time. Source: https://pytest-django.readthedocs.io/en/latest/database.html
  - Implication: the spike appears once per worker, not once per run. Do not read it as a slow test.
- **Session or module fixture cost lands on whichever test triggers it first.** With xdist and `--dist load`, which test that is changes between runs, so the ranking is unstable. (experience)
  - Implication: record setup separately, and attribute shared-fixture cost to the fixture, not the test.
- **`--durations` mixes phases and truncates.** It reports setup, call and teardown as separate rows, and the default view hides sub-0.005s rows unless `-vv`. Use `--durations=0` to get all rows. Docs: https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration
  - Implication: a row labelled with a test name can be setup, not the test body. Group by phase.
- **Misattribution by autouse fixtures.** An example is an issue where `--durations` was distorted by a freezegun autouse fixture. Source: https://github.com/pytest-dev/pytest/issues/10245
- **Fixture-aware plugins exist.** `pytest-durations` separates fixture time from test time, subtracts wider-scope fixture cost, and supports xdist. Source: https://socket.dev/pypi/package/pytest-durations/overview/1.3.0
- **Coverage overhead skews timings.** Coverage tracing slows Python-heavy tests much more than DB- or IO-bound ones, so the ranking under coverage differs from the ranking without. (experience)
  - Implication: say which mode the ranking was taken in. Rank without coverage for speed work, and check coverage separately for the threshold.
- **xdist worker balance.** coverage.py's own test suite carries a custom xdist balancing plugin, a sign that the default distribution is a known issue for uneven tests. Source: https://fuchsia.googlesource.com/third_party/github.com/nedbat/coveragepy/+/1aefbfbc9aaba0a568d6e3cdc775658171cc4e9d/tests/balance_xdist_plugin.py
  - Implication: total CPU time is a steadier target than wall time.

## Keeping the ranking

- **Duration files go stale.** Committed duration data (for example `pytest-split`'s `.test_durations`) drifts as tests are added, renamed or changed. Unknown tests get an average guess, which skews the split. (experience)
- **Merge conflicts.** A large generated file that every PR touches conflicts constantly. Common mitigations are regenerating on a schedule rather than per PR, a stable sorted format with one entry per line, and never hand-merging (take either side and regenerate). (experience)
  - Implication for this spec: the answers settle on a hand-refreshed committed file. Keep it sorted, deterministic and rounded so diffs are small.
- **Timing values in a committed file churn on every refresh.** Round the values, or keep only the top N rows.

## Pruning

- **Deleted tests later turn out to guard regressions.** Line coverage says a line is hit, not that a behaviour is asserted. A removed test may be the only one with the assertion. (experience)
  - Implication: the "name the covering test" rule needs the covering test to assert the same thing, not merely execute the same lines. The coverage threshold alone does not prove this.
- **"Redundant" tests that differ subtly.** Near-duplicates often differ in one input, a permission edge, or a site or user setup. Parametrised cases that look identical can pin different bugs. (experience)
  - Implication: compare the inputs and assertions of the pair, and record the difference in the spec.
- **Merged tests make failures harder to read.** A merged test fails at its first assert, so later checks are masked. The failure message no longer names the one behaviour that broke. (experience)
  - Mitigation: keep distinct test ids through parametrisation, and use assertion messages or `subtests`.
- **Cheapest wins are usually in fixtures, not in deleting tests.** Ranking by cost per test finds heavy setup (factories, DB writes, password hashing) before it finds redundant tests. This matches the idea's own finding that test count is a poor guide.

## Time limits

- **Per-test thresholds flake.** A fixed limit passes on an idle machine and fails on a loaded one or under coverage. It also fails the first test per worker when DB setup is counted. (experience)
  - Implication: the answers choose report-only, which avoids this. Keep the existing 300s `pytest-timeout` as the only hard limit.

## Sources

- https://pytest-django.readthedocs.io/en/latest/database.html
- https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration
- https://github.com/pytest-dev/pytest/issues/10245
- https://socket.dev/pypi/package/pytest-durations/overview/1.3.0
- https://fuchsia.googlesource.com/third_party/github.com/nedbat/coveragepy/+/1aefbfbc9aaba0a568d6e3cdc775658171cc4e9d/tests/balance_xdist_plugin.py

status: ok
