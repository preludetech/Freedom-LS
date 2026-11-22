# Test tiers

Before running pytest, name a tier (`none`, `targeted` or `full`) and follow this file. The flags
live here and nowhere else.

## The tiers

- **none.** No pytest. The step reports `tier: none` and moves on. A caller passes it when it
  runs its own tier afterwards (the rebase command does this). A targeted run whose wrapper prints
  `tier: none` is reported as `none` too.
- **targeted.** Run the wrapper with the step's diff:

  ```
  .claude/ds/scripts/select_tests.sh <diff arguments>
  ```

  The diff arguments are the step's own: `--working-tree` for uncommitted and untracked files,
  explicit paths, `--range <rev>..<rev>` (repeatable) for the files a git range changed,
  `--upstream-range <old>..<new>` (once) for the paths main brought in between two bases, where a
  path the branch's own diff does not contain counts only where it meets the branch (the apps it
  changed, the apps those import, the apps that import them, and the tests its own paths select),
  and `--tests-changed-in <rev>..<rev>` for test files that join a targeted
  run without ever raising its tier. An untracked file no rule knows is `none`; a tracked one is `full`. The `tier:` line is
  the tier that applies; `none` means there is nothing to run. Run the `command:` line exactly as
  printed, and quote the `why:` lines when reporting. The generic `none`, escalation and
  dependency-file lists are three glob tuples at the top of
  `${CLAUDE_PLUGIN_ROOT}/scripts/select_tests.py`; the project's own are `none`, `escalation` and
  `dependency_files` in `[tool.test_tiers]` in `pyproject.toml`. The script applies them; never apply them by
  hand. Done when every `why:` line is accounted for and the printed command exits zero.

  `narrow = true` in `[tool.test_tiers]` opts a project into narrow selection; it is off when the
  key is absent or `false`. Under it, a changed Python module selects its own app's tests plus the
  test files that import it, directly or through other modules, instead of every app that imports
  the app. A non-Python file in an app, or a module under `templatetags/`, selects its app plus the
  apps one hop away in the app map. The generic escalation globs stop meaning `full`, except
  migrations, a `conftest.py` above an app directory, and a `urls.py` or `apps.py` no app owns;
  the project's own `escalation` globs still mean `full`. A narrowed run prints
  `mode: narrow` under the `tier:` line, and each narrowed `why:` line ends `(narrow; the rest is
  left to a full run)`: links no import shows (a model named by string, receivers wired in
  `AppConfig.ready`, dotted paths in settings, a template included from another app) wait for the
  full run. `--wide` ignores `narrow` and selects whole related apps; it never prints `mode:`.

  A checkpoint selects wide. Its `<selector>` is the wrapper followed by `--wide`, and the targeted
  run after a `targeted` resolution passes `--wide` before the resolved `<diff>`:

  ```
  .claude/ds/scripts/select_tests.sh --wide <diff arguments>
  ```
- **full.** The whole suite, in parallel:

  ```
  uv run pytest -n auto
  ```

  plus `-m '<expression>'` when `[tool.test_tiers]` in `pyproject.toml` sets `markers`. That
  `-m` replaces the one in `addopts`, so tests the default run deselects still run in a tier.
  The wrapper prints the exact line for a `tier: full` result; with the test runner installed it
  starts with `.claude/ds/scripts/run_tests.sh`. Run it as printed. Coverage and its threshold run
  wherever the project puts them: in `addopts`, or in CI only.

  With `[tool.test_tiers.remote] command` set, every full tier runs that command, in the background
  as any full tier, with the local full command as its fallback. A `tier: full` result prints them
  on `command:` and `fallback:`. A full tier asked for directly, with no selector run, reads
  `command` from `pyproject.toml` itself and uses the local full command above as the fallback.
  `DS_TEST_REMOTE=off` skips the remote command: the wrapper prints the local command alone, and a
  direct request runs the local command.

  A remote command meets this contract: it prints the runner's `run:` lines, `run: tested <sha>`
  and `run: RESULT PASS|FAIL|UNAVAILABLE`; it exits 0 only on `PASS`; its failed set is its
  `run: failed` lines; the table's other keys are its own.

  On `run: RESULT UNAVAILABLE <reason>`, quote the reason and run the `fallback:` line as the
  full tier. Its result is the tier's result.

## How to run a tier

Run `targeted` and `full` with the Bash tool's `run_in_background: true` and wait for the completion
notification. Run one tier at a time per worktree. Run the bare command and let it finish; a full
run can take more than ten minutes, and a crash retry happens inside that one background run. No
`ps` or `pgrep` polling loops and no `timeout` wrapper.

## Memory-aware runs

The test runner, `.claude/ds/scripts/run_tests.sh`, wraps one pytest command: it sizes the xdist
worker count to free memory, waits a bounded time when memory is short, retries a crashed attempt
for the tests that never finished, and prints one verdict.

A number the command gives with `-n` is a ceiling on the worker count, and `-n 0` stays serial.
A pytest that exits before its session starts (a usage error, a `conftest.py` that fails to
import) is not retried: its exit code passes through as `RESULT FAIL`. A test whose worker dies
while running it in every pytest attempt, of two or more, is counted as failed.

Each setting comes from its environment variable, then from `[tool.test_tiers.memory]` in
`pyproject.toml`, then from the default. A wrong type or an unknown key exits 2 and names the key.

| Key | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `per_worker_mb` | `DS_TEST_PER_WORKER_MB` | 1024 | Memory one xdist worker needs |
| `reserve_mb` | `DS_TEST_RESERVE_MB` | 2048 | Memory left free for everything else |
| `max_workers` | `DS_TEST_MAX_WORKERS` | `os.cpu_count()` | Ceiling on `-n` |
| `psi_some_avg10_limit` | `DS_TEST_PSI_LIMIT` | 10.0 | Wait while `some avg10` in `/proc/pressure/memory` is above this |
| `wait_timeout_s` | `DS_TEST_WAIT_TIMEOUT_S` | 600 | Longest wait before running with 1 xdist worker |
| `max_retries` | `DS_TEST_MAX_RETRIES` | 2 | Crash retries after the first pytest attempt |
| `oom_score_adj` | `DS_TEST_OOM_SCORE_ADJ` | 500 | Set on the pytest child; 0 skips |

`DS_TEST_MEMORY_GUARD=off` runs the command unchanged: no gate, sizing, retry or extra lines.

## A single test run

The TDD RED and GREEN runs of one test:

```
uv run pytest <file>::<test> -x --no-cov
```

Pass `--no-cov` on `pytest --co` and any other partial run too.

## Reporting

Report the tier that ran as `tier: none|targeted|full`.

With the test runner, quote `run: summary (merged)` and `run: RESULT ...`, not pytest's own last
line, a remote full run's included. The step is done at `RESULT PASS`. `RESULT INCOMPLETE` means tests were left unfinished
after the retries: report it as blocked on memory, not as a failure to fix. `RESULT FAIL` is a
failure to fix, including a test counted as failed because it crashed its worker every time.

Without the runner, quote the final pytest summary line. The step is done when that line shows no
failures.

A failed-only re-run reports `tier: <tier> · summary: failed-only re-run of <n> tests + fix
selection: <verdict line>`. The failed run's own report line stays in the report, ahead of it.

## When a targeted run or full run fails

This section addresses the agent that owns the change, never a mechanic briefed only to run a tier.

The **failed set** is the node IDs of the tests the failed run left to fix. With the runner, they
are the `run: failed <node id>` and `run: unfinished <node id>` lines. When the output has no
`run: summary (merged)` line (no runner, `DS_TEST_MEMORY_GUARD=off`, or the runner's plain
fallback), they are the node IDs on pytest's `FAILED <node id> - <message>` short-summary lines. A
run that printed `run: failed ... and <n> more` has too many to list, so it takes the whole-tier
re-run, whatever the caller asked for.

A remote full run's `RESULT FAIL` with `run: failed` lines takes the failed-only re-run, run
locally. One with no `run: failed` line (its `run: coverage` line names the reason) has no
failed set, so it takes the whole-tier re-run, which starts at the full tier.

Fix the failure, then re-run as the caller says. A caller that names neither re-run gets the
whole-tier re-run.

### Failed-only re-run

Run only the failed set, then stop. Select with the fix's diff, not the original one:

- The fix is uncommitted: pass the files it edited as explicit paths. `--working-tree` would
  select the caller's whole uncommitted change again.
- The fix is committed: pass `--range <sha before the fix>..HEAD`.

What runs depends on the `tier:` line the selector prints:

- `targeted`: run the printed `command:` line with the failed set appended.
- `none`: run the failed set on its own. Replace `<markers>` with `markers` from
  `[tool.test_tiers]` and drop `-m` when it is unset. Drop the runner prefix when the runner is not
  installed.

  ```
  .claude/ds/scripts/run_tests.sh uv run pytest -n auto --no-cov -m '<markers>' <node ids>
  ```

- `full`: run the full tier. It is an ordinary full run, so its pass finishes the step.

The runner's node IDs are already shell-quoted: append them exactly as printed. A node ID taken
from a pytest `FAILED` line is the text between `FAILED ` and the first ` - `, wrapped in single
quotes, with each single quote inside it written as `'\''`.

Done when that run passes. A failure in it is fixed the same way, with its own failed set and the
new fix's diff.

### Whole-tier re-run

Do the failed-only re-run. Once it passes, run the tier again as it first ran. The gate is the
whole tier.
