# Research: best practices for RAM-aware parallel tests and agent fan-out

Note: written from established knowledge of the Linux kernel docs, psutil, pytest-xdist and pytest docs. URLs are the canonical references. I did not re-fetch them in this run, so check version-specific details (marked VERIFY) before relying on them.

## Ranking by likely impact (highest first)

1. **Size xdist workers by memory, not CPU.** Cap `-n` at `min(cpu_count, floor((available_bytes - headroom) / per_worker_bytes))`. This is the root-cause fix. On this machine 16 workers, each with a Django process, a DB clone connection and possibly Chromium, on 31 GB with 20 GB of swap already used, is the failure. Cheapest and biggest win.
2. **Measure with MemAvailable, and treat swap-in-use as a pressure signal.** An accurate gate is a precondition for item 1. Here swap is already 20 GB used, so "free" is misleading. MemAvailable does not count swap.
3. **Detect a worker crash distinctly from a test failure, then rerun only the unfinished tests with fewer workers (max 2 retries).** This is the user's own recovery idea and it is sound. It needs the crash signature and a way to list the tests that never finished (see below).
4. **Wait-for-RAM gate before starting (bounded poll with timeout).** Useful but secondary to item 1 because the fan-out of other processes changes memory after the gate. Keep it short and bounded.
5. **Reduce per-worker memory** (Playwright browser reuse, fewer Playwright tests per worker, avoid `--reuse-db` clone bloat, `--max-worker-restart`). Moderate impact, repo-specific, and mostly belongs in fls-dev or project config.
6. **Throttle SDD subagent fan-out by memory.** A subagent is a Claude Code process (Node, roughly several hundred MB each) plus whatever it runs, so the real spike is tests run by several parallel batches. `Parallel batches: 3` times `-n auto` multiplies. Highest-value change here is that each test run sizes itself against current MemAvailable (items 1 and 2), which automatically accounts for the other batches. A separate fan-out throttle is lower value.
7. **Section the suite with checkpoints.** Lowest impact versus complexity. Rerun-only-unfinished (item 3) gives most of the benefit with no checkpoint format.

## 1. Measuring available memory

### Linux
- **`/proc/meminfo` `MemAvailable`** is the kernel's estimate of memory available to start new workloads without swapping (free + reclaimable page cache and slab, minus low watermarks). It is the right number. `MemFree` is wrong (excludes cache), and `free`'s "available" column is just MemAvailable. Kernel 3.14+. Ref: https://www.kernel.org/doc/html/latest/filesystems/proc.html and commit https://git.kernel.org/linus/34e431b0ae39.
- **Swap** (`SwapTotal`, `SwapFree` in meminfo). MemAvailable ignores swap, so a machine can report plenty "available" while thrashing swap. Large swap-in-use plus active paging is the real warning. Practical signal: `SwapTotal - SwapFree` is high, or `pswpin`/`pswpout` in `/proc/vmstat` is growing during a short sample. Do not count free swap as headroom: swapped-out workers make tests 10x slower and still end in OOM.
- **PSI (`/proc/pressure/memory`)**: lines `some avg10=… avg60=… avg300=… total=…` and `full …`. Measures time tasks stalled on memory, so it captures thrashing that MemAvailable misses. Needs kernel 4.20+ with `CONFIG_PSI`. Can be absent or disabled (`psi=0`), and can need root on some setups. Use it as an optional second signal: treat `some avg10` above a threshold (about 10-20) as "wait". Fall back to MemAvailable-only when the file is missing. Ref: https://docs.kernel.org/accounting/psi.html.
- **cgroup limits**: inside a container or systemd slice, host MemAvailable overstates what the process may use. Read cgroup v2 `/sys/fs/cgroup/memory.max` (`max` means unlimited) and `memory.current`, or v1 `/sys/fs/cgroup/memory/memory.limit_in_bytes` and `memory.usage_in_bytes`. The effective budget is `min(MemAvailable, memory.max - memory.current)`. Refs: https://docs.kernel.org/admin-guide/cgroup-v2.html. On a plain developer desktop this normally does not bind, so implement it as a cheap min() and not a core feature. Claude Code sandboxes or systemd-run scopes could set limits, so keep the min().
- **OOM-killer**: when the kernel kills, a worker sees SIGKILL (exit status -9 from Python's `Popen.returncode`, 137 from a shell). `dmesg`/`journalctl -k` shows "Out of memory: Killed process"; usually unreadable without privileges, so do not depend on it.

### Portable (macOS, other)
- **psutil**: `psutil.virtual_memory().available` is MemAvailable on Linux and a computed value (inactive + free + speculative, approximately) on macOS; `.percent` is derived from it. `psutil.swap_memory()` gives swap used. Ref: https://psutil.readthedocs.io/en/latest/#psutil.virtual_memory. psutil is not stdlib. If the plugin scripts must stay dependency-free, read `/proc/meminfo` directly on Linux, `vm_stat` plus `sysctl hw.memsize` on macOS (parse page size from the first line of `vm_stat`; available is about free + inactive + speculative pages), and no-op (report "unknown", do not block) elsewhere. Failing open on unknown platforms is the established practice.
- macOS has no PSI; `memory_pressure` command or `sysctl kern.memorystatus_level` gives a coarse level. macOS compresses memory, so numbers are softer. Treat as optional.
- Windows is out of scope for this project (not mentioned in the answers).

## 2. Sizing pytest-xdist workers by memory

- xdist's own options: `-n N`, `-n auto` (physical cores via psutil if installed, else logical), `-n logical`, and `--maxprocesses=N` (caps `auto`/`logical`). `PYTEST_XDIST_AUTO_NUM_WORKERS` env var overrides what `auto` resolves to (xdist 3.1+; VERIFY). Ref: https://pytest-xdist.readthedocs.io/en/stable/distribution.html and https://pytest-xdist.readthedocs.io/en/stable/how-to.html. The env var is a low-cost integration point: a wrapper can compute N and export it or pass `-n N` explicitly, with no pytest plugin needed.
- xdist can also be told programmatically via a `pytest_xdist_auto_num_workers(config)` hook (xdist 3.x; VERIFY). It allows computing the worker count inside conftest/plugin, but then a wrapper script cannot easily reuse the number for retries. Prefer the wrapper script.
- Formula (established practice): `workers = clamp(1, cpu_cap, floor((MemAvailable - reserve) / per_worker))`. Typical per-worker figures need measuring: a Django test process is around 300-600 MB; a Playwright worker with Chromium adds around 400 MB-1 GB. Make `per_worker_mb`, `reserve_mb` and `min_workers` configurable (plugin defaults, pyproject `[tool.*]` table override, env override as the user requested). Measure by running once with `-n 1` and recording peak RSS (e.g. `/usr/bin/time -v` or psutil sampling), rather than guess.
- Subtract swap pressure: if swap in use is more than about 50% of SwapTotal or PSI is high, halve the budget or wait.
- Two-tier workers: if Playwright tests are a separate tier (see `test_tiers.md`), apply a larger per_worker figure to that tier. Browser tests are the memory hogs, so capping them separately buys the most.
- Practical floor: never go below 1 worker; at `-n 0` run in-process (no xdist) for lowest memory and cleanest tracebacks.

## 3. Detecting a crashed worker versus a test failure

- xdist emits, on a worker process dying (OOM kill, segfault, `os._exit`): `[gw3] node down: Not properly terminated` and then `replacing crashed worker gw3`; the test running at the time is reported failed as `worker 'gw3' crashed while running 'tests/test_x.py::test_y'`. If a worker crashes with no test identified: `worker 'gw3' crashed`. Source: `xdist/dsession.py` (`worker_errordown`, `handle_crashitem`) and `xdist/remote.py`. VERIFY exact text against the installed xdist version.
- Crash handling: xdist restarts the worker and marks only the in-flight item as failed (the crash item). `--max-worker-restart=N` (default `4 * number_of_workers`) is how many replacements are allowed before xdist aborts with "Maximum crashed workers reached"; `--max-worker-restart=0` disables restarts. Ref: https://pytest-xdist.readthedocs.io/en/stable/known-limitations.html and https://pytest-xdist.readthedocs.io/en/stable/crash.html (VERIFY URL). Consequence: a mass OOM can leave many "crashed" failures plus a summary where the suite did not run everything. Setting a small `--max-worker-restart` makes xdist fail fast, which gives the wrapper control to back off and rerun.
- **Distinguishing signals, most robust first:**
  1. Machine-readable report: use `--junitxml` or a small plugin/`pytest_report_teststatus`/`pytest_testnodedown(node, error)` hook (xdist hook, called when a node goes down; `error` is non-None for crashes). `pytest_handlecrashitem(crashitem, report, sched)` (xdist 3.x; VERIFY) is the dedicated hook. A conftest plugin that records crashed node ids to a file is the cleanest signal.
  2. Parse the console/junit text for `worker 'gwN' crashed while running` and `node down` / `Not properly terminated`. Brittle but dependency-free.
  3. Exit code: pytest returns 0 (ok), 1 (tests failed), 2 (interrupted), 3 (internal error), 4 (usage), 5 (none collected). A crash with xdist usually still yields 1 or 2/3 and not 137; a SIGKILL of the **main** pytest process gives 137 (shell) / -9 (Python) which is a clean OOM-of-the-controller signal. So exit code alone cannot separate worker crash from a failing test; combine with item 1 or 2. Pytest exit codes ref: https://docs.pytest.org/en/stable/reference/exit-codes.html.
  4. Corroborate with memory state: low MemAvailable or kernel OOM message at the time raises confidence that a crash was memory-related. A crash from a segfault in a C extension should not trigger "fewer workers" backoff in the same way, but for a retry decision both can be treated alike (rerun, bounded to 2).
- Other crash causes to expect: Chromium/Playwright subprocess killed (shows as a Playwright "Target closed"/"browser has been closed" test failure, not a worker crash); PostgreSQL backend killed (shows as `OperationalError: server closed the connection unexpectedly`, test failure). Decide whether those count as OOM; the answers say only worker crash versus test failure, so keep scope to xdist crash signatures.

## 4. Rerunning only unfinished tests

- `--lf` / `--last-failed` reruns tests recorded as failed in `.pytest_cache/v/cache/lastfailed`. With xdist the cache is written by the controller from reports. A crashed item is reported as failed, so it lands in `lastfailed`, but **tests queued behind it on that worker that never started are not recorded as failed or passed**, so `--lf` misses them. That is the gap the user's idea targets. Ref: https://docs.pytest.org/en/stable/how-to/cache.html.
- Reliable approach: compute "never finished" = (collected node ids) minus (node ids with a final passed/skipped/xfailed/failed report in a completed state). Collect via `--collect-only -q` (cost: a few seconds, more with Django), or have the same recording plugin note each `pytest_runtest_logreport` (phase `call`/`teardown` done) into an append-only file (one node id per line, flushed). The retry runs the complement, passed as explicit node ids (use `@file` argument files or `--deselect` if the command line gets long; pytest accepts a file via `@argsfile`, VERIFY pytest 8.2+) with the smaller worker count.
- Failed (genuine) tests from the first pass should not be rerun by the OOM recovery, only crash items and unstarted tests. Report genuine failures from all passes in the final summary; the crash items rerun once under reduced load and are judged then.
- `--sw`/`--stepwise` stops at first failure and is incompatible with this approach and xdist semantics; do not use.
- `pytest-xdist` `--dist loadfile`/`loadgroup` affect which tests share a worker (relevant for Playwright and DB-heavy groups) and how much is lost on a crash.
- Existing alternatives: `pytest-rerunfailures` reruns failing tests in place (including crashed ones with `--only-rerun`; its crashed-worker support is partial; VERIFY), but it cannot reduce worker count. Not a fit.

## 5. Backoff strategies

- Established: exponential backoff with cap and jitter for retrying contended resources (https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/). For local memory contention the retry should be **state-driven, not time-driven**: after a crash, wait until MemAvailable recovers (poll every few seconds, up to a timeout), then retry with a smaller worker count (e.g. halve: 16 -> 8 -> 4, never below 1). Add a modest fixed or capped-exponential sleep (e.g. 5 s, 15 s) as a floor so the OOM-killed memory is actually returned.
- Cap at 2 retries (per the answers). On exhaustion, fail with a clear message listing the unfinished tests, not a silent pass.
- Wait-for-RAM gate: poll with a hard timeout (e.g. a few minutes). On timeout, proceed with a reduced worker count down to `min_workers` and print the warning, rather than blocking forever, since there is no cross-worktree lock (per the answers). Since the lock is out of scope, jitter (random 0-5 s) before measuring reduces the case where several worktrees start at once and all read the same free value.
- Halving the worker count on each retry is the common choice; alternative is recomputing from fresh MemAvailable (preferred, with halving as an upper bound so it never goes up).

## 6. Reducing per-worker memory (Django + PostgreSQL + Playwright)

- **DB cloning**: each xdist worker creates `test_<db>_gwN` (pytest-django). Each clone costs PostgreSQL backend memory (shared_buffers is shared; per-connection `work_mem` and backend overhead is about tens of MB) and time, not Python RSS. Fewer workers means fewer clones. `--reuse-db` avoids create cost but not memory. `--nomigrations` / `--no-migrations` speeds creation. Ref: https://pytest-django.readthedocs.io/en/latest/database.html#parallel-testing-with-pytest-xdist. Cut PostgreSQL's own memory on the dev machine (`shared_buffers`, `max_connections`) only if measurements show it matters; that is a machine config, out of scope for generic plugins.
- **Playwright**: pytest-playwright launches a browser per session per worker (the `browser` fixture is session scoped, `context`/`page` function scoped). So N workers = N Chromium processes plus a context each. Reduce: run browser tests in a separate invocation with a lower worker cap (a tier, see `test_tiers.md`); use `--browser chromium` only (not all three); keep headless; avoid `--video`/`--tracing` on by default; `--headed` is much heavier. Ref: https://playwright.dev/python/docs/test-runners. Ensure contexts and pages are closed so memory does not grow across a long run.
- **Python worker memory growth**: `--max-worker-restart` only controls crash replacement. To bound growth from leaks, pytest-xdist has no "recycle after N tests" option; the plugin `pytest-forked` (`--forked`) is heavy and incompatible with Django DB connections; skip. Simply lower worker counts.
- `--maxprocesses=N` caps `-n auto`; a static cap is a valid cheap safety net in pyproject (`addopts`), e.g. 8, independent of dynamic sizing.
- `-p no:cacheprovider` is not helpful; leave the cache on since the retry design reads it.

## 7. Limiting agent/subagent fan-out by memory

- Each Claude Code subagent runs in the same Node process (subagents are in-process tasks in the session), so spawning fan-out does not multiply Node processes much; the memory problem comes from the commands those agents run, chiefly the test suite, linters and browsers. VERIFY architecture before designing a fan-out throttle.
- Therefore the highest-impact control is making test invocations self-limiting (sections 1-5), since that is what runs concurrently across batches and worktrees. Limiting `Parallel batches` by memory is a secondary option: compute the batch count at fan-out time from MemAvailable, `min(configured, floor(avail / per_batch_estimate))`, with `per_batch_estimate` equal to one test run's budget. As the batch runs tests with its own gate, this largely duplicates the gate. Recommended: apply the check in the test script only, and treat fan-out throttle as optional.
- A prompt-level instruction in the command ("check memory with the script before launching more than N agents") is unreliable; a script the command always calls is better. Commands in the generic plugin may call a script path and read a threshold from `.claude/sdd/config.md`.

## 8. Plugin design implications (generic plugins)

- Put the memory probe and worker-sizing logic in a generic script under `claude_plugins/django-stack/scripts/` (next to `select_tests.py`), with defaults in the script, overrides from a pyproject `[tool.*]` table (the project already uses `[tool.test_tiers]`), and per-machine env var override (e.g. a plugin-named env var; no FLS names). Keep stdlib only if possible: `/proc/meminfo` read on Linux, `vm_stat`/`sysctl` on macOS, fail open elsewhere.
- Keep per-worker memory numbers and Playwright specifics as project config values, not plugin defaults tied to this project.
- Thresholds worth exposing: `per_worker_mb`, `reserve_mb`, `min_workers`, `max_workers`, `wait_timeout_s`, `max_retries` (default 2), `swap_used_ratio_limit`, `psi_some_avg10_limit`.

## References
- https://www.kernel.org/doc/html/latest/filesystems/proc.html (MemAvailable)
- https://docs.kernel.org/accounting/psi.html (PSI)
- https://docs.kernel.org/admin-guide/cgroup-v2.html (memory.max, memory.current)
- https://psutil.readthedocs.io/en/latest/ (virtual_memory, swap_memory)
- https://pytest-xdist.readthedocs.io/en/stable/ (distribution, known limitations, crash handling, `--maxprocesses`, `--max-worker-restart`)
- https://docs.pytest.org/en/stable/how-to/cache.html (`--lf`, cache)
- https://docs.pytest.org/en/stable/reference/exit-codes.html
- https://pytest-django.readthedocs.io/en/latest/database.html (xdist DB names, `--reuse-db`)
- https://playwright.dev/python/docs/test-runners
- https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/

status: ok
