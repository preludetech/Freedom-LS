# Known complaints: sharded tests on GitHub Actions, triggered and awaited from scripts

Only the `gh workflow run` run-id item was checked against a live source in this session. The other items come from general knowledge and carry no URL. Verify them before the spec relies on them.

## Verified

- **`gh workflow run` run id.**
  - For years the dispatch API returned nothing, so scripts listed recent runs and picked the newest. That races when two dispatches land together.
  - On 2026-02-19 GitHub changed the dispatch API to return run ids on request. `gh` v2.87.0 and later print the run URL and a `gh run view` hint.
  - Spec implication: require `gh` >= 2.87.0 and parse the printed URL. Fall back to listing runs by branch, event and creation time on an older `gh`.
  - Sources:
    - <https://github.blog/changelog/2026-02-19-workflow-dispatch-api-now-returns-run-ids>
    - <https://github.com/orgs/community/discussions/9752>
    - <https://github.com/cli/cli/issues/9038>
    - <https://github.com/cli/cli/issues/7642>

## Complaints from general knowledge (no URL checked)

**Sharding**
- **pytest-split durations drift.**
  - `.test_durations` goes stale as tests are added or slowed. The groups become unbalanced, and one shard ends up at the job cap.
  - New tests with no recorded duration get the average, which skews the split.
  - The `least_duration` algorithm is more even than `duration_based_chunks`.
  - Mitigations: refresh the durations file periodically, and keep a generous per-job timeout.
  - Source: <https://github.com/jerry-git/pytest-split>
- **Tests skipped or run twice.**
  - All shards must use the same collection: same plugins, same `-k` or `-m` filters, same test ordering and no randomisation.
  - A collection difference between shards, such as the DB or env, silently drops or duplicates tests.
  - Mitigations: a final job that sums the collected counts and compares them to a full `--collect-only`.
  - Mitigation for new apps: derive the split from the collection rather than from per-app lists.
- **Coverage combine.**
  - Each shard's `.coverage.*` data holds absolute paths from its own runner checkout. If `[tool.coverage.paths]` is not set, `coverage combine` cannot merge them.
  - A threshold (`fail_under`) checked per shard fails on partial data. Check it only after combining.
  - A failed or cancelled shard leaves a combined report that is incomplete but can still pass.
  - Artifact upload and download names must not collide. `upload-artifact` v4 made artifact names immutable per run, so each shard needs a unique name.

**Triggering and waiting**
- **`workflow_dispatch` only works once the workflow file is on the default branch.**
  - The workflow can be dispatched only after the file exists on the default branch.
  - After that, `--ref <branch>` runs the branch's own copy of the file.
- **Concurrency `cancel-in-progress`.**
  - A group keyed on the ref cancels a manual run when a push to the same ref arrives, or the reverse.
  - A cancelled run reads as a failure to a script that waits on it.
  - Mitigation: include `github.event_name` or `run_id` in the group for dispatch runs.
- **Queue delays and limits.**
  - The free tier allows 20 concurrent jobs per account, and fewer on some plans. N shards times several concurrent runs queue behind each other.
  - Queue time is not covered by the job timeout, so a waiting script needs its own overall timeout.
  - Shard count therefore trades speed against queue risk.
- **API rate limits with `gh`.**
  - Tight `gh run view` polling can hit the rate limit. `gh run watch` defaults to 3-second polling and can be slow to exit.
  - Prefer `gh run watch --exit-status` with a longer `-i` interval, or poll every 15-30 seconds.
- **Extra workflows from pushes.**
  - Pushing every in-progress branch fires `push` and `pull_request` runs alongside the dispatch.
  - Mitigation: limit `push` to main, and run branches through `workflow_dispatch` and PRs.

**Infrastructure and output**
- **Postgres service container flakiness.**
  - The usual failures are connecting before the server is ready, and port-mapping surprises.
  - Mitigation: a `--health-cmd pg_isready` option with retries.
  - Parallel workers need one database per worker.
- **Playwright install failures on new runner images.**
  - When `ubuntu-latest` moves to a new Ubuntu release, `playwright install --with-deps` can fail on missing or renamed system packages. A Playwright release that supports the new image fixes it.
  - Mitigations: pin the runner to a specific `ubuntu-NN.04`, and upgrade Playwright.
  - Browser downloads can also fail transiently, so retry them. Cache `~/.cache/ms-playwright` keyed on the Playwright version.
- **Log truncation and `--log-failed`.**
  - `gh run view --log-failed` prints a failed step's whole log, which can be huge. It returns nothing while the run is still in progress, and it is empty for cancelled jobs.
  - Mitigation: have each shard upload a JUnit XML or `--tb=short` summary as an artifact. The agent then reads the failing test ids from that instead of raw logs.
- **Artifact retention.**
  - The default retention is 90 days and is configurable. The free tier's storage quota is small for large coverage data. Set `retention-days: 1-7` for per-shard artifacts.

status: ok
