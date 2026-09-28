# Research: do agent-run test processes outlive their agents?

Scope: this file covers only the process-lifecycle half of the hypothesis in `idea.md` — how Claude
Code (and `uv run`, pytest-xdist, Playwright) start and stop shell commands, and whether that leaks
`pytest`/Chromium processes that go on holding Postgres connections. It does not re-derive the
Postgres-side failure modes; see `research_postgres_failure_modes.md` and
`research_current_dev_db_setup.md` for those.

## Bottom line

**The mechanism is real and partly self-inflicted by design, but nobody has caught it in the act in
this repo yet.** Claude Code's own docs say a Bash command that times out is *not* killed — it is
moved to the background and keeps running. Nothing in this repo's commands/skills passes an explicit
timeout for the full suite, so every `uv run pytest` invoked by an agent is a candidate for exactly
that path, given the suite's size (100+ non-Playwright test files, ~19 Playwright test files across
7+ apps). Separately, several open Claude Code GitHub issues report the *bug* version of this problem
— timeout/session-kill paths that fail to kill the whole process tree, on top of the *by-design*
backgrounding. Both point the same way. What's missing is a `pg_stat_activity` or `ps` snapshot taken
at the moment this repo's dev DB actually went down, tying a specific leaked PID to a specific
Postgres connection — the diagnostics in §5 are how to get that, not a substitute for it.

---

## 1. Default/max Bash timeouts, and what happens on timeout, Esc, and subagent stop

**Confirmed, from Claude Code's own docs (code.claude.com):**

- Default timeout: `BASH_DEFAULT_TIMEOUT_MS` = 120000 (2 minutes). Ceiling the model can request:
  `BASH_MAX_TIMEOUT_MS` = 600000 (10 minutes); "the effective ceiling is the larger of this and
  `BASH_DEFAULT_TIMEOUT_MS`." Neither is set anywhere in this repo (`.claude/settings.json`,
  `claude_plugins/**`) — confirmed by grep, see §3.
  Source: https://code.claude.com/docs/en/env-vars

- **On timeout, Claude Code does not kill the command.** Verbatim from the tools reference:
  > "When a command reaches its timeout without finishing, Claude Code moves it to the background
  > instead of stopping it, unless the command starts with `sleep`. Claude keeps working while the
  > command continues. Claude Code applies the same lifetime rules to a moved command as to any other
  > background command, so it still ends a foreground subagent's command at that subagent's final
  > response."
  The result message it returns is literally `Command did not complete within its 120s timeout and
  was moved to the background`, with a task ID.
  Source: https://code.claude.com/docs/en/tools-reference

- **What "background" means for lifetime:** "A command that a foreground subagent started stops when
  that subagent gives its final response. A command that the main conversation or a background
  subagent started keeps running after a final response." So a full-suite run that a *foreground*
  subagent (e.g. `qa-bugfixer`, a `sdd-worker`) auto-backgrounds on timeout is torn down when that
  subagent's turn ends — but a run started by the depth-0 orchestrator itself, or by an explicitly
  background-spawned subagent, is **not** torn down when a turn ends; it is tracked as an
  ongoing background task instead.
  Source: https://code.claude.com/docs/en/tools-reference

- **Under `claude -p` (headless), background tasks are cleaned up on exit — with a signal caveat.**
  "If Claude starts a background Bash task during a `claude -p` run… that shell is terminated about
  five seconds after Claude has returned its final result and stdin has closed." And: **"On SIGTERM,
  Claude Code terminates the process tree of any Bash command that is still running."** But SIGTERM
  is a *cooperative* signal — it only fires this cleanup if something sends SIGTERM (or the run ends
  normally). A **SIGKILL**, a killed terminal, a crashed harness process, or a machine sleep does not
  give Claude Code the chance to run that cleanup at all; the docs don't claim otherwise.
  Source: https://code.claude.com/docs/en/headless

- **Esc / user interrupt and subagent-stop mechanics are not documented at the process level.** The
  docs describe the task-list UI ("when a subagent fails or you stop it, Claude Code keeps its row for
  30 seconds") and note a background subagent's leftover Bash task triggers a notification when it
  ends, but do not state what signal (if any) is sent to that Bash command's process tree when a user
  presses Esc or explicitly stops a subagent mid-task from the `/tasks` or task-list UI. **Unverified**
  — treat this as an open question, not settled by official docs.
  Sources checked (no answer found there): https://code.claude.com/docs/en/sub-agents ,
  https://code.claude.com/docs/en/tools-reference

## 2. Evidence of orphaned processes from Claude Code Bash commands

**Confirmed via GitHub issue content (anthropics/claude-code), each independently fetched and
substantive — but I could not cross-check maintainer/fix status beyond what each issue currently
shows, so treat "open" as "open at the time these pages were fetched," not as a permanent verdict:**

- **#84647 — "Bash tool timeout does not kill the child."** A timed-out `ugrep` call kept running
  15+ minutes after its 120s timeout and 12 minutes after the tool call had already returned to the
  model, reaching 20.24 GB RSS (a second orphan held 4.63 GB), driving the host into swap exhaustion.
  Root cause as described: the Bash wrapper doesn't kill the process group on timeout, doesn't reap on
  subagent exit, and doesn't clean up on session exit.
  https://github.com/anthropics/claude-code/issues/84647

- **#90672 — "Bash tool timeout doesn't terminate process tree."** On Windows, 21 orphaned
  `find.exe`/`grep.exe` processes observed from timed-out calls, each still crawling a ~1M-file
  workspace. https://github.com/anthropics/claude-code/issues/90672

- **#82433 — "Backgrounded (&) shell children survive a Bash-tool timeout and leak as PID-1
  orphans."** Process-group scoping around the timeout kill is described as incorrect, causing
  under-killing. https://github.com/anthropics/claude-code/issues/82433

- **#96625 — "Bash tool leaves orphaned background processes running after session crash/force-quit"**
  (Claude Code 2.1.278 and 2.1.280, macOS). Ten backgrounded CPU-spinning shells ran unsupervised for
  over a day after a force-quit; reparented to `launchd`. Proposed fix: launch the shell in its own
  process group (`setsid`) and `kill(-pid)` the whole group on termination — i.e. the same shape of
  fix this repo would otherwise have to build itself (see §4).
  https://github.com/anthropics/claude-code/issues/96625

- **#93996 — "Orphaned Bash-tool subprocesses (tsc/vitest) outlive a terminated session and run
  unsupervised for hours."** Same shape, different toolchain — a long-running test/build process is
  exactly the kind of command this bug class targets.
  https://github.com/anthropics/claude-code/issues/93996

- **#45717 — "Bash tool timeout kills Claude Code process (SIGTERM propagation), not just the child
  command."** Closed as not planned/stale. Reported against v2.1.97: a timeout's SIGTERM, sent to a
  shared process group, killed the parent Claude Code process itself (tmux showed "Pane is dead,
  status 143"), which — if it happens — is the inverse failure mode: the *agent* dies while its child
  keeps running, exactly the orphaning path in #96625.
  https://github.com/anthropics/claude-code/issues/45717

**Versions affected / fixed:** issues reference Claude Code 2.1.97 through 2.1.280 (current target
per this repo's `claude-code-authoring` skill is "2.1.x"). None of the fetched issues showed a merged
fix or a maintainer confirmation of resolution — they read as open/unconfirmed as of the fetch. This
is web research summarized by a fetch tool, not a from-source audit of the Claude Code codebase;
treat the *pattern* (multiple, independent, specific reports of process-group-scoping bugs around
Bash timeouts and session termination) as the confirmed part, and any individual number/version as a
detail to re-check if it becomes load-bearing for a decision.

## 3. How long the full suite plausibly takes vs. the 2-minute default, and what this repo tells agents

- The suite has **100+ non-Playwright test files** across `freedom_ls/*/tests/` (accounts, base,
  comms, content_base, content_engine, and more — the glob was still truncating at 100 matches) plus
  at least **~19 Playwright test files** (`@pytest.mark.playwright`) spread over `base`, `comms`,
  `course_applications`, `educator_interface`, `learner_interface`, `panel_framework`,
  `referral_tracking`. Each Playwright test launches a browser and a live Django server
  (`idea.md`'s own framing: "Playwright live-server tests hold two connections each").
- A Django suite this size, migrating/creating a test database and running dozens of browser-driven
  tests, plausibly runs from a few minutes to well over ten, especially when several worktrees are
  contending for the same Postgres container (`idea.md`'s own point about `template1` contention).
  That is comfortably past the 120s default and can exceed even the 600s (10 min) ceiling the model
  can request — I did not find or run an actual timing for this specific repo, so this is a plausible
  estimate from suite size, not a measured number.
- **Grepped `claude_plugins/` and `.claude/` for `timeout` and `run_in_background`: no hits that set
  a Bash-tool timeout or request backgrounding for the full suite.** `claude_plugins/django-stack/commands/rebase_main.md`
  Step 9 runs `uv run pytest -x -q` then `uv run pytest -q` (the full suite, twice) with no timeout
  argument mentioned; `claude_plugins/fls-dev/agents/qa-bugfixer.md` Step 5 runs `uv run pytest` (no
  `-x`, explicitly "a whole-suite result") with no timeout argument either. Neither file, nor any
  skill under `claude_plugins/django-stack/skills/testing/` or `claude_plugins/fls-dev/skills/testing/`,
  tells the calling agent to pass an explicit `timeout` on the Bash call. `pytest-timeout` is not in
  `pyproject.toml`'s dependencies (checked both the main and dev dependency groups — only
  `pytest-xdist` appears, twice, once per group).
- Net effect: every full-suite run in this repo — from the rebase hook, from `qa-bugfixer`, and from
  any `sdd-worker` that happens to run `pytest` — is left to Claude Code's own default 120s ceiling
  unless the calling agent happens to ask for longer. Given §3's runtime estimate, the auto-backgrounding
  behavior in §1 is not a corner case here; it is the likely default outcome for a full run.

## 4. Mitigations — fit for a dev-only repo vs. overkill

**Good fit — cheap, dev-only, matches the idea's own "fix both sides" direction:**

- **Pass an explicit Bash `timeout` for full-suite runs.** Add a line to `rebase_main.md` Step 9 and
  `qa-bugfixer.md` Step 5 (and any other place `uv run pytest` runs the whole suite) telling the
  calling agent to pass a timeout near the 600000ms ceiling. This doesn't fix a hard crash, but it
  closes the one leak path that is *entirely within this repo's control*: an agent letting the
  documented default-timeout-then-background behavior fire on a run nobody is actually waiting 10+
  minutes for.
- **`pytest-timeout`** (`uv add --dev pytest-timeout`, `--timeout=N` in `pyproject.toml`'s `[tool.pytest.ini_options]`
  or per-marker). Bounds any single hung test — including a Playwright wait that never resolves — so
  a stuck browser interaction can't be the reason a whole run (and the DB connections + Chromium
  process it holds) never exits on its own. Dev/test-only dependency; doesn't reach downstream FLS
  installs.
- **Cap pytest-xdist workers.** Already the idea's own direction (§4 of `idea.md`). Confirmed relevant
  here too: pytest-xdist's official issue tracker documents that when a worker dies (OS-killed, e.g.
  cgroup OOM), the controller doesn't always recover, and any process a *worker* leaks is reparented
  away from the *controller* when the worker exits — the controller has no visibility into it. Fewer
  workers means fewer independent leak points, not a fix for the reparenting blind spot itself.
  https://github.com/pytest-dev/pytest-xdist/issues/658
- **An orphan-reaper script, matched to what already exists.** This repo already ships
  `claude_plugins/django-stack/scripts/kill_runserver.sh` (finds and kills whatever is bound to a
  dev-server port). The same shape — `ps`-filter, then kill — fits a script that finds `pytest`/
  `manage.py runserver`/headless-Chromium processes older than N minutes and reports or kills them
  (§5 has the filter). Keep it a manual/on-demand script a developer runs, not a cron job: an
  automatic age-based kill risks taking out a `run_in_background` dev server or watch build someone
  left running on purpose.
- **The DB-side reaping the idea already commits to (idle-in-transaction timeout, statement timeout,
  no restart-policy gap) is the backstop that doesn't care *why* a connection was abandoned.** Given
  §1–2's finding that Claude Code's own kill/backgrounding behavior is not fully reliable even when it
  tries, the DB-side fix is the one guaranteed to hold regardless of which of these process-lifecycle
  paths actually fires on a given day.

**Overkill for this repo:**

- **A custom `setsid`-wrapping / process-group-killing wrapper script around `uv run pytest`.** This
  duplicates work `uv run` already does correctly on its own (see below) and that Claude Code's Bash
  tool is *supposed* to do (§1) — building a parallel mechanism means maintaining it, and every agent
  invocation would have to remember to use the wrapper instead of the plain command. Better to lean on
  the DB-side timeout as the thing that doesn't depend on any tool's kill path working.
- **`prctl(PR_SET_PDEATHSIG)` in a `conftest.py` fixture.** Linux-only, needs a native call (`ctypes`
  or a small C shim), only protects the *direct* child (not pytest-xdist's own worker children or a
  Chromium subprocess two levels down), and is exactly the kind of speculative cross-cutting
  infrastructure this repo's conventions caution against building without being asked. Skip it.
- **Automatically killing anything matching a process-name pattern on a timer.** Same objection as
  above: a legitimate `run_in_background` dev server has the same process name as an abandoned one;
  age alone is a weak signal without also checking whether its parent session is still alive.

**A signal-forwarding detail worth knowing, not a mitigation on its own — confirmed from `uv`'s own
docs:** `uv run` isolates its child into its own process group on Unix and reliably forwards SIGTERM to
that whole group exactly once; SIGINT is only forwarded if sent twice or if the child's process group
differs from `uv`'s own (which, given the isolation, it always does). So `uv run pytest` is *not* the
place signals get lost — if Claude Code's Bash tool sends a correctly-scoped SIGTERM, `uv` passes it
on. https://docs.astral.sh/uv/concepts/projects/run/ ; consistent with
https://github.com/astral-sh/uv/issues/12108 (a related SIGINT-forwarding report, unresolved as of
fetch). What happens *after* pytest receives that SIGTERM is a separate, unverified question: a bare
SIGTERM to a Python process is fatal immediately, without running fixture teardown, so a Playwright
`browser.close()` in a fixture would not run — whether the launched Chromium process dies with pytest
then depends on whether Chromium shares pytest's process group (general community reports say
Chromium can start its own process group/session, which would make a group-scoped kill miss it; I did
not find an authoritative Playwright doc confirming this for this repo's Playwright version, so mark
it **unverified**).

## 5. Detecting orphans on a dev machine — for the diagnostics story

Standard `ps`/`pgrep` techniques (not project-specific, no citation needed beyond general Unix usage):

```sh
# All pytest / runserver / headless-Chromium processes, oldest first, with parent PID
ps -eo pid,ppid,pgid,etimes,rss,cmd --sort=-etimes | grep -E 'pytest|manage.py runserver|chromium|chrome.*headless' | grep -v grep

# Anything reparented to init (ppid 1) is a confirmed orphan
ps -eo pid,ppid,cmd | awk '$2 == 1' | grep -E 'pytest|chromium|manage.py'

# Chromium specifically, with its parent
pgrep -af 'chrome.*--headless'
ps -o ppid= -p <pid>   # is that parent still a live `claude`/`node` process, or gone?
```

Cross-reference a suspicious PID against Postgres directly, to tie an orphaned process to the
connection it's holding — this is the missing link `idea.md` itself calls out ("nobody has captured a
… `pg_stat_activity` snapshot at the moment it fails"):

```sql
SELECT pid, usename, datname, state, query_start, state_change, query
FROM pg_stat_activity
WHERE datname LIKE 'test_db_%' OR datname LIKE 'db_%';
```

`pg_stat_activity.pid` is the *server-side* backend PID, not the client's OS PID, so this doesn't
directly join to the `ps` output above by PID — but a long `state_change`/`query_start` on a
connection to a specific worktree's `db_<branch>`/`test_db_<branch>`, correlated in time with a
long-`etimes` orphaned `pytest`/Chromium process found via `ps`, is the concrete evidence this
research topic is short on: a captured pairing of "this orphaned OS process" with "this held DB
connection," at the moment the shared server actually struggles.

---

status: ok
