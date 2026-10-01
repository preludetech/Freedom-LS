# Research: leaked agent processes on the dev machine

Scope: where the leaked `playwright-mcp`/Chrome processes and the self-matching pytest wait loop
(`research_live_diagnostics.md` §6) come from in **this repo**, and what's proportionate to stop or
reap them. Does not re-derive the Postgres-side failure modes (see `research_postgres_failure_modes.md`)
or the general Claude-Code-Bash-timeout leak path (see `research_agent_process_lifecycle.md`, which
this file complements rather than repeats).

## Bottom line

The leak is real, matches multiple independently-reported upstream bugs almost exactly (85
`playwright-mcp`/`npm exec` processes, 9 >1 day old, 36 Chrome processes — `research_live_diagnostics.md`
§6), and **the server that leaks them ships from the generic, portable `ds` (`django-stack`) plugin**,
not from an FLS-specific one. Any launch-flag or wrapper-script fix belongs there, so it reaches every
project that installs `ds` — proportionate here means small, config-free changes (pin a version, add
an on-demand reaper script matching the existing `kill_runserver.sh` shape), not a new subsystem. The
self-matching wait loop, separately, is **not instructed anywhere in this repo** — it is ad hoc agent
behaviour that a small addition to the existing "pass an explicit timeout" mitigation
(`research_agent_process_lifecycle.md` §4) would have avoided.

---

## 1. Where the Playwright MCP server is configured, and who uses it

**Only one `.mcp.json` exists in this repo:**
`claude_plugins/django-stack/.mcp.json` — read in full:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest",
        "--output-dir", "${CLAUDE_PROJECT_DIR}/qa-screenshots",
        "--headless", "--isolated",
        "--image-responses", "omit",
        "--caps", "testing"]
    }
  }
}
```

- **Launch command:** `npx @playwright/mcp@latest …` — unpinned (`@latest`, re-resolved by `npx` on
  every launch), headless, `--isolated` (disposable per-session Chrome profile — good for not
  accumulating profile dirs, irrelevant to whether the *process* itself leaks).
  `claude_plugins/fls-dev/commands/do_qa.md` Step 7 even calls out, in a "Per-run capture check," that
  "the Playwright MCP server is unpinned (`@latest`), so its behaviour can change between runs" —
  this repo already knows it floats on latest.
- **Which plugin ships it:** `django-stack`, manifest name **`ds`** (`claude_plugins/django-stack/.claude-plugin/plugin.json`).
  `claude_plugins/django-stack/README.md` states this plugin is **"portable… carries zero
  product-specific domain knowledge and depends on no other plugin,"** installed by "any Python/Django/
  HTMX/Tailwind project via `/ds:init` and `--plugin-dir`," and explicitly lists `.mcp.json` (the
  Playwright MCP server) under its "Hooks & configs" section. **Confirmed generic/shared** — any edit
  to this file's launch flags reaches every other `ds`-using project, not just FLS.
- **Tool namespace:** `claude_plugins/django-stack/skills/use-playwright/SKILL.md` documents that `ds`'s
  server is exposed as `mcp__plugin_ds_playwright__*`, and separately warns: *"A project that also
  declares a `playwright` server in its own root `.mcp.json` starts the server twice and gets the same
  tools again under the plain `mcp__playwright__*` prefix — drop the root declaration and rely on the
  one `ds` ships."* This repo's tree has **no root-level `.mcp.json`** (only the one inside
  `claude_plugins/django-stack/`), so the bare `mcp__playwright__*` prefix mentioned in the task
  (and pre-approved in `.claude/settings.json`'s `allow` list alongside `mcp__plugin_ds_playwright__*`)
  is not explained by anything version-controlled in this repo. `do_qa.md` Rule 1 itself anticipates
  this ("Another Playwright server may be visible in the session") without saying where it would come
  from. **Unverified**: whether a second registration exists at user- or project-local scope outside
  version control — per `CLAUDE.md` ("Do not look in the user's home folder for any claude code plugins,
  agents or configuration"), I did not check the user's home directory or user-level Claude config to
  chase this down; flagging it rather than investigating further.
- **Who uses it:** `claude_plugins/fls-dev/commands/do_qa.md` (Rule 1: "You MUST use Playwright MCP…
  the `mcp__plugin_ds_playwright__*` tools and no other browser server"), `claude_plugins/fls-dev/commands/protected/frontend_check.md`
  (the rebase-hook smoke pass, `allowed-tools: … mcp__plugin_ds_playwright__*`), and
  `claude_plugins/django-stack/skills/use-playwright/SKILL.md` itself (the interactive "look at a page"
  skill). All three are legitimate, intentional uses — the server is meant to run, repeatedly, across
  many QA/rebase invocations; the problem is exclusively that its process doesn't reliably die
  afterward.

## 2. Why they leak — Claude Code + `@playwright/mcp`, upstream evidence

Both the MCP-server-process layer and the Chrome-process layer inside it are independently and
currently broken, per multiple GitHub issues fetched 2026-09-28 (none showed a merged fix; treat "open"
as "open at fetch time"):

- **`npm exec`/`npx` wrapper doesn't forward cleanup, and Claude Code doesn't track the PIDs it
  spawns.** [anthropics/claude-code#33947](https://github.com/anthropics/claude-code/issues/33947) —
  "MCP server and subagent processes not cleaned up on session end — orphan accumulation (PPID=1)."
  Root cause as described: Claude Code doesn't track MCP server PIDs for cleanup on exit;
  **`npm exec` spawns two processes per invocation (a wrapper + a node child), and neither is
  terminated or registered for cleanup**; SIGHUP isn't forwarded to children on terminal close; a
  memoized connection-getter re-creates instead of reusing a server on reconnect, spawning duplicates.
  Observed on the reporter's machine: 107 unsigned (orphaned) node processes, ~7.75 GB RAM, ~40% CPU,
  accumulating indefinitely. Reported against **Claude Code 2.1.72+**. Closed **"not planned."**
  Three independent community tools (`cc-reaper`, `claude-cleanup`, `clean-orphans`) converged
  independently on the same fix shape: kill the process group (`kill -- -$PGID`), with a PPID=1 scan
  as fallback, gated by age. Related/same-class issues surfaced by search but not individually
  fetched: [#40667](https://github.com/anthropics/claude-code/issues/40667) ("MCP server processes
  leak on host after subagent/session termination"),
  [#1935](https://github.com/anthropics/claude-code/issues/1935),
  [#22612](https://github.com/anthropics/claude-code/issues/22612),
  [#79740](https://github.com/anthropics/claude-code/issues/79740) (stdio server orphaned on `/mcp`
  reconnect after a `.mcp.json` edit), [claude-code-action#865](https://github.com/anthropics/claude-code-action/issues/865).
- **Chrome itself is launched to ignore the signals that would let it die with its parent.**
  [microsoft/playwright-mcp#1568](https://github.com/microsoft/playwright-mcp/issues/1568) — "Headless
  Chrome processes orphaned after MCP stdio transport closes." Root cause: in
  `playwright-core/lib/tools/mcp/browserFactory.js`, `createPersistentBrowser()` launches Chrome with
  `handleSIGINT: false, handleSIGTERM: false` — Chrome is told to ignore those signals — and there is
  **no cleanup handler on the MCP server's transport-close or process-exit events, and no watchdog on
  the parent PID.** So when the node process (the `npx`-launched MCP server) dies, Chrome never
  receives a signal it will act on and keeps running. Observed elsewhere: after 8 days of normal use,
  11 orphaned `mcp-chrome-*` profile directories (~1 GB) and two still-running headless Chrome trees,
  one at 975% CPU. Tested against `@playwright/mcp@latest`, Node 24, Chrome 147 — i.e. current as of
  the fetch. No merged fix.
- **The same shape recurs specifically inside Claude Code's own `/mcp` reconnect flow.**
  [anthropics/claude-code#78551](https://github.com/anthropics/claude-code/issues/78551) — "Playwright
  MCP server leaves orphaned browser processes after `/mcp` reconnect — no cleanup, accumulates over
  days." Reported flow: after ~1 hour of use, a `Target page, context or browser has been closed`
  error prompts a `/mcp` → reconnect, which launches a **new** browser instance without killing the
  previous one. Over 3 days: **26 orphaned root Chrome instances (217 total OS processes)**, ~13 GB
  RAM (42.7% of 32 GB), contributing to sustained high CPU/thermal load — closely matching this
  machine's 36 Chrome processes / 4.1 GB. Reported with `--isolated` in use (same flag this repo's
  `.mcp.json` passes). **Closed "not planned."**
- **Where signals *do* get forwarded correctly, for contrast:** `research_agent_process_lifecycle.md`
  §4 already confirmed `uv run` isolates its child into its own process group and reliably forwards
  SIGTERM once (https://docs.astral.sh/uv/concepts/projects/run/). The `npm exec`/`npx` wrapper is a
  **separate, specifically-implicated** class of signal-forwarding failure — #33947 names it directly
  ("npm exec spawns two processes … neither is terminated") — not a generalisation from the `uv`
  finding.
- **Versions fixed:** none found. Every issue above reads as open or closed-not-planned at fetch time
  (2026-09-28), spanning Claude Code 2.1.72+ and current `@playwright/mcp@latest`. Treat the leak as
  the current, still-shipping behaviour of both the wrapper (`npx`/`npm exec`) and the server
  (`@playwright/mcp`), not a bug in an old version this repo could simply upgrade past.

## 3. The self-matching wait loop

Grepped `claude_plugins/**` and `.claude/**` for the loop's shape (`sleep`, `while true`, `until !`,
`ps aux`, `grep -q`) and for any documented alternative (`run_in_background`, `BashOutput`,
`background`):

- **No repo file instructs this loop.** The only `sleep` hits are unrelated: a pre-approved
  `sleep 3 && curl …` health-check pattern in `claude_plugins/django-stack/templates/settings.json:21`,
  and a comment noting Playwright's `expect()` auto-waits so tests don't need an explicit sleep
  (`claude_plugins/django-stack/resources/playwright-testing.md:102`). No skill, command, or agent file
  contains `ps aux`, `while true`, or an `until` polling loop.
- **No repo file documents `run_in_background`/`BashOutput` as the way to wait on a long pytest run**
  either — a grep for those terms across `claude_plugins/**` returned nothing.
- **Conclusion: this was ad hoc agent behaviour invented in-session, not something the repo told an
  agent to do.** It is the same underlying gap `research_agent_process_lifecycle.md` §3 already
  identified — no call site passes an explicit Bash `timeout` for a full pytest run — expressed as a
  worse variant: instead of letting Claude Code's documented default-timeout-then-background behaviour
  fire, the agent hand-rolled its own polling loop, and that loop happened to embed the exact string
  it was waiting to see absent (`echo "pytest finished"` inside a command whose own `ps aux | grep`
  matches any command line containing the substring `pytest`, including its own). Bracketing the
  filter (`[p]ytest`, which this loop's `grep` argument already did) does not save it — the failure is
  that the loop's *own* command line contains the literal string `pytest` (in `"pytest finished"`),
  so it always matches itself regardless of how the filter is bracketed.
- **What would prevent it:** the same fix already proposed in `research_agent_process_lifecycle.md`
  §4 — pass an explicit Bash `timeout` near the 600000 ms ceiling on any full-suite `uv run pytest`
  call (`claude_plugins/django-stack/commands/rebase_main.md` Step 9, `claude_plugins/fls-dev/agents/qa-bugfixer.md`
  Step 5) so the agent never needs to invent its own wait mechanism — plus, if a skill ever does tell
  an agent to wait on a long-running command, telling it explicitly to use `run_in_background` +
  `BashOutput`/the completion notification rather than a self-written `ps`/`grep` poll, and never to
  echo a marker string that itself contains the thing being polled for.

## 4. Mitigations proportionate to a dev repo

**Launch-flag changes to `claude_plugins/django-stack/.mcp.json` — generic `ds` plugin, ships to every
`ds`-using project, flag before changing:**

- **Pin an exact `@playwright/mcp` version instead of `@latest`.** Avoids `npx` re-resolving/re-fetching
  the package on every launch and makes behaviour reproducible across runs — the same problem
  `do_qa.md` Step 7 already flags ("the Playwright MCP server is unpinned… its behaviour can change
  between runs"). Precedent for exactly this change: [gevorg33/investigator-app#76](https://github.com/gevorg33/investigator-app/pull/76)
  ("the Playwright MCP runs a pinned version, not `@latest`"). This does **not** fix the process leak
  itself (§2's bugs are present in every version fetched) — it only removes version drift and
  `npx`'s re-resolution overhead.
- **Call the installed package directly instead of through `npx`/`npm exec`, if this repo is willing
  to add a pinned dependency.** Precedent: [BlaineHeffron/cadre#15](https://github.com/BlaineHeffron/cadre/pull/15)
  ("launch Playwright MCP from a pinned dependency") — install `@playwright/mcp` as a pinned
  `devDependency` and launch its `cli.js` with `node`/`process.execPath` directly, skipping the `npx`
  wrapper layer that #33947 names as spawning two untracked processes. This removes **one** of the two
  leak layers (the wrapper), not the other (Chrome's own `handleSIGINT:false`/`handleSIGTERM:false`
  launch in `browserFactory.js`, per #1568, which is internal to `@playwright/mcp` regardless of how
  it's invoked). **This is a change to the generic `ds` plugin's `.mcp.json`** — it reaches every
  project that installs `ds`, which is proportionate (it's a strict improvement with no downside for
  those projects) but should be called out in the plugin's own README/changelog when made.
- `--isolated` and `--headless` are already set — good defaults that reduce per-instance disk/GPU
  footprint but do nothing about the leak itself (§2's bugs reproduce with `--isolated` in place,
  per #78551).

**A small reaper script, precedent already in the repo:**

`claude_plugins/django-stack/scripts/kill_runserver.sh` (mirrored at
`.claude/ds/scripts/kill_runserver.sh` and `claude_plugins/django-stack/templates/wrapper_scripts/kill_runserver.sh`)
is the exact shape to follow: find a PID via a `ps`/`ss` filter, then `kill` it, with no confirmation
prompt (it's a `sh` script users run by hand). Read in full:

```sh
PID=$(ss -tlnp | grep ":$PORT " | grep -oP 'pid=\K[0-9]+')
if [ -n "$PID" ]; then kill "$PID"; else echo "No process found on port $PORT"; fi
```

A `reap_orphans.sh` in the same shape would:

- Filter `ps -eo pid,ppid,etimes,rss,cmd` for `npm exec.*@playwright/mcp`, `playwright-mcp`, and
  headless-Chromium command lines (the general filter is already spelled out in
  `research_agent_process_lifecycle.md` §5).
- Decide "leaked" using the same signal the three independent community tools converged on for this
  exact bug class (#33947): **PPID == 1** (reparented to init — the dominant case for a `claude`
  session that has fully exited) as the strong, cheap check, combined with an age threshold (e.g.
  >1 hour) so a process still owned by a live session isn't touched. `research_agent_process_lifecycle.md`
  §5's "is that parent still a live `claude`/`node` process, or gone?" check is the more thorough
  variant, for processes reparented to something other than init (a detached shell, tmux) — worth
  using if PPID=1 alone under-catches on this machine, but PPID=1 + age already matches the shape of
  what's actually been observed here (9 of 85 processes >1 day old, `research_live_diagnostics.md` §6).
- **Stay manual/on-demand, not a cron job or automatic kill-on-timer** — the same caution
  `research_agent_process_lifecycle.md` §4 already gives for a pytest/Chromium reaper applies
  identically here: an automatic age-based kill risks taking out a deliberately long-running
  `run_in_background` dev server or watch build someone left running on purpose. PPID=1 mitigates this
  (a process the developer is still watching normally still has a live parent), but it isn't a
  guarantee, so keep this a script a developer runs, not a background daemon.
- **Placement matters for the "don't burden downstream" constraint:** if this reaper only ever
  targets `playwright-mcp`/Chrome (the `ds` plugin's own leak), it's reasonable to add it *inside*
  `claude_plugins/django-stack/scripts/` next to `kill_runserver.sh` — every `ds`-using project gets
  a fix for a problem `ds` itself causes them, which is a benefit, not a burden. If it's written more
  broadly (also targeting `pytest`/`manage.py runserver`, per `research_agent_process_lifecycle.md`
  §5), it belongs in `claude_plugins/fls-dev/scripts/` or `.claude/fls-dev/scripts/` instead, since
  those process names are FLS's own dev workflow, not something every `ds` project necessarily runs
  the same way.

**Guidance in skills:**

- `claude_plugins/django-stack/skills/use-playwright/SKILL.md` already documents the dual-registration
  hazard (§1) — the natural place to add a short note that this server's processes can outlive the
  session (citing the upstream issues above) and where the reaper script lives, once one exists.
- `claude_plugins/django-stack/README.md`'s "Scripts" list (§ "What's inside") would need one more
  line if a reaper script is added, to keep the inventory accurate.
- For the wait-loop mitigation, the natural edits are the two call sites
  `research_agent_process_lifecycle.md` §3/§4 already names: `claude_plugins/django-stack/commands/rebase_main.md`
  Step 9 (`ds`, shared — flag before changing) and `claude_plugins/fls-dev/agents/qa-bugfixer.md` Step 5
  (`fls-dev`, FLS-specific, safe to change freely).

## What I could not verify

- The exact origin of the bare `mcp__playwright__*` tool prefix observed on this machine (§1) — no
  version-controlled `.mcp.json` in this repo produces it; most likely a project-local or user-level
  MCP registration outside version control, which I did not chase down per `CLAUDE.md`'s instruction
  not to look in the user's home folder.
- Whether PPID==1 alone (vs. a full live-ancestor walk) would misclassify any legitimate long-running
  process on this specific machine — I did not run the reaper's filter against live process state as
  part of this research task (this file is source/doc research, not a live audit; `research_live_diagnostics.md`
  §6 already did the one live snapshot this idea has).
- Whether any of the six anthropics/claude-code issues found by search but not individually fetched
  (`#40667`, `#1935`, `#22612`, `#79740`, `#51516`, `claude-code-action#865`) differ materially from
  `#33947`'s description — they were not opened, only surfaced by title in the search results.

status: ok
