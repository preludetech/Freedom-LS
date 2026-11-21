# Best practices: measuring per-test time and pruning slow tests

Written from the tools' documented behaviour. The URLs below are the documentation pages the claims come from; they were not re-fetched in this run, so verify flag names against the installed versions before the spec fixes a command.

## Measuring setup vs call vs teardown

- `pytest --durations=N` lists the N slowest phases, one row per phase (`setup`, `call`, `teardown`), not per test. `--durations=0` lists all. `--durations-min=S` (default 0.005s, and 0.005 hides rows unless `-vv`) sets the floor. Use `--durations=0 --durations-min=0` for a full ranking. <https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration>
- The per-phase split matters here: the research found `transaction=True` tests cost about 1s of teardown (flush) and database creation is 55-65s of session setup. Session database creation is outside any test's phases (it shows as the first test's setup, or as fixture setup of `django_db_setup`), so exclude or separate it or the first test per worker looks slow.
- JUnit XML (`--junitxml`): one `<testcase time=...>` per test, but `time` is the sum of setup + call + teardown, and the phases are not separate. Good for a single number per test, poor for splitting phases. Tuning: `junit_duration_report = call` makes it record call time only. <https://docs.pytest.org/en/stable/reference/reference.html#confval-junit_duration_report>
- pytest-json-report (`--json-report`) records `setup`, `call` and `teardown` durations per test in one JSON file, plus node ids, outcome and parametrize data. Works under xdist (the plugin merges worker output). Cost: another dependency. <https://github.com/numirias/pytest-json-report>
- A custom hook needs no dependency: in `conftest.py`, `pytest_runtest_logreport(report)` receives a `TestReport` per phase with `report.when`, `report.duration` and `report.nodeid`. Under xdist the controller receives the workers' reports, so a plugin that writes the file in `pytest_sessionfinish` on the controller (check `hasattr(config, "workerinput")` to skip workers) sees every test. Fits the "one command rewrites a committed file" decision, and lets the output be shaped (sorted CSV/JSON with a stable, diff-friendly format). <https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_logreport>
- Keep the hook limited to measuring (report only, no failing), matching the decision that nothing fails on slow tests.

## Measuring under xdist, load and noise

- Per-test durations under `-n auto` are wall times inflated by contention (CPU, Postgres, other worktrees on the same machine, as the research noted). Rankings are stable for large gaps and unreliable for small ones. Compare tests in orders of magnitude; do not chase 10-20% differences.
- Run the ranking with a fixed worker count (not `auto`) on a quiet machine, or run serially (`-n 0`) as the earlier research did. Serial is the cleanest but a full serial run of 19.5k tests is long; a fixed `-n 4` matches CI and cloud sessions (4 vCPU).
- Repeat the slowest slice 2-3 times and take the minimum (or median) per test before acting on it; the minimum is the least noisy estimate of intrinsic cost. Treat a one-off outlier as noise.
- Disable random ordering and coverage for the ranking run (the earlier research did both). Coverage adds a roughly constant multiplier (tracing overhead, often 1.3-3x, higher on line-heavy code), which distorts relative cost. Record that the ranking is without coverage and the target is stated on the same basis.
- `--dist loadgroup` / `loadscope` change which worker runs a test, not its cost, but cold caches on a worker's first tests inflate them. Ignore first-test-per-worker outliers.
- xdist docs: <https://pytest-xdist.readthedocs.io/en/stable/distribution.html>

## CPU time vs wall time

- Wall time includes waiting on Postgres, subprocesses and other processes' load; CPU time (`time.process_time()` / `resource.getrusage`) counts only this process. The idea's target is "the full run's CPU time", so sum CPU across workers: use `time` / `/usr/bin/time -v` (user + sys) on the whole command for the total, and the same value across repeated runs is far steadier than wall.
- Per-test CPU time of the pytest process excludes the Postgres server's CPU (a separate process), which is substantial for DB-heavy tests. For total-cost purposes either measure whole-machine CPU for the run, or accept per-test wall as the ranking key and use total CPU only for the target.
- A hook can capture both: record `time.process_time()` at `pytest_runtest_setup` start and `pytest_runtest_teardown` end (or in `pytest_runtest_protocol` wrapper) to store call-level CPU next to `report.duration`.
- `pytest-benchmark` and `pytest-profiling` exist but are for micro-benchmarks and call stacks; use `cProfile` / `pyinstrument` on single slow tests after ranking, not for the full run.

## Aggregating parametrized cases

- Node ids look like `path::test_fn[param-id]`. Strip the `[...]` suffix (split on the first `[`) to group cases under their test function, and sum, count and mean per group. The research showed why: one test with 1,400 cases at 0.04s is 56s, and one with 696 cases at 3.5s is over 40 minutes. Rank by total per function, then show per-case mean and case count.
- Parametrize ids can contain `::` or `[`; split the nodeid on `::` first, then on the first `[` of the last segment.
- Also aggregate by file and by app (path prefix) so the ranking shows which area dominates, and report the phase split (setup/call/teardown) per group, since shared-fixture fixes act on setup.

## Finding redundancy

- Coverage contexts: `coverage run`/`pytest --cov --cov-context=test` (pytest-cov) stores which test executed each line in the `.coverage` SQLite file (`coverage json --show-contexts`, or query the `context`/`line_bits` tables). Per test you get the set of lines covered; two tests are candidates when one's covered set is a subset of the other's. Docs: <https://coverage.readthedocs.io/en/latest/contexts.html> and <https://pytest-cov.readthedocs.io/en/latest/contexts.html>
- Caveats: line coverage subset is necessary, not sufficient, for redundancy. Two tests can hit the same lines and assert different behaviour (different inputs, branches within a line, different assertions). Treat it as a shortlist and have a person read both tests; the decision already requires naming the covering test. Branch coverage (`--cov-branch`) narrows false positives.
- Coverage contexts are heavy (large database, slower run). Run it once on a slice (the slowest N test functions from the ranking) rather than the full suite.
- Parametrized suites: many cases often cover identical lines; check whether the case varies a branch or a boundary. Pruning cases that exercise the same branch with the same equivalence class is the usual safe cut (equivalence partitioning plus boundary values).
- Mutation-style reasoning: ask whether a plausible bug would still be caught if this test were deleted. Practical version: delete or weaken the candidate, then run a mutation tool (mutmut, cosmic-ray) on the touched module, or hand-mutate (flip a condition, drop a filter) and see whether the named covering test fails. Full mutation testing on this size of suite is too slow; use it only on the specific module of a removal. <https://mutmut.readthedocs.io/>
- Duplicates in other forms: tests asserting framework behaviour (Django ORM, form field validation) rather than project code; tests that repeat an invariant already checked by a higher-level test; the same setup repeated with only a trivial assertion changed (merge into one test with several asserts if setup dominates).
- Safety net: the coverage threshold (already decided) plus running the full suite; compare per-file coverage before and after, not just the total, since a total can hide a local loss.

## Common speedups in Django/pytest-django tests

- Share expensive setup: `TestCase.setUpTestData` (Django) creates data once per class inside a class-level transaction and rolls back per test; the pytest equivalent is a class/module-scoped fixture requesting `django_db_blocker` and creating objects within `with django_db_blocker.unblock()`, or `django_db_setup`-dependent fixtures with explicit cleanup. Objects created in `setUpTestData` are deep-copied per test in Django 3.2+, so mutation is safe. <https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.setUpTestData>
- With pytest-django, ordinary function-scoped `db` tests wrap each test in a transaction rolled back after; module-scoped data needs the blocker approach or a `django_db_setup` override. <https://pytest-django.readthedocs.io/en/stable/database.html>
- Avoid `transaction=True`: it uses `TransactionTestCase` semantics, truncates tables on teardown (the research measured about 1s each) and cannot use rollback. Use it only for tests that need real commits (`on_commit` callbacks (consider `django_capture_on_commit_callbacks` instead), threads, select_for_update across connections). Replacing `transaction=True` where it was added out of habit is often the largest single-test saving. <https://pytest-django.readthedocs.io/en/stable/helpers.html#django-capture-on-commit-callbacks>
- Factory overuse: `factory_boy` `SubFactory` chains build the whole graph (site, user, cohort, course...) per test; use `build()` / `build_batch` when the DB isn't needed, pass existing related objects in, use `create_batch` with only the needed fields, and make traits cheap. The earlier research already showed the password hash dominated `UserFactory`; set an unusable or pre-hashed password where the password is not under test. <https://factoryboy.readthedocs.io/en/stable/recipes.html>
- Lower parametrize counts: collapse cartesian products (`@parametrize` stacked decorators multiply cases) into representative and boundary cases; use `pytest.param(..., marks=...)` for the few that are important; or assert all cases in one test loop when the setup cost per case is high and a failure message names the case (`subtests` / `pytest-subtests`). Trade-off: fewer node ids, less isolation.
- Move pure-logic tests off the DB: if a function takes values and returns values, test with plain objects or `build()`d unsaved instances, no `db` marker, so no transaction setup or queries. Missing `db` marker also lets xdist schedule them anywhere. Mock at the I/O boundary only.
- Avoid per-test heavy work: building clients and logging in with the password hasher (use `client.force_login`), rendering full pages when only context is checked, `call_command` in tests.
- Reduce session overhead (already identified by earlier specs): `--reuse-db`, `--no-migrations` or squashed migrations, a fast password hasher. These help every test and usually beat pruning per-test cost; check that the ranking excludes them.
- Playwright tests are out of scope.

## Setting a time target

- State the target on the same basis the ranking was measured: CPU time summed over workers, no coverage, fixed machine class, plus the measured baseline from the first full run.
- Derive it from the ranking, not from a guess: take the cumulative cost curve (sorted cost, running total). If the top K functions or files hold about X% of total, the achievable cut is bounded by what can be saved from them. Set the target as baseline minus realistic savings (for example, a stated fraction of the top-K cost), and keep a floor equal to the irreducible parts (database creation, collection).
- Report: baseline, target, result, and the list of changed tests with their saved cost. Report both CPU total and wall on a fixed worker count; wall depends on worker count and noise, CPU is the steadier comparison.
- Use a Pareto approach: the ranking is long-tailed, so stop when the next candidates each save less than review effort (a common cut-off is the point where the marginal test costs under about 0.5-1% of the target). The research's per-case numbers show the tail is the shuffle test (56s for 1,400 cases) and the permission matrix (other spec), so the worth-it region may be small.
- Keep the committed ranking a stable, sorted, diff-friendly file (function-level totals, case count, mean, phase split, with the date, commit and command in a header), as the answers decided; no failing time limit, report only, the existing 300s `pytest-timeout` stays.
- Beware measurement drift: after the run, refresh the ranking and compare function-level totals so a refactor that moved cost to setup is not counted as a saving.

status: ok
