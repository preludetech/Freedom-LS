# Research: reference implementations for memory-aware parallelism and crash recovery

Method note: written from working knowledge of each tool's documented behaviour. No pages were fetched this session, and no tool was run on the dev machine. URLs are the canonical docs for each claim. Items marked (verify) should be checked against the pinned versions before the spec commits to them.

## Summary: what to take

| Mechanism | Fits a generic pytest wrapper? | Verdict |
|---|---|---|
| xdist `pytest_xdist_auto_num_workers` hook / `PYTEST_XDIST_AUTO_NUM_WORKERS` env var | Yes, as a conftest hook or env var set by the wrapper | Best way to cut workers when RAM is low |
| xdist `--maxprocesses` | Yes, a plain CLI cap | Simple fallback and good for the wrapper to pass |
| xdist `--max-worker-restart` | Yes | Set to 0 so the wrapper owns recovery, or leave the default |
| Wrapper-level wait, retry and backoff, modelled on GNU parallel `--memfree` | Yes, this is the core | Take the semantics: do not start below X, back off, requeue |
| pytest-rerunfailures | Partly | Wrong layer: no memory awareness, no worker-count reduction |
| pytest-split / pytest-shard | Partly | Useful only for resumable sections |
| cargo-nextest retries and backoff config | Design reference only | Copy the config shape (count, delay, exponential, jitter) |
| Bazel `--local_resources` | Design reference only | Copy the `HOST_RAM*.5` expression idea |
| systemd-run / cgroup `MemoryMax` | Optional, Linux only | Gives a clean OOM signal and protects the rest of the machine |
| earlyoom / systemd-oomd | No (system daemons) | Out of scope for the plugin; mention as a user-side option |

## 1. pytest-xdist

Docs: https://pytest-xdist.readthedocs.io/en/stable/distribution.html, https://pytest-xdist.readthedocs.io/en/stable/how-to.html, https://pytest-xdist.readthedocs.io/en/stable/known-limitations.html, https://pytest-xdist.readthedocs.io/en/stable/crash.html, hook reference at https://pytest-xdist.readthedocs.io/en/stable/api.html

### Worker count

- `-n auto` uses the physical core count when `psutil` is installed, otherwise `len(os.sched_getaffinity)`/`os.cpu_count()`. `-n logical` uses logical cores. Neither looks at RAM. On the 16-core machine `-n auto` therefore gives 16 workers regardless of free memory.
- `--maxprocesses=N` caps the count that `auto`/`logical` produce. It does nothing with explicit `-n 8`. Example: `pytest -n auto --maxprocesses=6`.
- Hook, in conftest or a plugin:

```python
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    # called only when -n auto / logical
    ...
    return n
```

  The hook is invoked only for `auto`/`logical`. It is the supported place to compute `min(cores, (MemAvailable - reserve) // per_worker_estimate)`.
- Env var `PYTEST_XDIST_AUTO_NUM_WORKERS=N` overrides the auto count without code (verify the minimum version). The wrapper can compute N and export it, or pass `-n N` directly. Passing `-n N` is the more transparent choice: the chosen count is visible in the command line.
- A conftest hook lives in the project's tests, so it is not generic-plugin content unless the plugin ships it. A wrapper script that computes N and passes `-n N` needs no conftest and fits the generic-plugin constraint better.

### Crash behaviour

- When a worker process dies (OOM-killer SIGKILL, segfault), the controller prints `worker 'gwN' crashed while running '<nodeid>'`, marks that one test as failed (report text "node down: Not properly terminated" / "worker crashed"), and starts a replacement worker (`replacing crashed worker gwN`). Tests that were pending on that worker are rescheduled.
- `--max-worker-restart=N` limits the number of replacements; the default is 4x the number of workers. When the limit is exceeded the run aborts with "maximum crashed workers reached". `--max-worker-restart=0` disables replacement.
- Implication for the answers.md requirement ("tell a worker crash apart from a test failure"): the crash is distinguishable in the output by the `crashed while running` / `node down` text, and in the JUnit XML or reportlog by the report's longrepr. A stable route is `--report-log=FILE` (pytest-reportlog, JSON lines) or `-p` plugin/conftest hook `pytest_handlecrashitem(crashitem, report, sched)` (xdist hook, exists in the xdist API; verify) which fires with the crashing nodeid. Only the item running at crash time is reported as crashed; others that were queued are rerun by xdist automatically, so "rerun only tests that never finished" mostly means: rerun the crashed test plus whatever never got a report.
- Because the replacement worker comes up under the same RAM pressure, xdist's own restart loops; this is the main failure to fix, and xdist has no backoff or worker reduction.
- Each worker is a full Python process plus a cloned test DB connection. Per-worker RSS for a Django project with Playwright is large (Chromium per worker adds several hundred MB). The per-worker estimate should be measurable: a wrapper can sample RSS of the `gw*` processes during a run (psutil children of the pytest PID) and persist the high-water mark to adapt the next run (optional, adds scope).

### Distribution modes relevant to resume

- `--dist load` (default), `loadfile`, `loadscope`, `worksteal`, `each`. Not memory related. `loadfile` keeps a file's tests on one worker, which reduces repeated fixture set-up and DB-clone cost.

## 2. pytest-rerunfailures

Docs: https://github.com/pytest-dev/pytest-rerunfailures

- `--reruns N`, `--reruns-delay SECONDS`, `--only-rerun REGEX`, `--rerun-except REGEX`, marker `@pytest.mark.flaky(reruns=2, reruns_delay=1)`.
- Reruns a failed test in-process after the failure report. Crashed-worker reruns under xdist are supported in recent versions (verify the version that added it; it rescues the crashed item on the replacement worker).
- Not suitable as the main mechanism: it has a fixed delay only (no exponential backoff, no RAM check), it retries genuine test failures too (hides real failures unless restricted with `--only-rerun`), and it does not reduce worker count. It would also change test semantics for the whole project. Treat as a rejected alternative.

## 3. pytest-split and pytest-shard

- pytest-split: https://github.com/jerry-git/pytest-split. `--splits N --group K` runs the K-th of N groups. `--store-durations` writes `.test_durations` (JSON, nodeid to seconds); `--splitting-algorithm duration_based_chunks|least_duration`. Balanced by recorded duration.
- pytest-shard: https://github.com/AdamGleave/pytest-shard. `--shard-id=I --num-shards=N`, assignment by hash of the nodeid, so no stored data but unbalanced.
- Both only select tests deterministically. Neither checkpoints or resumes. For "run in sections with checkpoints", the wrapper would loop over groups and record which groups passed (e.g. a small JSON file in a temp dir). Each section is a fresh pytest process, which also frees memory leaked by long runs and gives natural points to re-check RAM. Costs: per-section start-up and DB-clone overhead (Django test DB creation per worker), and an extra dependency. The repo already has `claude_plugins/django-stack/scripts/select_tests.py`; check whether it can emit nodeid lists for sectioning without a new plugin.
- A dependency-free alternative to resume: pytest's built-in cache `--lf` / `--ff` (`.pytest_cache/v/cache/lastfailed`). Under xdist `--lf` works but the cache records the crash-failed test and real failures together, so it reruns real failures too. Hence a reportlog-based "never finished" computation is more precise: finished = nodeids with a `call` report; unfinished = collected minus finished (use `--collect-only -q` for the collected set).

## 4. GNU parallel: `--memfree` and `--memsuspend` (best semantic model)

Docs: https://www.gnu.org/software/parallel/parallel.html (options `--memfree`, `--memsuspend`), man page also at https://manpages.debian.org/parallel

- `--memfree SIZE`: do not start another job unless at least SIZE memory is free. "If less than 50% of SIZE is free, the youngest job is killed (per `--term-seq`) and put back on the queue to be run later." Also the check before every start; there is a minimum that guarantees one job always runs, so the queue cannot deadlock (verify detail).
- `--memsuspend SIZE`: suspend (SIGSTOP) the youngest job when memory falls below SIZE, resume (SIGCONT) when free again. Not appropriate for a pytest run: a stopped worker holds its RAM.
- "Free" in GNU parallel is the sum of free + cache/buffers (like `MemAvailable`).
- Take-aways for the spec: (a) check before start; (b) kill-and-requeue the youngest unit on severe pressure rather than letting the kernel pick a victim; (c) always allow at least one unit to run to avoid starvation; (d) requeue means retry, which matches the answers.md retry requirement.
- GNU parallel as a dependency: not generic for a Python wrapper, and it works on commands, not xdist workers. Use the semantics, not the tool. For SDD fan-out of subagents, there is no process to throttle from a script; a wrapper cannot limit Claude Code subagents, only the command's prompt can (e.g. reduce batch size when `MemAvailable` is low, read via a small script).

## 5. Bazel, Ninja, Make

- Bazel: https://bazel.build/reference/command-line-reference#flag--local_resources. `--local_resources=memory=HOST_RAM*.67` (older name `--local_ram_resources=HOST_RAM*.67`, deprecated), `--local_resources=cpu=HOST_CPUS-1`, `--jobs`. Actions declare a resource set; the scheduler only starts actions whose declared RAM fits the remaining budget. Tests can be tagged with `cpu:N`/`resources:memory:N` (`--test_*` and `size` presets, `size=large` implies bigger estimates). Also `--flaky_test_attempts=N` and `--test_timeout`. Lesson: budget = fraction of host RAM as an expression, plus per-unit estimates; the config shape "RAM budget as a fraction" is a good default for a pyproject table, e.g. `reserve_gb`/`per_worker_gb`.
- Ninja: https://ninja-build.org/manual.html. `-j N`, `-l MAX_LOAD` (load average; start no new jobs while load is above), and "pools" (`depth`) to cap concurrency of heavy rule classes. No memory awareness. Lesson: load average as a throttle is a weak proxy for memory.
- Make: `-j N -l LOAD`. Same, no memory.
- Neither is a fit for pytest directly.

## 6. cargo-nextest

Docs: https://nexte.st/docs/configuration/ and https://nexte.st/docs/features/retries/

- Retries and backoff in `.config/nextest.toml`:

```toml
[profile.default]
retries = { backoff = "exponential", count = 3, delay = "1s", max-delay = "10s", jitter = true }
test-threads = "num-cpus"        # or a number, or "-2"
```

- `threads-required = N` per test (override by filter), so heavy tests count as N slots: this is the closest thing to per-test memory weight. Test groups with `max-threads` cap concurrency for a class of tests.
- Distinguishes a test that fails from one that is killed by a signal (reports `SIGKILL` / "signal 9" status), and flags "flaky" when a retry passes. `--partition count:1/3` or `hash:1/3` for sharding.
- Lesson: retry policy as a small structured config (count, delay, exponential backoff, jitter, max delay), and a distinct report state for signal kills. The user's "max 2 retries" maps to `count = 2` with an exponential delay.

## 7. systemd-run and cgroup memory limits

Docs: https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html, https://docs.kernel.org/admin-guide/cgroup-v2.html

- Run the whole test run in a transient scope:

```
systemd-run --user --scope -p MemoryHigh=16G -p MemoryMax=20G -p MemorySwapMax=0 -- uv run pytest -n 8
```

  - `MemoryHigh` throttles and reclaims aggressively when crossed (soft, no kill); `MemoryMax` is the hard limit and invokes the cgroup OOM killer; `MemorySwapMax=0` stops the run from pushing the shared 39 GB swap further (swap is at 20 GB already, so swap thrash is probably the real cause of the freezes). `ManagedOOMSwap`/`ManagedOOMMemoryPressure` are the systemd-oomd knobs.
  - Without `memory.oom.group` (`OOMPolicy=kill` makes the whole unit die; verify default for scopes), the kernel kills the biggest process in the cgroup, which for xdist is typically one worker, which xdist then reports as a crash. With `OOMPolicy=kill`/`memory.oom.group=1` the whole run dies at once.
  - Crash detection: the cgroup file `memory.events` has an `oom_kill` counter (`oom_kill N`). After the run, the wrapper can read it (path from `/proc/self/cgroup` or `systemctl --user show -p ... <scope>`) and know that an OOM kill happened, instead of guessing from worker text. Exit status 137 or a worker killed by SIGKILL is the fallback signal.
  - Needs cgroup v2 with the memory controller delegated to the user manager (usual on modern systemd distributions, not guaranteed; check `cat /sys/fs/cgroup/user.slice/user-$UID.slice/user@$UID.service/cgroup.controllers`). Linux-only: needs a feature test with a graceful no-op elsewhere.
- Benefit: it protects the other eight worktrees, Chrome and the VM from the test run. Cost: it makes OOM deaths certain rather than less likely, so it must come with the retry loop. Treat as an optional layer, off by default, enabled by a `[tool.*]` setting or env var.

## 8. earlyoom and systemd-oomd

- earlyoom: https://github.com/rfjakob/earlyoom. `earlyoom -m 5 -s 5` sends SIGTERM when available RAM and free swap are both below 5%, SIGKILL at half that; `--prefer REGEX` / `--avoid REGEX` bias victim choice (e.g. prefer `chrome|chromium|pytest`, avoid `claude|code`). Daemon, needs root, system-wide. Not something a plugin can install; a docs note ("run earlyoom with `--prefer`/`--avoid`") is the most it can do.
- systemd-oomd: https://www.freedesktop.org/software/systemd/man/latest/systemd-oomd.service.html. Uses PSI (memory pressure) per cgroup. Same: system config, not a plugin concern.

## 9. Reading memory correctly on this machine

- `/proc/meminfo`: `MemAvailable` (kernel estimate of memory available without swapping), `SwapTotal`, `SwapFree`. Python: `psutil.virtual_memory().available`, `psutil.swap_memory()`. `psutil` may not be a project dependency; parsing `/proc/meminfo` is dependency-free and Linux-only (the machine is Linux; add a no-op fallback elsewhere).
- Problem for this machine: with 20 GB swap already used, `MemAvailable` can look healthy while the system is thrashing, since cold pages were swapped. A better pressure signal is PSI: `/proc/pressure/memory` lines `some avg10=X avg60=Y avg300=Z total=N`. A wait-for-RAM gate could use both: `MemAvailable >= need` and `some avg10 < threshold` (kernel 4.20+, needs PSI enabled; Linux 7.0 here). Worth putting in the spec as an optional second condition (Facebook/Meta's oomd and systemd-oomd use the same signal: https://docs.kernel.org/accounting/psi.html).
- Free swap is also a good condition: do not start while swap used is above some fraction.

## 10. Suggested shape for a generic wrapper (from the above)

1. Gate: poll `MemAvailable` (and optionally PSI) until `>= reserve + workers * per_worker` or a timeout; at least one worker always allowed (GNU parallel's non-starvation rule).
2. Size: `workers = clamp(1, min(cores, (avail - reserve) // per_worker), max_workers)`; pass as `-n workers` (and `--maxprocesses` is then unnecessary).
3. Run with `--report-log` to a temp file (or JUnit XML) and `--max-worker-restart=0` (or a small value) so a crash ends the run quickly instead of xdist restarting under the same pressure.
4. Classify: OOM crash if worker-crash text / signal 9 / cgroup `oom_kill` increased; otherwise a normal failure, passed through with no retry.
5. Retry: up to 2 times, exponential backoff (nextest shape), recompute the worker count (halve or recompute from fresh RAM), run only the nodeids with no result (collected minus finished) plus the crashed one.
6. Config: plugin defaults in a script, overridable by a `[tool.<name>]` table in pyproject.toml (`reserve_gb`, `per_worker_gb`, `max_retries`, `backoff_seconds`, `wait_timeout_seconds`), and per-machine by an env var (e.g. a `*_RESERVE_GB`-style variable named by the plugin, no FLS name).
7. SDD fan-out: no throttle is possible from a script; the command can call the same script's "available workers" mode to pick the effective batch count, bounded by `Parallel batches` in `.claude/sdd/config.md`.

## Open questions for the spec writer

- Which xdist version is pinned (check `uv.lock`) for `PYTEST_XDIST_AUTO_NUM_WORKERS`, `pytest_handlecrashitem`, and rerunfailures crash support.
- Is `psutil` already in `uv.lock`? If so `-n auto` is already physical-core-based and `psutil` is free to use.
- Whether the Playwright tests (Chromium per worker) need a heavier per-worker estimate than the unit tier: nextest `threads-required` suggests a per-tier weight (see `[tool.test_tiers]`).
- Is cgroup delegation available on the user manager? If not, drop the systemd-run layer.

status: ok
