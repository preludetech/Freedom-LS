# Test load from SDD batches

Measured on 2026-11-21 on the same 16-core, 30 GB machine as `research_test_timings.md`, while
13 Claude Code sessions were open across FLS worktrees and the First Class project.

## What a batch's targeted run selects

`select_tests.sh --range <commit>^..<commit>` replayed over the 119 `[batch …]` commits on `main`
since 2026-11-19:

| Result | Batches |
|---|---|
| `tier: full` | 34 |
| `tier: targeted`, 28 to 38 of the 42 app test directories | 35 |
| `tier: targeted`, 1 to 5 app test directories | 47 |
| `tier: none` | 3 |

69 of 119 batches (58%) run most or all of the suite.

Why the 34 went to `full`:

| Reason | Batches |
|---|---|
| Unmapped path, 3 of them `demo_content/**/*.md` | 14 |
| `**/conftest.py` | 9 |
| `config/**` | 3 |
| `**/urls.py` | 2 |
| `**/factories.py` | 2 |
| Dependency file | 2 |
| `**/migrations/**` | 1 |
| `**/apps.py` | 1 |

Why the 35 targeted runs were wide: the selector works per app. One changed file selects the owning
app's tests directory and the tests directory of every app that imports it, through any number of
runtime imports. App test directories selected by a change to one file in each app:

| App | Test directories selected |
|---|---|
| `base` | 38 |
| `panel_framework` | 36 |
| `accounts` | 36 |
| `icons` | 30 |
| `content_engine` | 28 |
| `educator_interface` | 2 |

Owning apps behind the 35 wide runs (a batch can touch several): `panel_framework` 20,
`form_engine` 9, `base` 8, `learner_interface` 3, `educator_interface` 3, `content_engine` 3.

## How often one batch runs its tier

`implement_plan.md` and `test_tiers.md` ask for the tier:

- once in the batch;
- again, whole, after any failure is fixed ("the gate is the whole tier, not the `--lf` subset");
- once per review fix, design fix and integration fix batch (73 `review fix` commits in 60 days);
- once more over the wave's range after a parallel batch wave is integrated.

The final `full` run of `implement_plan`, each step's pre-step rebase and the `finish_worktree`
checkpoint come on top.

## Runs that did not pass

`run_tests.py` deletes its record file on `RESULT PASS`, so `/tmp/ds_run_record_*.jsonl` holds
only runs that failed or never finished. 130 of them in the 3.5 days since the last reboot:

- 79 finished with failures. 51 never finished: a few were still running, the rest were killed or
  abandoned.
- 98 of the 130 collected more than half the suite (19,738 tests in the largest collection).
- A large run took a median of 22 minutes, and up to 88.
- 109 started with 4 workers, 13 with 3, 6 with 2, 2 with 1.
- 46 of the 79 failed runs failed 3 tests or fewer. 16 failed more than 50.
- The tests that failed in the most runs are Playwright flows: `test_learners_list_flow.py`
  (12 runs), `test_members_flow.py` (11), `panel_framework`'s `test_data_table_flow.py` (11) and
  `test_quick_view_flow.py` (9).

## Machine state while measured

- Load average between 40 and 77.
- `/proc/pressure/cpu` `some avg10` about 80. `/proc/pressure/memory` `some avg10` 0.09.
- 26 of 31 GB of memory in use and 21 GB in swap.
- Two parallel batch worktrees had finished editing, two files each, within 6 minutes of creation.
  Their pytest runs were then 39 minutes old.
- A batch worktree's setup (`uv sync`, `npm i`, the Tailwind build) took 45 seconds.

## What the runner limits

- `wait_for_memory` in `run_tests.py` reads `MemAvailable` and memory pressure. It never reads CPU
  load and knows nothing of other runs.
- Each run takes up to `max_workers` (4 here) whatever else is running.
- A run short of memory waits up to `wait_timeout_s` (600), then starts with one worker.
- Of six test runs alive at one moment, three did not go through the runner: two plain
  `uv run pytest -n …` calls, one wrapped in `timeout 1800`, and a First Class run.

## Not measured

- Time spent waiting for memory. The runner prints it and does not record it.
- Runs that passed, since their records are deleted.
- Whether the repeat Playwright failures are timeouts caused by load.
