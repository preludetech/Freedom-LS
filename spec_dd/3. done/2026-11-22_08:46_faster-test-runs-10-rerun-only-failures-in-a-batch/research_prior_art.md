# Research: prior art (faster-test-runs-10-rerun-only-failures-in-a-batch)

Question: what has already been tried for "after a failed run, re-run only the failures", here or
elsewhere, and what happened? Paths are relative to the worktree root.

## 1. Why the whole-tier gate after `--lf` exists

- **It was there from the first commit and has never changed.** `git log --follow` on
  `claude_plugins/django-stack/resources/test_tiers.md` shows the sentence "Once that is green,
  re-run the whole tier as it first ran. The gate is the whole tier, not the `--lf` subset." added
  in `769ef9b41` (2026-10-08, `[batch 1] Add the test tier definition and the single test run`).
  `git log -S"--lf"` finds no later commit touching it. Later commits only inserted the runner
  sentence (`ca3c73fb2`, 2026-11-12). Current text: `test_tiers.md:97-103`.
- **Where it came from:** `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient`.
  - `idea.md:101` lists it under "Settled": "A failing targeted run is fixed with the pytest
    cache's `--lf` loop, then the tier re-runs whole."
  - `2. plan.md:181-185` carries the same text into the tier definition.
  - The only stated reason is in `research_test_selection_tools.md:74` and `:130`: `--lf`
    "does not detect regressions in tests that passed before", so it is for "fix loops only; never
    as the gate".
  - At the time no batch ran a targeted run (`research_current_test_runs.md:188`: no command used
    `--lf` or a changed-files subset), and each batch ran the full suite (`:13`). The rule was set
    before any measurement of how often or how widely it would fire.
- **It was not argued against load.** The effort's own measurement now shows the cost:
  `spec_dd/1. next/faster-test-runs/research_batch_test_load.md` "How often one batch runs its tier"
  lists the whole-tier repeat as one of four tier runs per batch, and "Runs that did not pass"
  counts 79 failed runs in 3.5 days, 46 of them with 3 failures or fewer, a median of 22 minutes
  for a large run, up to 88, and the top repeat failures being Playwright flows (likely timeouts
  under load; not measured).

## 2. Places in this repo that already dropped the whole-tier repeat

The narrowing this spec proposes has been done twice already, at the milestone end of the loop:

- **`implement_plan` Step 3 fix loop** (`spec_dd/3. done/2026-11-19_16:16_spec_dd_efficiency_and_docs/1. spec.md:79-82`):
  a failed final full run is fixed by re-running the failing tests by node ID until they pass,
  then `targeted` over the fix's range. "It does not repeat the full run ... The full run in
  `finish_worktree` Step 1 covers the fixes." Live at `claude_plugins/sdd/commands/implement_plan.md:133`.
  This is close to answers.md Q1 (failed tests plus the selection for the fix's own diff).
- **`do_qa` / `qa_fix`** (same spec, `1. spec.md:83-85`): "Full run after the last fix" became
  `targeted` over the fix commits.
- No problem from either change is recorded in later specs: `2026-11-21_16:08_full-test-run-still-too-often`
  contains no `--lf` or whole-tier discussion (grep), and its `research_prior_art.md` lists the
  remaining full runs as call-site and checkpoint issues, not missed regressions.

Inside a batch, the old rule still applies through one pointer: `implement_plan.md:52` (batch),
`:82` (fix batches are batches), `:88` (integration run after a wave), `:122` (review fix) and
`claude_plugins/django-stack/commands/rebase_main.md:215-222` all send a failure to "When a
targeted run or full run fails". Changing that one section changes all of them, which is what the
idea's "the rule is written in the tier definition" relies on.

## 3. What the `--lf` mechanism was found to get wrong

`spec_dd/3. done/2026-11-13_14:59_claude-ram-usage` looked hard at `--lf` and rejected it for
crash recovery:

- `research_best_practices.md:51`: a crashed xdist item is reported as failed and lands in
  `lastfailed`, but tests queued behind it on the dead worker are recorded as neither, so `--lf`
  misses them.
- `research_known_complaints.md:29`: "a later partial run can overwrite the lastfailed set"
  (unverified there). From pytest's cache plugin behaviour, `lastfailed` is also cumulative: a test
  that failed in an older run and was not selected since stays in it, so `--lf` after a narrow
  targeted run can pull in stale failures from other apps (not measured here).
- Its spec (`1. spec.md:55`) settled: "Completion is recorded by a pytest plugin, not read from
  `--lf`." The runner records every node ID's outcome in `/tmp/ds_run_record_*.jsonl`
  (`claude_plugins/django-stack/scripts/run_tests.py:446`, `:696`) and retries only unfinished
  tests through `--ds-only-nodeids` (`:448`, `:577`). A test that crashed its worker on every
  attempt is counted failed (`:368-379`; `test_tiers.md:56-58`), which is the idea's last settled
  point.
- Consequence for this spec: the "failed tests" set can come from `--lf` (as today) or from the
  runner's own record. The record is deleted on `RESULT PASS` and kept on failure
  (`research_batch_test_load.md` "Runs that did not pass"), so it holds exactly the failed run's
  outcomes. Which source to use is open; the ram-usage spec chose the record over `--lf` for the
  same reasons.
- Each worktree, and each batch worktree, has its own `.pytest_cache`
  (`research_test_selection_tools.md:71`), so `--lf` in a batch worktree sees only that batch's runs.

## 4. Related rules that already re-run "only what failed"

- `finish_worktree` "Flaky tests" (`claude_plugins/sdd/commands/finish_worktree.md:106-126`) re-runs
  each failing test by node ID three times to classify it, but then step 4 says "follow the run that
  failed again from its start", which resolves to `full` again
  (`research_finish_worktree_reruns.md` "A failed run"). That repeat is
  `faster-test-runs-11-record-failed-full-runs`'s, not this spec's; the idea keeps the
  `finish_worktree` checkpoint unchanged.
- `spec_dd_efficiency_and_docs/research_best_practices.md:26`: "Use `--lf` to confirm a fix, then a
  broader tier to confirm nothing else broke. `--lf` alone is not evidence of a green suite." This
  is the argument for the gate; the idea answers it by keeping the gate at `implement_plan` Step 3's
  full run and the `finish_worktree` checkpoint, and answers.md Q1 widens the re-run by the fix's
  own diff.

## 5. Elsewhere

From tool documentation (not fetched this session; recalled, so check before quoting):

- pytest `--lf` / `--ff` / `--lfnf`: re-run only last failures, or failures first then the rest.
  `--lf` with nothing recorded runs everything unless `--lfnf=none`.
  https://docs.pytest.org/en/stable/how-to/cache.html
- Jest `--onlyFailures` (`-f`) and watch mode's "run only failed tests": the inner-loop default;
  the full suite stays in CI. https://jestjs.io/docs/cli#--onlyfailures
- Gradle Test Retry plugin: on failure, re-runs only the failed tests, at most N times, and the
  build passes if they pass; it is aimed at flakiness, but it is the CI-level precedent for not
  re-running the whole task. https://github.com/gradle/test-retry-gradle-plugin
- GitHub Actions "Re-run failed jobs": re-runs only failed jobs of a workflow, not the passed ones.
  https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/re-running-workflows-and-jobs
- Tiered-gating sources already gathered in
  `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/research_tiered_gating.md:9-14` (Google
  TAP presubmit/postsubmit, Nx, Facebook predictive selection): narrow runs in the inner loop, the
  complete run at a later gate. None prescribes a whole-suite repeat after each inner-loop fix.

What the sources agree on: re-running only failures is the normal inner-loop step, and the safety
net is a later broader run, not a repeat of the same wide run. The risk every source names is a
regression the fix causes in tests that had passed; answers.md Q1 (add the fix diff's targeted
selection) and the kept final full run and checkpoint are this repo's answer to it.

## 6. Summary for the spec

- The whole-tier repeat was a day-one "settled" rule with one stated reason (`--lf` misses
  regressions), set before batches ran targeted tiers and before any load data.
- The repo already dropped the same repeat at `implement_plan` Step 3 and in QA fixes, using
  "failing tests by node ID, then `targeted` over the fix's range"; no fallout is recorded.
- Decide the failed-test source: `--lf` has known gaps (crash queue, stale cumulative entries,
  per-worktree cache); the runner's record is the mechanism the ram-usage spec chose.
- Edit only `test_tiers.md:97-103`; every batch, fix batch, integration run and the rebase's
  targeted step point there. The rebase's `full` run (answers.md Q3) needs its own wording,
  since the same section serves both tiers today.

status: ok
