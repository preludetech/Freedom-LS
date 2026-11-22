# Prior art: running this repo's tests on GitHub Actions

## Here

### Current workflow (`.github/workflows/tests.yml`)
- Jobs: `lint`, `type-check`, `unit-tests` (15 min cap, `-n auto --cov --cov-fail-under=92`, then the
  panel_framework and icons standalone runs), `dev-tooling-tests` (10 min), `playwright-tests`
  (15 min, `playwright install --with-deps chromium`, `-n auto`, uploads `test-results/` on failure).
- Triggers: push to main and PRs to main only. There is no `workflow_dispatch`.
- `concurrency` cancels in-progress runs for the same ref. A second dispatch on one branch would
  cancel the first.
- Each job has its own Postgres service, so there is no database sharing between jobs.
- No suite splitting. No coverage combine step. Postgres is published on port 6543 and the Playwright
  job uses `POSTGRES_DB: test_db`, unlike the unit job's `db`.

### Timeline and what broke
- Last green run: 2026-10-10 (`spec_dd/1. next/faster-test-runs/research_test_timings.md`, "GitHub
  Actions on this repository"). That date matches the `testing-cleanup-junk` spec, which set the
  `-m "not playwright"` split and the coverage threshold
  (`spec_dd/3. done/2026-10-10_11:22_testing-cleanup-junk/2. plan.md` lines 161, 203, 876, 890).
- Since then: `unit-tests` is cancelled at the 15-minute cap, 45% of the way through 18,533 tests on
  4 workers with coverage. `playwright-tests` fails at `playwright install --with-deps chromium`
  because `ubuntu-latest` is Ubuntu 26.04 and Playwright 1.58.0 does not support it.
- Earlier caps: the unit job had `timeout-minutes: 10` and no `-n` in October
  (`research_test_suite_speed.md` section 4 in the done `testing-cleanup-junk` folder). That research
  could not see CI logs, so the run time was inferred, not measured. The earlier research's open
  question was whether coverage was the biggest cost. The SlipCover paper puts coverage.py overhead at
  a median of about 180%.
- Earlier splitting attempts in this repo: none found. The only split in the history is the unit and
  Playwright split, and later the `dev_tooling` marker.

### Recorded lessons
- Per-job setup is large: every pytest invocation spends 55 to 65s creating the test database
  (167 migrations), and each xdist worker repeats it. Splitting into N jobs times N workers
  multiplies that cost. `--no-migrations` brings it to about 3.9s (`research_test_timings.md`).
- Argon2 hashing is a large per-test cost; spec 1 (fast password hasher) targets it. Expect runner
  time to fall once that lands.
- Playwright tests are about 7s each plus DB setup; 220 of them.
- Collecting the suite takes 66s in one process, so each job that collects everything pays that.
- Marker expressions: a CLI `-m` replaces the `addopts` `-m`, so CI runs `ci_only` and `weasyprint`
  tests that the local tier deselects (`research_test_suite_speed.md`, `research_qa_helpers_and_tooling_tests.md`).
  A split must keep the marker expression in step with the local full tier.
- Claude cloud sessions are owned by spec 7, not this one.

### Working example in the First Class project (`/home/sheena/workspace/first_class/First-Class-LMS.git/main/.github/workflows/build-and-push.yml`)
- A six-group matrix of path lists, `fail-fast: false`, each group on its own runner with its own
  Postgres. About 3,100 tests there.
- Exhaustive by construction: a catch-all group collects the whole tree minus every path the other
  groups claim (`--ignore` and `--ignore-glob`), so a new app lands in the catch-all. The comment
  records collected counts that sum to the bare `pytest` count, a manual check that nothing is lost.
- Needs `-c pyproject.toml` so pytest picks the right rootdir and `addopts`.
- Pins `PYTEST_ADDOPTS` with `-v -ra --tb=long --showlocals --durations=10` and a fixed
  `--randomly-seed`, so a CI failure reproduces locally. The failing group's command can be copied
  verbatim.
- Repo-wide checks (`manage.py check`, `uv lock --check`) run in the smallest group with
  `!cancelled()`.
- Pinned `setup-uv@v10.0.1` because floating major tags stopped being published after v8.
- No coverage combine: the matrix groups there do not enforce a combined threshold. That would be new
  work for FLS (answers.md: combine and enforce 92%).

## Elsewhere

- Duration-based splitting with pytest-split (<https://github.com/posthog/pytest-split>): tests with
  no stored duration get the average, so a stale durations file is tolerated, but a project note
  reports about 7% cost from drift over weeks. Pest's time-based sharding behaves the same way: new
  files are spread evenly while known ones stay balanced. A rstest guide says shards should restore
  the duration cache read-only and a separate non-parallel job should write it, otherwise every run
  partitions cold. Another plugin (pytest-balance) writes per-node duration files and merges them
  afterwards to avoid write conflicts between parallel jobs.
  Sources: <https://python-rstest.readthedocs.io/en/stable/guides/sharding/>,
  <https://pypi.org/project/pytest-balance>,
  <https://laravel-news.com/time-based-sharding-in-pest-v4-6-0>.
- Matrix scope pitfall: a matrix with several axes makes one N-way split across all combinations
  unless index and total are set explicitly (<https://depot.dev/docs/ci/how-to-guides/split-tests>).
- Run-id race when a script starts a workflow and waits: `workflow_dispatch` historically returned no
  run id. Workarounds were a unique input echoed in `run-name` and polling recent runs; two
  near-simultaneous dispatches can pick the wrong run
  (<https://github.com/orgs/community/discussions/9752>). GitHub changed this on 2026-02-19: the
  dispatch API returns run IDs (<https://github.blog/changelog/2026-02-19-workflow-dispatch-api-now-returns-run-ids>),
  and `gh workflow run` prints the run URL from CLI v2.87.0. This is the fix to check the installed
  `gh` version against before using it.
- Not verified from sources in this pass: free-runner queue delays and shard flakiness reports. No
  authoritative figure was found, so treat the "5 to 8 minutes" in `idea.md` as a guess to measure
  once the matrix runs.

## Implications for the spec (not decisions)
- Reuse the First Class pattern (catch-all group plus path groups) to meet "a new app cannot be left
  out", or add a check that the union of groups equals the collected set.
- Per-job DB setup cost is the main risk to the 5-8 minute target; consider `--reuse-db` or
  `--no-migrations` for CI only if it stays faithful.
- Add `workflow_dispatch` and revisit `cancel-in-progress` so an SDD dispatch is not cancelled.
- Pin the Playwright runner to a supported image (for example `ubuntu-24.04`) or upgrade Playwright.
- Return failures to the agent through the run id from the dispatch response, then the failing
  group's log or the traces artifact.

status: ok
