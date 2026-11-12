# Research: prior art for the RAM problem

Limits of this run: no shell was available, so `git log --grep` was NOT run. Everything "here" comes from reading `spec_dd/3. done/` and the current files. Web findings come from search-result summaries, not fetched pages, so treat numbers as unverified.

## Here: what was already tried

### 1. Four-worker cap on `-n auto` (done, in place)
- Introduced by `spec_dd/3. done/2026-10-01_09:40_database-keeps-going-down/` (spec 1. spec.md ~l.132, plan Slice 7, plan l.396). Root `/conftest.py` defines `pytest_xdist_auto_num_workers(config) -> int` returning `min(4, os.cpu_count() or 1)`. Tests: `tests/test_conftest.py` (8 and 16 cores give 4; 2 cores give 2; unknown gives 1).
- The reason given was DB load, not RAM: "what the shared dev server can serve" (Postgres connection slots and `template1` contention across worktrees). The spec says to revisit `max_connections` and the cap of 4 later (spec ~l.283).
- The hook only affects `-n auto` and `-n logical`. An explicit `-n 8` is not capped (spec l.133). `make-sdd-more-efficient` (plan l.53, 73, idea l.98) kept the cap and said "nothing to add".
- **Discrepancy to resolve before specifying:** the brief says `-n auto` spawns 16 workers. The root `conftest.py` in this worktree caps it at 4. Either the hook is not taking effect (check the xdist version, or whether the run is made with an explicit `-n`/`PYTEST_ADDOPTS`), or the observed RAM failures come from 4 workers x (Chromium + live server + DB clone) times several concurrent worktrees. The spec writer should measure the real worker count and per-worker RSS first. Note xdist docs say the hook beats the `PYTEST_XDIST_AUTO_NUM_WORKERS` env var, so an env var cannot override the hardcoded 4 today. A RAM-aware cap has to live in or replace this hook.
- CI uses `-n auto` too (`.github/workflows/tests.yml` l.88, l.183), so the hook also governs CI runners. Any RAM logic must not break there.

### 2. Test tiers and `select_tests.py` (done, no memory handling)
- `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/` created the targeted/full tiers. `claude_plugins/django-stack/scripts/select_tests.py` hardcodes `FULL_COMMAND = "uv run pytest -n auto"` and `TARGETED_PREFIX = "uv run pytest -n auto --no-cov"` (l.80-81). `resources/test_tiers.md` l.26 and l.61 repeat them (`--lf --no-cov`, append `-n auto`). The aim was speed and fewer full runs, not RAM. The research docs (`research_current_test_runs.md`, `research_test_selection_tools.md`) mention the shared dev Postgres and "concurrent full runs in multiple worktrees multiply connections" but never RAM or swap.
- Rules already in the testing skill: run the suite in the background, never start a second full run in the same worktree, a run can exceed 10 minutes. `addopts` in `pyproject.toml` l.90 has `--dist loadfile` (a module's tests share one worker). That matters for any "rerun only unfinished tests": rerun by node id and keep `loadfile`.
- `pytest-testmon` was considered and rejected as a gate (xdist/coverage interplay unverified).

### 3. Orphan process reaping (done, on-demand only)
- `database-keeps-going-down` Slice 9: `claude_plugins/django-stack/scripts/reap_playwright_mcp.sh [--kill]` (wrapper copies at `.claude/ds/scripts/` and `templates/wrapper_scripts/`; tests in `tests/test_reap_playwright_mcp.py`; `dev_db/diagnose.py` l.496, l.559 calls it).
- It lists Playwright MCP servers (and their browser descendants) that are orphaned (parent PID 1 or the user systemd subreaper), owned by the current user, older than 1 hour. It prints `pid age rss command`. `--kill` sends SIGTERM, waits 5 s, then SIGKILL. The `.mcp.json` pins `@playwright/mcp`.
- Decisions recorded in `research_agent_process_lifecycle.md`: keep it manual, not a cron job (an age kill could hit a deliberate background server); a `setsid`/process-group wrapper around pytest and `PR_SET_PDEATHSIG` were rejected as overkill; add `pytest-timeout`; pass an explicit Bash timeout for full-suite runs. Evidence cited there: Claude Code issues #84647 (an orphan reached 20 GB RSS and drove the host into swap exhaustion), #82433, #96625, #93996 (https://github.com/anthropics/claude-code/issues/84647). Also pytest-xdist issue #658: when a worker is OOM-killed the controller may not recover and worker-leaked processes are reparented (https://github.com/pytest-dev/pytest-xdist/issues/658).
- Gap: the reaper is about orphans of ended sessions, not about live memory pressure. It scopes to Playwright MCP, not pytest-launched Chromium or stray pytest workers.

### 4. SDD fan-out cap (`Parallel batches`)
- `spec_dd/3. done/2026-11-08_12:35_sdd-improvements-combine-steps/` added the `Parallel batches:` key under `## Worktree Scripts` in `.claude/sdd/config.md` (this repo sets 3; spec l.328). Read by `claude_plugins/sdd/commands/implement_plan.md` l.65-81 ("Cap"; batch wave = first `min(len(ready), cap)`). Blank/1 = sequential. Each batch in a wave of 2+ runs in its own git worktree (`isolation: "worktree"`) with the Setup script, so each has its own DB. A wave then runs the `targeted` tier after integration.
- Existing retry rule worth reusing: a batch gets at most two retries across all waves (implement_plan l.73), and a worker returning no status line counts as `failed` with reason `no return`. The user's "max 2 retries" matches this convention.
- The cap is a static number. Nothing reads free RAM. The spec's own todo (still unticked) was to prove a wave with `Parallel batches: 2`. No spec records RAM as a reason for 3.
- Other fan-outs (research workers, review waves) have no cap config at all in what I saw. `spec_review.md` has a "review wave". Check those commands for a count before specifying.

### 5. Postgres-side memory sizing (done)
- `research_server_sizing.md` in `database-keeps-going-down`: do not sum backend RSS (shared_buffers double counts, use Pss); worst case = shared_buffers + connections x work_mem multipliers. The dev DB is a shared container (port 6543), so each xdist worker's DB clone and connections add load there, but backends are small. This is a separate memory pool from pytest workers and Chromium.

### 6. Not found
- No spec in `spec_dd/3. done/` or `spec_dd/2. in progress/` (other than this one) tried RAM gating, OOM detection, backoff, or checkpoint/resume of a suite. Grep hits for "memory" were all Postgres sizing or unrelated. `--lf`, `--max-worker-restart`, `--maxprocesses` and `pytest-timeout` are not configured in `pyproject.toml` (confirm `pytest-timeout` against the dependency list; the lifecycle research recommended adding it and the CI step history suggests it may now exist).

## Elsewhere: what is known

All from search summaries (not fetched pages); cite-and-verify before relying.

1. **xdist behaviour on worker death.** xdist restarts a crashed worker and reports the running test as failed; `--max-worker-restart N` caps restarts, `0` disables. A "node down: Not properly terminated" with 12 workers was followed by an INTERNALERROR (KeyError in the scheduler, xdist issue #714); the workaround was fewer workers or `-n 0`. So a crash shows up as a failed test with a "worker crashed" message, which is the signature for the user's "tell a crash from a test failure" answer, and the controller can itself die. https://pytest-xdist.readthedocs.io/en/stable/_sources/crash.rst.txt , https://sparkless.readthedocs.io/en/latest/robin_mode_worker_crash_investigation.html , https://github.com/pytest-dev/pytest-xdist/issues/658
2. **Hugging Face transformers CI** found the cgroup limit, not host RAM, was the real constraint when pytest crashed and hung. Relevant if the guard reads `/sys/fs/cgroup` rather than `/proc/meminfo` (`MemAvailable`). https://lightrun.com/answers/huggingface-transformers-ci-solving-the-pytest-crashing-and-hanging-ci-job
3. **Worker count from RAM.** No built-in xdist option or well-known plugin does it. The documented route is the `pytest_xdist_auto_num_workers` hook (beats `PYTEST_XDIST_AUTO_NUM_WORKERS`), computing `min(cpu, MemAvailable // per_worker_estimate)`. Available memory is a better input than total. `--maxprocesses` caps `auto`/`logical`. https://pytest-xdist.readthedocs.io/en/stable/distribution.html , https://tessl.io/registry/tessl/pypi-pytest-xdist/files/docs/hook-specifications.md
4. **Kernel-side guards.** `systemd-run --scope -p MemoryMax=... -p MemorySwapMax=...` limits one command's cgroup. `MemoryHigh` throttles (reclaim pressure) and `MemoryMax` is the hard kill. Swap can mask a limit, so pair with `MemorySwapMax`. `systemd-oomd` is opt-in per cgroup (`ManagedOOMMemoryPressure=kill`, `ManagedOOMSwap=kill`) and needs cgroup v2. A too-tight limit can kill helper processes. No source tied these to pytest. The 39 GB swap (20 GB in use) on this machine means plain "free RAM" checks must consider swap and PSI: the box will thrash long before an OOM kill. Linux PSI (`/proc/pressure/memory`) is the signal that matches "about to thrash". https://braindetox.kr/en/posts/memoryhigh_vs_memorymax_build_throttle_linux.html , https://dev.to/lyraalishaikh/stop-linux-memory-death-spirals-early-practical-systemd-oomd-with-psi-and-cgroup-policy-369j , https://docs.aws.amazon.com/linux/al2027/ug/resource-limiting-systemd.html
5. **Orphans as a RAM cause.** Claude Code Bash timeouts and session crashes leak long-running child processes (one at 20 GB RSS). Pattern confirmed by several independent issues (see section 3). https://github.com/anthropics/claude-code/issues/84647 , https://github.com/anthropics/claude-code/issues/96625
6. **Not found:** no published write-up of many parallel AI agents plus test suites sharing one developer box with a RAM-aware scheduler, and no checkpoint/resume plugin for pytest beyond `--lf`/`--sw`. xdist `--sw` is unverified under `-n`; `--lf` works under xdist (computed in the controller).

## Takeaways for the spec

- The cheapest, proven lever is already half built: a worker cap in `pytest_xdist_auto_num_workers`. Making it RAM-aware (and project/env configurable) fits the user's thresholds answer. First confirm why 16 workers appear, given the cap of 4.
- Crash detection can use xdist output ("worker ... crashed", "node down") plus `--max-worker-restart 0` to fail fast, then rerun by node id with fewer workers. `--lf` alone would also rerun real failures, so it does not meet the "never retry real failures" answer.
- The SDD fan-out cap (`implement_plan.md` Cap) is the natural place to shrink the wave on low RAM, reusing its two-retry rule.
- Generic-plugin rule: the 4 in `/conftest.py` is a project value in a project file, so it stays in the project and can move to a `[tool.*]` table.

status: ok
