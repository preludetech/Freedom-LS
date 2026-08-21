# Research: Parallelizing QA and Model Tiering for `/do_qa`

This document analyses what is actually parallelizable inside the FLS `/do_qa` command given Claude Code 2.1.x constraints, and what cheaper model tiers can legitimately handle. All recommendations are grounded in the hard constraints documented in `fls-claude-plugin/skills/claude-code-authoring/` and confirmed against external Playwright MCP behaviour.

---

## 1. What in QA is actually parallelizable?

### The single-browser constraint is real and documented

The standard `microsoft/playwright-mcp` server uses one persistent browser profile. When a single MCP server is started, all agents that connect to it share the same browser window and fight over the same tab. This is not theoretical: GitHub issue #893 on `playwright-mcp` documents agents "fighting over the same tab in the same browser window" when run in parallel against one server, producing inconsistent results. The profile-locking issue (#1294) further confirms that a second client hitting the same profile gets a hard "Browser is already in use" error.

Therefore: **with one Playwright MCP server = one browser = all three viewport phases (desktop/mobile/tablet) are serial by nature.**

### What would true viewport parallelism require?

Running desktop, mobile, and tablet as separate depth-0 agents each with their own browser would need:

1. **A separate MCP server process per agent.** Each server must point to a distinct `--user-data-dir` (or use `--isolated`). The `playwright-parallel-mcp` project achieves this by spawning a child MCP server process per session, giving OS-level isolation. The `concurrent-browser-mcp` alternative does the same via session IDs routing to independent instances.

2. **A separate `runserver` port per agent.** `/do_qa` already handles dynamic port selection; three agents each calling `find_available_port.sh` and launching their own `manage.py runserver` would work independently.

3. **MCP server configs declared at session startup.** Claude Code's MCP server list is configured before a session begins; you cannot spin up a new MCP server from inside a running session or from a subagent. This is the hard blocker: `/do_qa` runs at depth 0 and subagents do not receive `mcp__playwright*` in their `tools:` (confirmed by `sdd-worker.md` and `qa-data-helper.md` frontmatter which list only `Read, Glob, Grep, WebFetch, WebSearch, Write` and `Bash` respectively — no `mcp__playwright*`).

4. **Three simultaneous depth-0 sessions.** Fan-out with Playwright would require launching three separate top-level Claude Code sessions (not subagents), each preconfigured with its own MCP server pointing at a distinct `--user-data-dir`. This is outside the current workflow model and would require external orchestration (a shell script that launches three `claude` processes).

### What is genuinely serial and why

- Steps 3-7 in `do_qa.md` (navigate, login, desktop tests, mobile resize, tablet resize) all share one browser session where navigation state carries over. Resize is cheap; it is the page-walking and screenshot-taking that costs tokens.
- The `fls:qa-data-helper` delegation is serial-by-necessity: it modifies the shared database that the browser session reads. Running it concurrently with browser tests against the same DB risks mid-test data mutation.
- Screenshot compression (Step 8) and report assembly (Step 9) are serial post-processing and are cheap.

### What IS parallelizable today, within constraints

Within a single `/do_qa` depth-0 session with one Playwright server:
- **Test-data creation** (delegating to `fls:qa-data-helper`) and **initial server startup + branch-badge check** could in principle be overlapped, but the data helper needs the server address only to confirm its work — the real DB operations happen via `manage.py shell`, not the browser. This is a minor win.
- **Report assembly and todo-update** (Steps 9-11) can delegate to `fls:sdd-mechanic` (Haiku) as a fire-and-forget unit after screenshots are taken, while no more browser work is needed.
- **The ad-hoc probe** (Step 5, "if something seems out of place spawn one `fls:sdd-worker`") is already correctly structured as a parallel non-browser depth-1 unit.

---

## 2. Cheap-up-front gating (skip the full matrix for trivial changes)

### Diff-scoping before launching the browser

Before starting the dev server, run `git diff main...HEAD --name-only` (or the equivalent for the worktree branch). Classify the diff:

- **Admin-only**: all changed paths match `*/admin.py`, `*/admin/`, migrations, management commands, or `config/`. The command already says "Don't do mobile/tablet tests if we are checking the django admin interface." A pre-step that detects this and sets a `$SKIP_RESPONSIVE` flag would save two-thirds of browser time automatically.
- **Backend-only (no template/static changes)**: if the diff contains zero `*.html`, `*.css`, `*.js`, or `static/` paths, responsive layout tests are unlikely to surface anything. Skip mobile/tablet, or reduce them to a single navigation smoke-check.
- **Single-component change**: if the diff is confined to one template file and its associated view, narrow the test plan to that component's tests plus a navigation smoke test, rather than the full suite.

This classification is cheap (one `git diff` + pattern matching) and can be done in a few lines of Bash inside Step 1, before any Playwright work starts. The result is a flag (`FULL | ADMIN_ONLY | BACKEND_ONLY`) that the later steps read.

### Fast smoke gate before the full matrix

Add an explicit **Step 4.5: smoke check**:
- Navigate to the home page and one key page relevant to the change.
- If either fails (404, 500, missing element), stop and report immediately without running the full matrix.
- If both pass, proceed with desktop/mobile/tablet.

This is a single Playwright snapshot + one decision — cheap but catches the most common breakage patterns (import errors, template syntax errors, missing URL registrations) before spending tokens on the full run.

### Test-plan line-item filtering

The QA plan (generated by `/plan_from_spec`) could be annotated with tags like `[responsive]`, `[admin]`, `[backend]`. The depth-0 `/do_qa` session reads the plan and the diff classification, then filters out irrelevant test IDs before walking them. This is a spec-level improvement (change the plan format) rather than a runtime change, but it avoids the current all-or-nothing approach.

---

## 3. Model tiering for QA sub-work

### The inline-execution caveat matters here

`/do_qa` runs the depth-0 session. Its `model:` frontmatter is **inert when the command is followed inline** — the session model governs. The only way to move work to a cheaper model is to spawn a **named agent file** (e.g. `fls:sdd-mechanic` or `fls:sdd-worker`) with `model: haiku` or `model: sonnet` in its frontmatter, as the skill documents explicitly.

### Tasks that can move to Haiku (`fls:sdd-mechanic`)

- **Screenshot compression** (Step 8): a pure `uv run --with pillow python ...` Bash call. No judgement needed. Spawn `fls:sdd-mechanic` with the path and the command; it runs and returns `status: ok`. This is already the textbook Haiku use case.
- **Report assembly from structured notes** (Step 9, if the depth-0 session produces structured notes first): if the depth-0 session emits a machine-readable list of `{test_id, status, screenshot_path, notes}` entries to a scratch file, a Haiku agent can render that into `qa_report.md` using a template. Haiku handles templated text well. The judgement (what is a bug vs expected?) stays at depth 0.
- **`todo.md` update** (Step 11): already documented as a `fls:sdd-mechanic` pattern in `update_todo.md`. No change needed here — the command should already be spawning the mechanic for this.
- **Dev-server lifecycle** (start/kill, find port): pure Bash. Could be a mechanic chore, though the port-collision check (Step 3, reading the debug-badge) currently requires Playwright so it stays at depth 0.
- **Diff classification** (the pre-step proposed in section 2): one `git diff` and pattern match. Mechanic-grade work.

### Tasks that must stay at depth 0 (session model)

- **The actual browser driving** (Steps 5-7): exploratory navigation, reading page snapshots, deciding what to click next, recognising layout bugs from a screenshot, judging whether an overflow is a real problem or a known limitation. This requires strong vision + reasoning. Must stay at depth 0 on the strong session model.
- **Data-gap detection** (Step 5, rule 2): deciding whether a missing element is a data gap or a real bug requires page context + the test plan. Depth 0.
- **The ad-hoc probe decision** (Step 5, "if anything seems out of place"): initiating the probe is depth-0 judgement; the probe itself correctly runs as `fls:sdd-worker` (Sonnet).
- **`fls:qa-data-helper`** delegation: already uses `model: opus` by design. Correctly tiered since it involves reading factories and writing new ones.

### Current tiering gap

The main token drain in `/do_qa` is that **Steps 8-11 run on the full session model even though none of them need it**. The session accumulates a long context of screenshots and navigation output before reaching report assembly, making those final steps expensive. Moving screenshot compression and report rendering to spawned agents (Haiku + Sonnet respectively) would trim the depth-0 context significantly.

---

## 4. Industry patterns for parallel browser testing and what maps onto an LLM-driven flow

### Playwright workers and sharding

Standard Playwright test sharding (`--shard=1/3 --shard=2/3 --shard=3/3`) and workers (`--workers=N`) work because tests are **code artifacts** that can be partitioned and dispatched ahead of time. Each worker knows its test list before it starts; there is no mid-run decision about what to test next.

LLM-driven QA is fundamentally different: the agent reads a snapshot, decides what to interact with, acts, reads again. The test sequence is **emergent**, not pre-declared. Playwright's `fullyParallel: true` and `--shard` flags therefore do not apply directly — there are no `.spec.ts` files to shard.

**What does map:** the idea of sharding by *viewport* (desktop, mobile, tablet) as three independent test contexts with no shared state between them. Each viewport effectively is a shard — it needs its own browser, its own server port, and its own screenshot directory. The parallelism model is "three identical test suites against three browser configurations" rather than "one suite split across workers."

### The `playwright-parallel-mcp` and `concurrent-browser-mcp` projects

Both projects exist precisely to solve the multi-agent parallel browser problem. `playwright-parallel-mcp` spawns a separate child MCP server process per session (each with its own browser), routing calls via a `sessionId` parameter. This is the architectural pattern that would enable three Claude Code sessions to each run their own viewport without interference.

However, both require **configuring multiple MCP server instances** before the session starts — the same hard constraint discussed in section 1. They solve the browser isolation problem but not the "can't spawn MCP servers from inside a running session" problem.

### Token-noise isolation (the more applicable pattern)

Anthropic's own multi-agent research system reports ~15x token cost multiplier for parallel subagents. Their mitigation: each subagent compresses its context before returning to the lead agent — only the summary crosses the boundary. For `/do_qa`, this means the depth-0 session should **not** accumulate raw Playwright output (snapshots, long accessibility trees) in its main context. Instead: take screenshot → save to file → note the path → continue. The heavy snapshot data stays out of the main context. The report-assembly step then reads the files (paths, not contents) rather than replaying the snapshots.

---

## 5. Concrete recommendation for FLS

### What is worth doing

**A. Diff-scoping gate (highest ROI, no architectural change needed)**
- Add a pre-step (before launching the server) that runs `git diff main...HEAD --name-only` and classifies the change as `FULL`, `ADMIN_ONLY`, or `BACKEND_ONLY`.
- `ADMIN_ONLY` skips Steps 6-7 (mobile/tablet) entirely.
- `BACKEND_ONLY` reduces Steps 6-7 to a single-page navigation smoke check.
- Cost: ~10 lines of Bash in Step 1. Benefit: saves 50-66% of browser time for the majority of backend changes.

**B. Smoke gate before full matrix**
- Add Step 4.5: navigate to home + the primary changed page, take one snapshot, confirm no 500/404. If it fails, write a report and stop — do not walk the full plan.
- Cost: 2 Playwright tool calls. Benefit: avoids running 20 tests after a crash-on-load error.

**C. Offload Steps 8-11 to Haiku/Sonnet agents**
- Step 8 (compress screenshots): spawn `fls:sdd-mechanic` (Haiku) immediately after the last screenshot is taken.
- Step 9 (report assembly): have depth-0 write a structured JSON scratch file of `{test_id, status, viewport, screenshot_path, notes}` entries as it goes. Then spawn `fls:sdd-worker` (Sonnet) to render `qa_report.md` from that scratch file. This moves the longest synthesis step off the already-large depth-0 context.
- Step 11 (todo update): already documented for `fls:sdd-mechanic`. Confirm this is actually being spawned rather than inlined.

**D. Pass file paths not snapshot content**
- Current practice: Playwright snapshots (accessibility trees, DOM state) accumulate in the depth-0 context throughout the run. Enforce a discipline of `browser_take_screenshot` → note path → do not re-read the screenshot into the prompt. The report assembly step reads paths from the scratch file, not screenshot bytes.

### What is NOT worth doing (in the current architecture)

**Viewport parallelism via separate sessions.** Running three simultaneous depth-0 Claude Code sessions each with their own Playwright MCP server is technically achievable but requires:
- An external shell orchestrator launching three `claude` processes simultaneously.
- Three separate MCP server configurations (distinct `--user-data-dir` or use of `playwright-parallel-mcp`).
- A merge step to combine three `qa_report.md` outputs.

This is a real engineering project, not a config tweak. Given the ROI: the diff-scoping gate (recommendation A) will eliminate viewport tests for most backend-only changes anyway, so the three viewport passes are rarely all needed. Parallelize only after A-D are in place and the matrix is still the bottleneck.

**Model tiering for the browser-driving steps.** Desktop/mobile/tablet driving must stay on the strong session model — the visual judgement and exploratory navigation are the core value. Tiering those to Haiku would produce unreliable results.

**Playwright test sharding.** Not applicable — there are no pre-declared test scripts to shard.

---

## Recommendations for FLS (bullet summary)

- Add a `git diff` pre-classification step that sets `ADMIN_ONLY` or `BACKEND_ONLY` flags; use them to skip or reduce responsive viewports before any server starts.
- Add a two-call smoke gate (home page + changed page) before the full test walk; abort early on load failure.
- Move screenshot compression to `fls:sdd-mechanic` (Haiku) immediately after last screenshot.
- Write a structured scratch JSON as depth-0 walks tests; use `fls:sdd-worker` (Sonnet) to render `qa_report.md` from that file, keeping report assembly off the saturated depth-0 context.
- Confirm `todo.md` update (Step 11) is already spawning `fls:sdd-mechanic`, not inlining the helper.
- Pass file paths only between steps; never replay raw Playwright snapshots into the depth-0 context.
- Do NOT attempt viewport parallelism until the above are in place — the diff gate eliminates the need for most runs.
- Do NOT tier the browser-driving steps below the session model; visual judgement is the core cost and it is worth it.

---

## References

- [playwright-mcp issue #893: multiple parallel claude-code agents interfere](https://github.com/microsoft/playwright-mcp/issues/893)
- [playwright-mcp issue #1294: support isolated browser instances / separate user-data-dir](https://github.com/microsoft/playwright-mcp/issues/1294)
- [playwright-parallel-mcp: spawns child MCP server processes for session isolation](https://github.com/sumyapp/playwright-parallel-mcp)
- [concurrent-browser-mcp: dynamic creation and management of parallel browser instances](https://github.com/sailaoda/concurrent-browser-mcp)
- [microsoft/playwright-mcp official repo](https://github.com/microsoft/playwright-mcp)
- [Playwright parallelism docs](https://playwright.dev/docs/test-parallel)
- [Playwright sharding docs](https://playwright.dev/docs/test-sharding)
- [Playwright browser context isolation docs](https://playwright.dev/docs/browser-contexts)
- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic: Effective context engineering for agents](https://www.anthropic.com/engineering/effective-context-engineering-for-agents)
- [Claude Code subagents docs](https://code.claude.com/docs/en/sub-agents)
- [Claude Code model config / costs docs](https://code.claude.com/docs/en/costs)
- [Optimizing Test Runtime: Playwright Sharding vs. Workers (currents.dev)](https://currents.dev/posts/optimizing-test-runtime-playwright-sharding-vs-workers)

---

status: ok
reason: research complete — parallelism constraints, gating options, tiering recommendations, and industry pattern mapping all grounded in actual constraint files and cited sources
