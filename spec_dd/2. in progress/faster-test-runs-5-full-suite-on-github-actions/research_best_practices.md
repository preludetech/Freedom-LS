# Research: best practices for splitting the suite across GitHub Actions jobs

Written from established knowledge of the tools (no live fetch this run); verify version-specific details against the cited docs before the spec pins them.

## 1. Splitting: pytest-split vs path/marker matrices

- pytest-split (<https://github.com/jerry-git/pytest-split>, also mirrored at posthog/pytest-split): `pytest --splits N --group K --durations-path .test_durations`. Generate the file with `pytest --store-durations --durations-path .test_durations` (a full run). Split strategies: `duration_based_chunks` (default; contiguous chunks) or `least_duration` (balanced greedy; better balance, tests not contiguous). Pass `--splitting-algorithm least_duration`.
- Every test runs exactly once: pytest-split partitions the collected item list deterministically, so the union of groups 1..N is the full collection, provided all jobs collect the same set (same deselect/marker flags, same plugins, same ordering seed). New tests absent from the durations file get the average duration and are still assigned, so a new app can never be left out. This is the main advantage over a path matrix, where a new app/dir missing from the matrix is silently never run.
- Guard for "exactly once": add a cheap check job that runs `pytest --collect-only -q` and compares the count to the sum of per-group counts (each group can print its count via `--junitxml` totals). Fail if sum != total. With xdist inside a job, pytest-split still works (it splits at collection; xdist then distributes within the group). Don't use `pytest-randomly`/random ordering differing between jobs.
- Keeping durations fresh: commit `.test_durations` and refresh periodically (scheduled workflow or manual `workflow_dispatch` job that runs `--store-durations` and opens a PR), or have each CI run upload its durations and a periodic job merges them. Stale durations only hurt balance, not correctness. With xdist, `--store-durations` under `-n` can give incomplete/odd results; generate with `-n0` or accept the merge behaviour (`--clean-durations` to drop removed tests).
- Path/marker matrices: simple and readable, but need manual upkeep and a "rest" catch-all job (e.g. `--ignore` of every named dir) to guarantee coverage of everything; imbalanced. Playwright tests are better split off by marker/dir as its own job (needs browsers) and not part of the pytest-split pool, or split with a separate pytest-split pool.
- Matrix shape: `strategy: { fail-fast: false, matrix: { group: [1,2,3,4,5,6] } }`; the number of groups is the single knob, and `--splits ${{ strategy.job-total }}` keeps it consistent.

## 2. Combining coverage across jobs

- Each job: `coverage run`/`pytest --cov` with `COVERAGE_FILE=.coverage.${{ matrix.group }}` (or `--cov-append` off, parallel mode `[tool.coverage.run] parallel = true`), then `actions/upload-artifact@v4` with a unique name per job (`coverage-${{ matrix.group }}`); v4 artifacts are immutable and names must be unique per run. Hidden files: set `include-hidden-files: true` (v4.4+ excludes dotfiles by default, which silently drops `.coverage.*`).
- Combine job (`needs: [tests]`, `if: always()` or success only): `actions/download-artifact@v4` with `pattern: coverage-*` and `merge-multiple: true`, then `coverage combine`, `coverage report --fail-under=92` (or `[tool.coverage.report] fail_under = 92`), optionally `coverage xml`/html upload.
- Paths: set `[tool.coverage.run] relative_files = true` so data files hold relative paths, and add `[tool.coverage.paths]` mapping if jobs run in different checkouts/containers. Without this `combine` reports "No source for code" or double-counts. Same source tree and commit across jobs avoids most issues.
- The threshold must be enforced only in the combine job; per-job `--cov-fail-under` must be off (each group sees only a slice). Playwright/e2e coverage can be included by the same mechanism or excluded deliberately.
- Docs: <https://coverage.readthedocs.io/en/latest/config.html#config-run-relative-files>, <https://coverage.readthedocs.io/en/latest/cmd.html#cmd-combine>, <https://github.com/actions/upload-artifact>, <https://github.com/actions/download-artifact>, <https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md>.

## 3. Timeouts and free-runner limits

- Public repo, standard runners: free and unlimited minutes. `ubuntu-latest` public-repo runner: 4 vCPU, 16 GB RAM, 14 GB SSD (private repos: 2 vCPU/7 GB). Source: <https://docs.github.com/en/actions/using-github-hosted-runners/using-github-hosted-runners/about-github-hosted-runners#standard-github-hosted-runners-for-public-repositories>.
- Concurrency: Free plan 20 concurrent jobs across the account (5 macOS); so a 6-8 job matrix plus others is fine, but a second concurrent run (e.g. PR plus on-demand) queues. Source: <https://docs.github.com/en/actions/administering-github-actions/usage-limits-billing-and-administration>.
- Job execution limit 6 hours (default `timeout-minutes` 360); always set explicit `timeout-minutes` per job (e.g. 15-20) so a hang fails fast. The existing 15-minute cap failing at under half-way is a symptom of an unsplit suite. Workflow run limit 35 days; matrix max 256 jobs.
- A Postgres service container (`services: postgres: image: postgres:17` with health-check options) per job; each matrix job gets its own, so no DB collisions. xdist with `-n auto` uses 4 CPUs on public runners.

## 4. Caching

- uv: `astral-sh/setup-uv` with `enable-cache: true` and `cache-dependency-glob: uv.lock` (<https://docs.astral.sh/uv/guides/integration/github/>). Use `uv sync --locked`.
- npm/Tailwind: `actions/setup-node` with `cache: npm`; or cache `~/.npm` keyed on `package-lock.json`. Build Tailwind once in one job and pass as artifact if build is slow; usually fast enough to run per job.
- Playwright browsers: cache `~/.cache/ms-playwright` keyed on OS + Playwright version (`uv run playwright --version`); on cache hit run `playwright install-deps` only (system libs are not cached), on miss `playwright install --with-deps chromium`. Only install the browser actually used (chromium). Docs: <https://playwright.dev/python/docs/ci#github-actions>. (Playwright docs themselves note caching browsers is often not worth it because the download is similar in speed to restore; measure.) Only the Playwright job needs it.

## 5. Playwright on new Ubuntu images

Problem: `ubuntu-latest` has moved to 26.04 (per the task brief) and Playwright 1.58's `install --with-deps` doesn't know that distro (apt package names changed, e.g. t64 renames, fonts). Options, best first:
1. Pin `runs-on: ubuntu-24.04` for the Playwright job (and arguably all jobs, for reproducibility). Cheapest, officially supported platform for Playwright (Ubuntu 22.04/24.04). Downside: the pinned image eventually gets deprecated (GitHub supports roughly two LTS images), so schedule a revisit.
2. Upgrade Playwright to a release that lists Ubuntu 26.04 support (check release notes: <https://playwright.dev/python/docs/intro#system-requirements>, <https://github.com/microsoft/playwright-python/releases>). Needs a lockfile bump and a local re-run of the e2e tier.
3. Run the job in the official container `mcr.microsoft.com/playwright/python:v<version>-noble` (`container:` key) with a version matching the installed package exactly; browsers are preinstalled, no install step, no apt dependence. Postgres service then reached by service hostname rather than localhost, and needs `--ipc=host`/`--user pwuser` considerations per the docs (<https://playwright.dev/python/docs/docker>). More moving parts (uv inside the container).
Recommendation: pin ubuntu-24.04 now for the browser job; only pinned jobs avoid surprise image drift. Don't pin using `latest` anywhere you depend on system packages.

## 6. Triggering on demand and reading results

- Workflow needs `on: workflow_dispatch:` (optionally with inputs). `gh workflow run tests.yml --ref <branch>`. The workflow file must exist on the default branch for dispatch from the CLI to be discoverable (the `--ref` branch's version of the file is what runs, but the workflow must be registered).
- Run id: historically `gh workflow run` printed nothing and `workflow_dispatch` API returned 204 with no body, hence the race. GitHub changed the API in early 2026 so the dispatch endpoint can return the run id (`return_run_details`) and newer `gh` prints the run URL; verify against current docs/`gh --version` (<https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event>, <https://cli.github.com/manual/gh_workflow_run>). Fallbacks if unavailable:
  - Record a timestamp before dispatch, then poll `gh run list --workflow tests.yml --branch <b> --event workflow_dispatch --json databaseId,headSha,createdAt,status --limit 10` and pick the run whose `headSha` equals the commit under test and `createdAt` >= the timestamp (`gh run list --commit <sha>` also filters by sha). Retry for ~30-60 s.
  - Robust alternative: pass a unique correlation id as a workflow input (e.g. `run_tag=<uuid>`), and set `run-name: tests ${{ inputs.run_tag }}` in the workflow; then match on `displayTitle`. This eliminates the race even with several dispatches on the same sha.
- Wait: `gh run watch <id> --exit-status` (blocks, exit non-zero on failure; `--interval` for polling; uses API quota, so a 10-20 s interval). Alternatively poll `gh run view <id> --json status,conclusion`. Put an outer timeout in the script and treat "queued for N minutes" as a distinct outcome from failure (unreachable/slow handling).
- Failure output: `gh run view <id> --log-failed` gives the log for failed steps only (large with 18k tests; pytest `-q` and `-rf` with a short traceback keeps it readable). Better: each test job writes `--junitxml=junit-${{ matrix.group }}.xml` and uploads with `if: always()` as artifact `junit-<group>`; the script runs `gh run download <id> --pattern 'junit-*' --dir <tmp>` and parses `<testcase>` elements with `<failure>/<error>` for test ids and messages. Also `$GITHUB_STEP_SUMMARY` can list failed ids for humans. Also the commit sha tested is in `headSha`, which is what a full-run record needs.
- Check the artifact upload step uses `if: always()` and that cancelled/timed-out jobs yield no XML (handle by falling back to `--log-failed`).
- Auth: `gh` needs a token with `actions` write; `GH_TOKEN` env in non-interactive use. Branch must be pushed first (run tests the pushed commit, not the working tree); compare `headSha` to local HEAD.

## 7. Concurrency groups vs on-demand runs

- A `concurrency: group: tests-${{ github.ref }}, cancel-in-progress: true` is good for PR pushes (cancels superseded runs) but would cancel an on-demand run for the same ref on a new push, and an on-demand run could cancel a PR run. Use a group that distinguishes the event: `group: tests-${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}` with `cancel-in-progress: ${{ github.event_name != 'workflow_dispatch' }}`, or include the run_tag input so dispatches never cancel each other. Never cancel runs on main pushes (use `cancel-in-progress: false` or `github.ref != 'refs/heads/main'`).
- Docs: <https://docs.github.com/en/actions/using-jobs/using-concurrency>.
- With the 20-job account cap, parallel on-demand runs from several worktrees each using ~8 jobs will queue; keep matrix size moderate (4-8 groups) and consider the queue wait as part of the timeout/fallback design.

## 8. Other practices worth noting

- `fail-fast: false` on the split matrix so all failures show in one run.
- A final "gate" job (`needs: [tests, coverage]`, `if: always()`) giving a single required status check name, so branch protection doesn't depend on matrix job names.
- Keep one definition of the pytest invocation (a script or `uv run` task) shared by local and CI to avoid drift.
- DB: `--reuse-db` is pointless in CI; use `--create-db` with xdist's per-worker DBs.

## Sources

- <https://github.com/jerry-git/pytest-split>, <https://github.com/posthog/pytest-split>
- <https://coverage.readthedocs.io/en/latest/cmd.html#cmd-combine>
- <https://github.com/actions/upload-artifact>, <https://github.com/actions/download-artifact>
- <https://docs.github.com/en/actions/using-github-hosted-runners/using-github-hosted-runners/about-github-hosted-runners>
- <https://docs.github.com/en/actions/administering-github-actions/usage-limits-billing-and-administration>
- <https://docs.astral.sh/uv/guides/integration/github/>
- <https://playwright.dev/python/docs/ci>, <https://playwright.dev/python/docs/docker>
- <https://cli.github.com/manual/gh_workflow_run>, <https://cli.github.com/manual/gh_run_watch>, <https://cli.github.com/manual/gh_run_view>
- <https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event>
- <https://docs.github.com/en/actions/using-jobs/using-concurrency>

status: ok
