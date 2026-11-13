# Known complaints: RAM exhaustion in parallel tests and agent fan-out

Evidence quality: web search summaries (several vendor blogs, mirrored GitHub issues). Items marked (unverified) are my inference or a single weak source. Check before quoting in the spec.

## 1. pytest-xdist: `-n auto` oversubscription

Complaints:
- `-n auto` sizes by CPU cores (physical by default; `-n logical` for logical), never by memory. CircleCI support warns it "may lead to resource overuse and errors". On this machine that is 16 workers on a box already running ~9 worktrees, Chrome, a VM and 20 GB of swap.
- Override exists: env var `PYTEST_XDIST_AUTO_NUM_WORKERS` changes the auto count. This is the natural hook for a computed worker count (no need to rewrite `-n auto` in every caller).
- Each worker is a full Python + Django process (plus a DB connection, plus Chromium for Playwright tests). Memory scales roughly linearly with workers (inference, unverified; measure RSS per worker on this repo).

Design should: compute `workers = min(cpu_count, floor((MemAvailable - headroom) / per_worker_estimate))`, floor at 1, export it via `PYTEST_XDIST_AUTO_NUM_WORKERS` or pass explicit `-n`. Make `per_worker_estimate` and `headroom` the overridable thresholds (pyproject `[tool.*]` plus env var).

Refs: https://pytest-xdist.readthedocs.io/en/stable/distribution.html , https://support.circleci.com/hc/en-us/articles/49277796780571-Configuring-CPU-Parallelism-for-pytest-in-CircleCI

## 2. Worker crash messages and telling them apart from test failures

- A killed worker shows as `worker 'gwN' crashed while running '<nodeid>'` and/or `node down: Not properly terminated`. It means the process died with no Python teardown (OOM SIGKILL, segfault, other fatal signal). A report calls resource exhaustion the most common cause. The test named is only the one running when the worker died, and it is not necessarily the memory hog.
- xdist auto-restarts the crashed worker and reports the running test as failed. `--max-worker-restart=N` caps restarts. After many crashes some users see follow-on `INTERNALERROR ... KeyError WorkerController` (see sparkless report), which is noise, not the root cause.
- Complaint: the crash looks identical to a genuine failure in the summary, so humans and agents rerun the whole suite or "fix" the named test.
- Confirmation signal: kernel log (`dmesg` / `journalctl -k`, "Out of memory: Killed process") at the crash time. Often not readable without privileges (unverified on this machine). Cheaper signals: the crash text above, plus the worker exit signal being SIGKILL (-9).

Design should: classify the run as a crash when the output contains `crashed while running` / `Not properly terminated` (and not a normal assertion failure), separate crashed-test ids from assertion failures, and never present crashed tests as failures to fix. Consider `--max-worker-restart=0` (or a small number) so a memory death stops the run quickly instead of limping on with restarts that die again.

Refs: https://pytest-xdist.readthedocs.io/en/stable/_sources/crash.rst.txt , https://adhdecode.com/debugging/pytest/xdist-worker-crashed-unexpectedly/ , https://sparkless.readthedocs.io/en/latest/robin_mode_worker_crash_investigation.html , https://bugs.gentoo.org/924416

## 3. `--lf` after a crash (unverified, test it)

- I found no source. From my knowledge of pytest's cache plugin: `--lf` reruns ids recorded as failed in `.pytest_cache`. A crashed test is recorded as failed, but tests that were queued and never ran on a dead worker are not marked failed, so `--lf` would rerun only the crashed one(s) and silently skip the never-run ones. Also a later partial run can overwrite the lastfailed set.
- Implication: `--lf` is the wrong resume mechanism for "rerun only tests that never finished" (the user's answer). The design needs its own record: collect all node ids (`--collect-only -q`), record per-test completion (e.g. a small report plugin / junit XML / `-rA` results), and rerun `all - finished`. Rerun set = never-finished tests plus the crashed test(s).
- The spec should include a spike that verifies actual `--lf` behavior with a killed worker before relying on either approach.

## 4. Leaked processes after a crash

- Killed xdist workers can orphan children: Chromium processes from Playwright, `uv run` wrappers, Postgres backends tied to leftover connections. Gentoo report ties crashes to long-lived execnet gateways (weak).
- Claude Code has its own leak reports (below): background bash runner re-exec leaks, subagents not cleaned up.

Design should: run pytest in its own process group/session (e.g. `setsid`/`start_new_session`) and on abort or before retry kill the whole group, then check no `chromium`/`headless_shell` descendants remain before measuring free RAM again. Measure RAM after cleanup, otherwise the retry sees leaked memory and backs off forever or retries into the same wall.

## 5. Postgres connection and DB clone limits

- Each xdist worker makes its own test DB (`test_<db>_gwN`, pytest-django) and holds connections. Default `max_connections=100`; with many workers plus Django threads or pools one write-up hits `FATAL: sorry, too many clients already` at ~12+ workers (SQLAlchemy-based, so only indicative for Django). With ~9 worktrees on one Postgres, each running up to 16 workers, the shared server could exceed 100 across worktrees even though the user chose no cross-worktree lock.
- Template-clone approaches fail when the template DB has another open connection (`source database is being accessed by other users`). Django has a ticket on parallel DB clone failures with TimescaleDB.
- Clone cost: 16 clones of the DB per run is time and disk. Fewer workers reduces this too, so memory-driven worker reduction also helps connections.
- Postgres backends use RAM themselves (shared_buffers is shared; per-backend work_mem).

Design should: cap workers also by `max_connections` headroom if cheaply readable (optional, low priority), and treat "too many clients" / "being accessed by other users" as a distinct infrastructure error: report it, retry with fewer workers, do not treat it as a test failure. Lower priority than RAM.

Refs: https://habr.com/ru/articles/1047134/ , https://mergify.com/blog/postgres-database-per-test-sqlalchemy , https://pytest-django.readthedocs.io/en/stable/database.html , https://groups.google.com/g/django-updates/c/XuhWxAm07pc

## 6. Playwright memory per worker

- Each worker launches its own Chromium; guides cite hundreds of MB per browser plus per-page renderer processes (numbers are vendor-blog estimates, unverified; measure here). Standard advice: cut workers (2 to 4 per machine), scale out by sharding instead. Docker: `/dev/shm` too small gives Chromium crashes (`--disable-dev-shm-usage`); mostly irrelevant on a bare Linux host.
- Browser OOM looks like a Playwright "Target crashed" / "browser has been closed" error, not an xdist worker crash, because the kernel may kill Chromium (a large process, picked first) rather than the Python worker. That makes memory deaths look like real UI test failures.

Design should: treat Playwright/browser tests as a heavier class: separate, lower worker cap (or run in their own section after the unit tier), with a larger per-worker estimate. Add "Target crashed", "Browser closed", "Page crashed" to the infrastructure-failure patterns so they are not read as test bugs. Hook points: the tiers in `claude_plugins/django-stack/resources/test_tiers.md` and `[tool.test_tiers]` in pyproject.toml.

Refs: https://webcrawlerapi.com/glossary/playwright/how-to-fix-playwright-worker-memory-crashes , https://currents.dev/posts/playwright-ci-at-scale-github-gitlab , https://dev.to/rendershot/headless-chromium-at-scale-four-fixes-for-a-fleet-that-kept-eating-ram-1mdp

## 7. Auto-retry masking flaky or genuinely failing tests

- Complaints about pytest-rerunfailures: reruns hide real bugs and flaky tests, make suites slower, and under xdist can hide order-dependent failures (failure moves between tests each rerun). Source is a flaky-test-tooling vendor (Mergify), so possibly biased, but the concern is widely held.
- Relevant risk here: a retry loop that reruns "failures" would rerun genuine failures and eventually pass a flaky one, or burn time re-running a real bug twice.

Design should: retry ONLY on a classified infrastructure death (worker crash, kernel OOM signature), never on an assertion failure/test error. Rerun only never-finished tests; keep results of tests that already finished (including failures) and merge them into the final report. Cap at 2 retries (as answered). Print every retry loudly ("run crashed from memory; retry 1/2 with N workers, M tests remaining") so it is never silent, and make the final exit code reflect genuine failures from any attempt. A test that fails in attempt 1 for a real reason must stay failed.

Refs: https://mergify.com/learn/flaky-tests/pytest , https://mergify.com/blog/pytest-xdist-ordering-races , https://pytest-rerunfailures.readthedocs.io/

## 8. Waiting loops that hang forever

- General failure mode (my knowledge, not from a source): "wait until RAM is free" loops with no deadline hang when something else (a Chrome tab, a VM, a leaked process) holds the memory permanently. In an agent context a hung bash call blocks the whole SDD command; Claude Code tool calls also have timeouts, so an unbounded wait may be killed mid-loop without cleanup.
- With 20 GB of swap in use at a quiet moment, free RAM may never reach a high bar.

Design should: bounded wait (max total seconds, poll interval, both configurable), then proceed with a reduced worker count (down to 1) rather than failing or waiting forever; log what it decided. Decide on progress: if the wait times out, the safest fallback is `-n 1..2` and an explicit message, not abort. Make the loop non-interactive and killable by SIGINT/SIGTERM with cleanup.

## 9. MemAvailable misleading with swap, page cache and zram

- `MemAvailable` estimates memory available without swapping, counting reclaimable page cache. Complaints: (a) Cached includes non-freeable memory (shmem, tmpfs, ramfs), so MemAvailable can overstate; (b) with swap, the kernel will page out anonymous memory to make "available" memory, so a machine with 20 GB swap used is already under pressure while MemAvailable looks fine; (c) with zram the SwapFree slot count is inaccurate; (d) systemd-oomd had a bug counting cache as used (Ubuntu fixed it by using MemAvailable instead of MemFree).
- Failure mode for us: MemAvailable high yet the machine thrashes (swap-in/out), tests become very slow or get killed. And the reverse: it may read low because of a big page cache after a big build, causing needless waits.
- Better signals: PSI (`/proc/pressure/memory`, `some avg10`/`full avg10`) shows actual stall time, and is the signal earlyoom/systemd-oomd-style tools use; also swap usage (`SwapTotal - SwapFree`) and swap-in rate (`pswpin` in `/proc/vmstat`). Check PSI exists (needs kernel CONFIG_PSI; fine on kernel 7.x) and fall back to MemAvailable if absent.

Design should: use MemAvailable as the primary sizing input (simple, portable), but also (a) subtract or penalize heavy swap usage, (b) gate the start on PSI `some avg10` below a threshold when available, (c) make all thresholds configurable, (d) print the numbers it read. Do not use MemFree. Note that on this machine swap-in-use is high at idle, so a naive "swap used > X means wait" check would wait forever: use swap-in rate / PSI, not absolute swap used.

Refs: https://chrisdown.name/2026/03/24/zswap-vs-zram-when-to-use-what.html , https://lists.snapcraft.io/archives/foundations-bugs/2022-April/472213.html , https://bugs.launchpad.net/bugs/1978738 , https://oneuptime.com/blog/post/2026-07-31-memfree-vs-memavailable/markdown , https://lkml.iu.edu/hypermail/linux/kernel/2603.0/04407.html

## 10. Claude Code parallel subagents exhausting RAM (GitHub issues, anthropics/claude-code)

Issue titles as mirrored on claudeissues.com (confirm numbers on GitHub before citing):
- #70523 (open): kernel OOM from parallel subagent + per-agent MCP fan-out; ~6 subagents launched ~70 node processes, ~43.5 GB RSS; no aggregate memory ceiling or concurrency cap. https://claudeissues.com/issue/70523-bug-kernel-oom-not-v8-heap-from-parallel-subagent-per-agent-mcp-fan-out-exhausts
- #69033 (open): request for memory-aware throttling; fan-out of ~84-92 subagents crashed host; the cap is count-based, min(16, cores-2). https://claudeissues.com/issue/69033-workflow-harness-memory-aware-throttling-when-fanning-out-subagents
- #74035 (open): deeply nested subagent fan-out, one CLI process 1.7 GB to 26 GB RSS in ~10 min. https://claudeissues.com/issue/74035-deeply-nested-subagent-fan-out-causes-unbounded-memory-growth-host-level-oom
- #74001: OOM under multi-subagent load, subagent CLI processes grow to 6.5 GB RSS each. https://claudeissues.com/issue/74001-oom-crash-under-multi-subagent-load-subagent-cli-processes-grow-to-6-5-gb-rss-ea
- #64751 (open): workflow subagents balloon to ~2 GB each and are not cleaned up (regression 2.1.156 to 2.1.160). https://claudeissues.com/issue/64751-bug-workflow-subagents-balloon-to-2gb-each-and-arent-cleaned-up-regression-2-1-1
- #32623: excessive memory with multiple subagents causes system hang. https://claudeissues.com/issue/32623-bug-excessive-memory-consumption-with-multiple-subagents-causes-system-hang
- #87319: 8 parallel background subagents; cgroup OOM kill; background bash runner leaks memory. https://claudeissues.com/issue/87319-background-bash-runner-process-re-execd-versioned-binary-leaks-memory-after-comm
- #62193 (closed): thousands of parallel bash processes in 17 s caused OOM. https://claudeissues.com/issue/62193-bug-claude-code-spawned-3-000-parallel-bash-processes-in-17-seconds-causing-oom
- #18471, #19100, #16470 (V8 ~4 GB heap exhaustion with parallel Explore/Task agents); #27788 (subagents inherit unbounded V8 heap reservation, resolved); #15487 (feature request: `maxParallelAgents` setting).
- Common thread: no aggregate memory ceiling; concurrency limits are count-based; each subagent is a separate Node process (hundreds of MB to GB, growing), and MCP servers are started per agent.

Design should (for the SDD side): the plugin cannot change Claude Code itself, so it must limit its own fan-out: (a) check free RAM before launching a wave of workers/batches and size the wave (the existing `Parallel batches: 3` in `.claude/sdd/config.md` becomes an upper bound, reduced when RAM is low), (b) use a conservative per-subagent estimate (e.g. 1 to 2 GB, configurable, based on the issues above), (c) test runs inside those parallel batches multiply the load (3 batches times `-n auto` = up to 48 pytest workers), so each batch's test run should get its share of workers, not the whole machine's cores. This is the likely biggest single cause here: nested parallelism. The user chose per-run checks only, no cross-worktree lock, so the share must be derived from what is currently free at launch time, accepting some race.

## 11. OOM killer picking the wrong process

- Kernel picks by `oom_score` (mostly RSS + swap + `oom_score_adj`), so it kills the biggest process, not the one that caused the pressure. On a dev box that is often Chrome, the qemu VM, a Claude Code session or an IDE rather than the test run. Consequences: the user's work is lost; or the test suite survives and a different process dies, so the test run is not even the process that "failed". Conversely, a Chromium child or one xdist worker dies and the suite looks flaky.
- Userspace killers (earlyoom, systemd-oomd) may fire earlier and by their own rules; I found no concrete report of them mis-killing due to MemAvailable on zram, only the cache-counted-as-used bug above.
- Mitigation available without root: a process can raise its own `oom_score_adj` (up to 1000) but not lower it. So the test runner can write `/proc/self/oom_score_adj` = 500..1000 before spawning pytest (children inherit), making the test processes (and Playwright Chromium) the preferred victims instead of the user's browser, VM and Claude sessions. That makes crashes cheaper (a restartable test run dies rather than a session) and detectable by the crash classifier. This fits the user's goal and is a strong candidate. Trade-off: the test run dies more readily, so the back-off and resume logic must be good. Linux-only; skip silently on other platforms.
- Also `systemd-run --user --scope -p MemoryMax=...` can cap a run in its own cgroup (needs cgroup v2 user delegation; unverified here). Whole-group kill then stays contained. Optional, adds complexity; likely out of scope for a first version.

## Summary of what to build, in order of likely impact

1. Memory-aware worker count at pytest launch (`PYTEST_XDIST_AUTO_NUM_WORKERS` / `-n`), per-class estimates (plain vs Playwright), floor 1.
2. Share-aware sizing when SDD runs batches in parallel (nested parallelism is the multiplier).
3. Crash classifier + retry of only never-finished tests with fewer workers, max 2, loud, genuine failures preserved. Own completion record, not `--lf`.
4. Set `oom_score_adj` high on test processes so the kernel kills them, not the user's apps.
5. Bounded wait with a deadline and fallback to fewer workers; PSI as the pressure signal, MemAvailable for sizing.
6. Process-group cleanup before retries and measuring.

status: ok
