# Research: reference implementations for splitting pytest across GitHub Actions jobs

## 1. First Class workflow (read only)

File: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/.github/workflows/build-and-push.yml`

- Triggers: `push` to main and `workflow_dispatch`. `build` and `deploy-staging` follow with `needs: test`. The test job is a matrix named `test / ${{ matrix.group }}`.
- **Path groups, not duration splitting.** `strategy.matrix.include` has 6 groups. Each group has a `paths` string that is appended to `uv run pytest -c pyproject.toml ${{ matrix.paths }}`. `fail-fast: false`, so one run reports every broken area.
  - The groups are `project` (`tests/`), `fls-learner-interface`, `fls-learner-data`, `fls-accounts`, `fls-content` and `fls-platform`. The FLS ones are directories under `submodules/Freedom-LS/freedom_ls/`.
  - Families of apps are claimed by shell glob (`learner_*`, `course_*`, `content_*`).
- **Guard against leaving tests out.**
  - The last group, `fls-platform`, is a catch-all. It takes the whole `freedom_ls` tree minus the paths the other groups claim. It uses `--ignore=<dir>` for named apps and `--ignore-glob='*/freedom_ls/learner_*'` and the like for the families. A new upstream app lands in the catch-all by default.
  - The comment records a manual count check: the per-group collected counts, 18+474+493+533+382+1234, add up to 3134, which equals what bare `pytest` collects. This is a comment only. Nothing in CI enforces it, so a mismatch between the explicit lists and the ignore lists would go unnoticed.
  - Weak point: the ignore lists and the claimed lists are written twice and must be kept in sync by hand.
- **`-c pyproject.toml` is required.** If every path sits under a submodule, pytest picks the submodule's own `pyproject.toml` as rootdir, with different addopts. The workflow notes that this trips the submodule's coverage gate and its marker deselects. For FLS, running tests from the repo root avoids this.
- **Coverage:** none. There is no `--cov` and no combine step. The workflow comment says the submodule's 73% gate must not apply, so coverage is effectively dropped on this pipeline.
- **Postgres:** a `services: postgres: image: postgres:17` per matrix job. Each job has its own runner, so there is no contention. Health checks use `pg_isready`. The DB settings come through env vars (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`), because the settings module otherwise derives the DB name from the git branch and defaults to port 6543.
- **Reproducibility:** `PYTEST_ADDOPTS: -v -ra --tb=long --showlocals --durations=10 --randomly-seed=20260831`. The pinned seed means re-running a group locally gives the same order. `-ra` plus `--tb=long --showlocals` make the log self-diagnosing, which matters for a script that reads failures.
- **Timing:** the comment says the suite is about 3100 tests and 5+ minutes serial. Only the slowest group is on the critical path. No numbers per group are given. The `project` group is small (18 tests) and hosts the repo-wide checks (`uv lock --check`, `manage.py check`) with `if: matrix.group == 'project' && !cancelled()`.
- Setup: `actions/checkout` with submodules, `astral-sh/setup-uv` (pinned patch version), `uv sync --frozen`, `setup-node` plus `npm ci` (icons need `node_modules`).

## 2. pytest-split (jerry-git, and the PostHog fork)

- <https://github.com/jerry-git/pytest-split> and <https://github.com/posthog/pytest-split>
- `pytest --store-durations` on the full suite writes `.test_durations`. Commit it. `--durations-path` moves it.
- `pytest --splits N --group K` (K from 1 to N) runs one slice. A matrix job runs each K.
- `--splitting-algorithm`: `duration_based_chunks` (the default; keeps the original order) or `least_duration` (better balanced). The README says `duration_based_chunks` is incompatible with randomising plugins (pytest-randomly, pytest-random-order). It recommends `least_duration` plus a shared seed across groups for random ordering. **FLS-relevant:** First Class uses pytest-randomly with a pinned seed, so `least_duration` is needed.
- A test with no stored duration gets the average. New tests are therefore placed without a refresh, but balance drifts, so the file needs periodic regeneration.
- Every test lands in exactly one group by construction, since the split is computed over the collected set. That is the guard against leaving tests out. All groups must collect the same test set (same paths and same `-m` and `-k` options).
- PostHog maintains the fork. The pytest-split-ng fork (<https://pypi.org/project/pytest-split-ng/>) is reported to support pytest 9+. I could not confirm that. Check the pytest version before choosing.
- **Not verified:** I could not fetch PostHog's own `ci-backend.yml` (the raw and blob URLs returned 404 and search did not surface it). Do not cite PostHog's workflow usage without opening it in the repo.

## 3. Other open-source sharding patterns

- **Sentry** (<https://raw.githubusercontent.com/getsentry/sentry/master/.github/workflows/backend.yml>): a `calculate-shards` job outputs a shard count (default 30) and shard indices (script `.github/workflows/scripts/calculate-backend-test-shards.py`). A matrix runs `instance: ${{ fromJSON(...shard-indices) }}` with `MATRIX_INSTANCE_TOTAL` as env var, `TEST_GROUP_STRATEGY: roundrobin` and `fail-fast: false`. Each shard runs `run-backend-tests.sh`. A final gate job `backend-required-check` has `if: always()` and fails on `contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')`. The gate pattern is useful as the single required check. Note that it passes when a shard is skipped or absent, so it does not detect a missing shard. Sentry's coverage is not uploaded in this file.
- I did not open the Saleor, Wagtail or Django workflows, so I make no claims about them.

## 4. Combining coverage

- hynek, "ditch codecov python": <https://hynek.me/articles/ditch-codecov-python/>
  - Each matrix job runs coverage in parallel mode and uploads `.coverage.*` with `actions/upload-artifact` (`name: coverage-data-<matrix key>`, `include-hidden-files: true`, because dot-files are skipped by default).
  - A later `coverage` job has `needs: tests` and `if: always()`. It downloads with `pattern: coverage-data-*` and `merge-multiple: true`, then runs `coverage combine`. Then `coverage report --format=markdown >> $GITHUB_STEP_SUMMARY`, then `coverage report --fail-under=100`.
  - On failure it uploads the HTML report as an artifact.
  - It shows no `[tool.coverage]` snippet. For `coverage combine` to work across runners, set `parallel = true` and `relative_files = true` (path remapping) in the coverage config. This comes from coverage.py docs, not from the article.
- Guide: <https://pydevtools.com/handbook/how-to/how-to-combine-coverage-across-a-ci-matrix/> (same pattern).
- **Implication:** with a sharded run, the per-job `--cov-fail-under` must be disabled (`--cov-fail-under=0` or `--no-cov-on-fail`), and the threshold enforced once in the combine job. The combine job should also `needs` all shards, so a missing shard artifact means a lower total, not silent success. I did not look at py-cov-action.

## 5. Starting a workflow_dispatch run and reading its result

- `gh workflow run <file> --ref <branch> -f key=value` (<https://cli.github.com/manual/gh_workflow_run>). The manual says it prints the created run URL "if available". It does not document obtaining the run ID. Common workarounds (my inference, not from the page): list runs by `gh run list --workflow <file> --branch <branch> --event workflow_dispatch --json databaseId,headSha,createdAt -L 1` shortly after dispatch, or pass a unique input (e.g. a nonce) and match it. The run ID race is the weak point.
- `gh run watch <run-id> --exit-status` blocks and exits non-zero when the run fails (<https://manpages.debian.org/testing/gh/gh-run-watch.1.en.html>). `gh run view <id> --log-failed` prints only the failing steps' logs. `gh run download <id> -n <artifact>` fetches artifacts (for example a JUnit XML or a failures summary from each shard). The last two are from my knowledge of the `gh` CLI, not verified in this session.
- Third-party actions that dispatch and wait, for use inside workflows (they are not needed for a local script):
  - <https://github.com/marketplace/actions/workflow-dispatch-and-wait>
  - <https://github.com/ietf-tools/workflow-dispatch-action> (`waitForCompletion`)
  - benc-uk/workflow-dispatch (`wait-for-completion`, 5 s poll, 900 s default timeout)
  - I did not find a "return-dispatch" action in search and cannot confirm its name or behaviour.
- **FLS-relevant:** an SDD script can be plain `gh`: dispatch with the branch, find the run for the head SHA, `gh run watch --exit-status` with its own timeout, then on failure `gh run view --log-failed` or download a failures artifact. Because `-ra --tb=long` is set, the failure summary is in the log. Verify that the run's `headSha` equals the local commit. This is what the full-run record needs.

## Take-aways for the spec

1. Two ways to define the split: path groups with a catch-all (First Class, hand-maintained, but gives per-area signal) or pytest-split over the whole collected set (every test lands in exactly one group by construction, needs a durations file and `least_duration` with pytest-randomly).
2. Combine coverage via artifacts, a single combine job, and `--fail-under` there. Per-shard thresholds must be switched off. Make the combine job and a gate job depend on all shards.
3. The gate job pattern should also treat `skipped` as a failure, so a missing shard cannot pass.
4. The remote trigger and read-back is plain `gh`, and the run ID lookup is the fragile step.

status: ok
