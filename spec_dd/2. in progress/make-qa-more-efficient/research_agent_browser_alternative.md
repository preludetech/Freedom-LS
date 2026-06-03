# Research: vercel-labs/agent-browser as Playwright MCP Alternative/Complement

**Context.** FLS's `/do_qa` command relies on Playwright MCP, which is available only at depth 0. Subagents (`sdd-worker`, `qa-data-helper`) get no MCP tools, so "true viewport parallelism" was pushed to Phase 4 and requires an external orchestrator launching three top-level sessions. `agent-browser` is a Bash-driven CLI — if any agent with the `Bash` tool can drive it, depth-1 subagents could potentially handle parallel viewports without an external harness. This document validates or refutes that claim and assesses the full tradeoff.

---

## 1. What It Is and How an Agent Drives It

### Architecture

`agent-browser` is a native Rust CLI + persistent Rust daemon communicating over Chrome DevTools Protocol (CDP) directly — no Node.js runtime required for the daemon itself. The daemon launches automatically on first command and stays resident. All browser state lives in the daemon; the CLI is stateless. Chrome is downloaded once via `agent-browser install` (from Chrome for Testing).

**It is NOT an MCP server.** There is no MCP server mode. An agent drives it exclusively by issuing shell commands via the `Bash` tool:

```bash
agent-browser open http://127.0.0.1:8000/
agent-browser snapshot -i          # interactive-only accessibility tree
agent-browser click @e2            # click element by stable ref
agent-browser type @e3 "hello"
agent-browser screenshot page.png  # to disk — NOT to context
```

### Claude Code Integration (Skills)

Install: `npx skills add vercel-labs/agent-browser` installs a thin SKILL.md stub at `.claude/skills/agent-browser/SKILL.md`. The stub is intentionally minimal and contains trigger words + a pointer to the CLI. Agents retrieve current documentation at runtime: `agent-browser skills get core` (or `--full`) which returns the complete command reference matching the installed CLI version. This solves version drift — the stub rarely changes while the daemon delivers current docs.

Skills work with Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, Goose, OpenCode, and Windsurf.

### Install/Runtime Requirements

- No Node.js for the daemon (Node 24+ only if building from source)
- No Rust at runtime (pre-built native binaries for macOS ARM64/x64, Linux ARM64/x64, Windows x64)
- Chrome auto-downloaded on first `agent-browser install`; Chrome-only (no Firefox, no WebKit)
- npm needed only to run `npx skills add ...`

### Maturity

- **35,100 GitHub stars** (measured June 2026)
- **Pre-1.0**: currently v0.27.1 (released June 1, 2026); 83+ tagged releases
- **Cadence**: ~1-2 releases per week. Breaking changes are possible at any minor version
- **License**: Apache-2.0
- **Risk assessment**: high activity, high star count, but pre-1.0 means the CLI surface can change between minor versions — a non-trivial churn risk for an automation workflow that depends on exact command flags

---

## 2. Token Efficiency vs Playwright MCP

### Published Numbers

The most credible benchmark (2026) compares a 10-step authenticated workflow:

| Tool | Tokens (10-step flow) |
|---|---|
| Playwright MCP | ~114,000 |
| Playwright CLI | ~27,000 |
| agent-browser | ~7,000 |

Overhead at session start (before any page interaction):
- Playwright MCP tool definitions: ~13,700 tokens
- Chrome DevTools MCP tool definitions: ~17,000 tokens
- agent-browser: 0 (no tool schema — it's a CLI)

Per-action response size:
- Playwright MCP button click: returns ~12,891 characters (full accessibility tree update)
- agent-browser button click: returns `Done.` — six characters

Snapshot size per page (interactive-only mode `-i`):
- agent-browser: ~200–400 tokens for a typical page
- Playwright MCP: ~3,800–50,000 tokens depending on page complexity (full tree)

Vercel's own internal testing (when reducing toolset by 80%) observed: 3.5x faster execution, 37% fewer tokens consumed, 42% fewer steps required, 100% success rate (vs 80% baseline).

### Comparison to the FLS Baseline

The `research_playwright_mcp_efficiency.md` documents the FLS-specific Playwright MCP costs:
- ~114,000 tokens per 8-step authenticated workflow in default mode
- Screenshots into context: up to 232,000+ tokens per full-page screenshot (the single largest sink)
- ~4,200 tokens of tool schema overhead per session

Against the `imageResponses: "omit"` + `capabilities: ["core","testing"]` config (Phase 1 of the idea), the Playwright MCP cost drops materially. **After Phase 1 tuning, Playwright MCP's effective cost for snapshot-only interaction is closer to 27,000–50,000 tokens for the FLS workflow** (screenshots to disk, incremental snapshots). `agent-browser` at ~7,000 per similar workflow is still notably cheaper, but the gap narrows substantially once Playwright is tuned.

### Honest Caveat

The agent-browser 7,000-token figure is from a generic 10-step benchmark, not an FLS-specific measurement. An FLS QA run involves login flows, cohort/course navigation, and paginated views — more complex than a generic benchmark. The snapshot filtering options (`-i`, `-c`, `-d`, `-s`) do allow the agent to request only interactive elements at a limited depth, which is well-matched to the FLS pattern of navigating to a specific view and verifying elements. The ~93% reduction claim (from paddo.dev) is directionally right but the absolute number depends heavily on page complexity.

---

## 3. The Depth-1 / Parallelism Unlock (the crux)

### What the Constraint Actually Is

From `idea.md` and `research_parallel_qa_and_model_tiering.md`:
- Playwright MCP is available only at depth 0 — this is because it is an MCP server listed in `.mcp.json`, and MCP server configurations are set before session startup. A subagent cannot receive MCP tools.
- `sdd-worker.md` and `qa-data-helper.md` frontmatter confirm: no `mcp__playwright*` in tools at depth 1.

### What agent-browser Changes

`agent-browser` is invoked via `Bash`, not via MCP tools. The constraint that blocks MCP at depth 1 **does not apply to Bash**. An agent with the `Bash` tool can run `agent-browser open ...`, `agent-browser snapshot`, `agent-browser click @e1` etc. as standard shell commands.

**So yes: any depth-1 agent that has the `Bash` tool can drive a browser via agent-browser.** Currently:

- `fls:qa-data-helper` has `Bash` in its tools frontmatter
- `fls:sdd-worker` does NOT have `Bash` in its tools frontmatter (tools: Read, Glob, Grep, WebFetch, WebSearch, Write)
- `fls:sdd-mechanic` (Haiku): tools not verified here but typically limited

**To enable 3-way parallel viewport QA via depth-1 fan-out, FLS would need:**

1. A new spawnable agent (e.g. `fls:qa-viewport-agent`) with `Bash` in its tools list and `agent-browser` allow-listed in permissions (see section 4)
2. `agent-browser` installed and `agent-browser install` run once (downloads Chrome)
3. `npx skills add vercel-labs/agent-browser` run once to plant the SKILL.md stub
4. Each viewport worker gets its own session name (`--session desktop`, `--session mobile`, `--session tablet`) and hits its own runserver port

### Session Isolation Reality Check

This is where the picture gets complicated. There are two isolation mechanisms:

**`--session <name>` flag (daemon-mode):** The official docs say each session has its own "browser instance, cookies and storage, navigation history, authentication state." However, GitHub issue #1068 documents a **known limitation**: the `--session` flag provides tab-namespace isolation only; it does *not* call CDP `Target.createBrowserContext`, so storage (cookies, localStorage, sessionStorage) leaks between sessions when multiple agents connect to the same running daemon/Chrome instance.

**`--profile <name>` flag:** Creates separate Chrome processes (separate `--user-data-dir`), giving true OS-level process isolation — same model as Playwright's `isolated: true`. True isolation, but heavier: separate Chrome process per viewport, similar resource cost to separate Playwright MCP instances.

**Verdict for FLS parallel QA:** If the three viewport workers each use `--profile` (not just `--session`), isolation is complete but each launches its own Chrome process. This is equivalent resource cost to the Playwright-MCP three-process approach. The theoretical simplicity advantage (no external orchestrator) is real — the fan-out is standard depth-0 → depth-1 agent spawning — but `--session` alone is not enough; `--profile` is required for actual storage isolation, and that's heavier.

### Comparison: agent-browser fan-out vs Playwright-MCP external orchestrator

| | Playwright MCP + external orchestrator (Phase 4) | agent-browser depth-1 fan-out |
|---|---|---|
| Where browser drivers run | 3 separate top-level Claude sessions | 3 depth-1 subagents from one depth-0 session |
| How orchestrated | External shell script launches 3 `claude` processes | Standard `Agent` tool fan-out (same as today) |
| Browser isolation | Separate Playwright MCP servers, distinct `--user-data-dir` | `--profile` flag (separate Chrome processes) |
| Tool grants needed | Each top-level session needs `mcp__playwright*` | Each worker needs `Bash` + agent-browser allow-list |
| Report merge | Shell script merges 3 separate `qa_report.md` files | depth-0 collects structured returns from 3 agents |
| Complexity | High — external orchestrator, 3 sessions, merge script | Low-medium — normal fan-out + a new agent file |
| Dependencies | `@playwright/mcp` per session | agent-browser binary + Chrome (one-time install) |
| Pre-1.0 churn risk | Low (Playwright is stable) | Medium (v0.27.x, weekly releases) |

**The parallelism unlock via agent-browser is genuinely simpler than the external-orchestrator approach.** The fan-out model is already native to FLS's SDD architecture. The external-orchestrator approach is architecturally foreign and requires building a new harness. This is a real advantage.

**The catches:**
1. Session isolation requires `--profile` (separate Chrome processes), not just `--session`; this partially negates the "lighter weight" argument
2. The daemon is shared; if three workers all issue commands to the same daemon simultaneously there may be ordering/race issues at the daemon level — this is not well-documented for high-concurrency local use
3. Pre-1.0 churn: a flag rename or behavior change in a minor version could silently break the parallel setup
4. The SKILL.md stub requires `agent-browser skills get core` to be run at startup — this is a Bash call that must complete before the worker can start driving the browser; not a blocker but adds a step

---

## 4. Interaction with FLS's Churn Problem

### security-guard.sh Audit

The hook (`security-guard.sh`) blocks on `Bash` calls only the following patterns:
- `rm -rf` in the command string
- `.env` access (not `.env.example`)
- `id_rsa`, `.pem`, `.key` access

**`agent-browser` commands do not match any of these patterns.** A command like `agent-browser open http://127.0.0.1:8000/` or `agent-browser snapshot -i --json` will not be blocked by security-guard.sh.

### Current Allow-list Gap

The current `.claude/settings.json` does not include any `Bash(agent-browser *)` entry. Any `agent-browser` call would hit the default prompt (requires user approval) unless allow-listed. The fix is a single line:

```json
"Bash(agent-browser *)"
```

added to the `allow` array. One wildcard covers all agent-browser subcommands (`open`, `snapshot`, `click`, `type`, `screenshot`, `batch`, `skills`, etc.).

### Net Effect on Churn

Playwright MCP drives the browser via MCP protocol tools — the `mcp__playwright__*` allow-list entry is already in `settings.json` and covers all Playwright tool calls without prompts. Replacing or complementing Playwright with agent-browser via `Bash` would require adding the `Bash(agent-browser *)` allow-list entry — one addition.

However, Bash calls have a different risk profile from MCP tool calls in the context of cascade-cancel: each `agent-browser` Bash call is an independent process invocation. The idea's Phase 1 resilience rules already specify "never batch a permission-prone Bash call with a Playwright call" — a similar discipline would need to apply to agent-browser calls (issue each as a solo call, not batched with other Bash calls). This is not worse than today, just analogous discipline.

**Net: agent-browser does not worsen the churn problem. The security guard does not block it. One allow-list entry makes it prompt-free. The existing batching discipline applies equally.**

---

## 5. Migration Cost and Risks

### What Would Change in `do_qa.md`

Currently `do_qa.md` includes:
- `allowed-tools: Read, Write, Glob, Bash, Agent, mcp__playwright*`
- Steps 3–7: explicit `mcp__playwright` tool usage for navigate, snapshot, click, screenshot

Replacing Playwright MCP with agent-browser would require:
- Removing `mcp__playwright*` from `allowed-tools`
- Replacing all Playwright-specific step descriptions with agent-browser CLI commands
- Rewriting Steps 3–7 around `agent-browser open`, `snapshot`, `click`, `screenshot`
- Agent needs to internalize the `@e1`/`@e2` ref system instead of CSS selectors/accessibility tree navigation

This is a substantial rewrite of the command's core browser-driving section — not a trivial config change.

### What Is LOST by Replacing Playwright MCP

- **Cross-browser coverage.** Playwright supports Chromium, Firefox, WebKit. agent-browser is Chrome-only. FLS QA currently runs on Chromium; this is not a regression but forecloses future multi-browser coverage.
- **Playwright Test Agents / Healer ecosystem.** Microsoft's v1.56 Planner/Generator/Healer pipeline (which generates reusable `.spec.ts` files from MCP-driven QA runs) becomes unavailable. This is a significant future-path closure — the hybrid MCP-exploration → test-runner re-verification workflow documented in `research_playwright_mcp_efficiency.md` depends on Playwright's official toolchain.
- **Codegen and `.spec.ts` generation.** `npx playwright codegen` for recording flows is inapplicable.
- **Official Microsoft ecosystem support.** Playwright MCP is backed by Microsoft; agent-browser is a Vercel Labs project. Support trajectory differs.
- **Proven FLS integration.** Playwright MCP works today. agent-browser would need onboarding, testing, and validation.

### What Is GAINED

- ~7,000 vs ~114,000 tokens per 10-step flow (vs ~27,000–50,000 after Phase 1 tuning of Playwright)
- Depth-1 browser driving (enables Phase-4 viewport parallelism as normal fan-out)
- No MCP protocol overhead; sub-100ms command round-trips via persistent daemon
- Cloud provider integrations (Browserbase, Browserless, etc.) — not relevant for FLS local dev QA
- Auth Vault and domain allowlists — not relevant for local dev server QA
- Content boundaries feature (`--content-boundaries`) — potentially useful for preventing page-injected content from polluting agent context

### Security Features Relevance for FLS Local Dev QA

- **Domain allowlists**: Could lock the agent to `127.0.0.1` only — useful for preventing accidental navigation to production. Potentially valuable.
- **Action policies**: Could gate destructive actions (form submissions that write data). Low priority — QA uses a dev database.
- **Auth Vault**: Not relevant; FLS stores admin credentials in `.claude/fls/config.md`.
- **Browserbase/Browserless**: Not relevant; FLS QA runs against a local dev server.

---

## 6. Recommendation: Complement, Replace, or Pass

### Honest Assessment

The parallelism unlock is real but overstated when examined carefully:

1. **The token savings are real.** Even after Phase 1 Playwright MCP tuning (~50–70% cut), agent-browser's ~7,000-token per-workflow figure is still 2–5x cheaper. For a 3-viewport run, the difference is meaningful.

2. **The depth-1 parallelism unlock is real.** Standard depth-0 → depth-1 fan-out via the `Agent` tool can drive three browser workers simultaneously — no external shell orchestrator needed. This is a genuine architectural simplification vs the Playwright Phase-4 approach.

3. **BUT session isolation requires `--profile` not just `--session`.** The `--session` flag shares a Chrome context (cookies/storage leak). `--profile` gives true isolation but means three separate Chrome processes — same resource cost as three Playwright instances. The "lighter weight" argument partially evaporates.

4. **The pre-1.0 churn risk is real.** Weekly releases, pre-1.0 versioning, occasional flag-level breaking changes. Building FLS's QA automation on a pre-1.0 tool is a maintenance commitment: pinning a specific version and re-testing on upgrade becomes necessary.

5. **Migration cost is high** (rewriting do_qa.md's core browser section, losing the Playwright Test Agents / Healer path, Chrome-only lock-in).

6. **Phase 1–3 should land first.** The diff-scoping gate (Phase 1) eliminates the 3-viewport matrix for most runs. After Phase 1–3 are in place, if the matrix is still the bottleneck, the question of which parallelism path is cheaper becomes relevant. Building on agent-browser before Phase 1–3 is premature optimization.

### Recommendation: Spike first; do not replace yet

**Do not replace Playwright MCP now.** The existing decision ("Replacing Playwright MCP wholesale — MCP is the right tool for the exploratory role; we tune it and add a deterministic fast-path, we don't replace it") stands through Phase 1–3. The combination of: (a) `imageResponses: "omit"`, (b) `capabilities: ["core","testing"]`, (c) diff-scoping gate, (d) model tiering for post-browser steps — addresses the major cost and churn drivers without abandoning Playwright's ecosystem.

**Run a spike before committing to Phase 4.** The Phase 4 decision (external orchestrator vs agent-browser fan-out) should be informed by real data. The spike below is the right gate.

---

## Recommendation for FLS: Concrete Spike Plan

**Goal:** Determine whether agent-browser's depth-1 fan-out is genuinely viable for FLS parallel viewport QA before reopening the "don't replace Playwright MCP" decision.

**Prerequisite:** Phase 1 (Playwright MCP config tuning + diff-scoping gate) is implemented and baseline token/wall-clock numbers are recorded.

### Step 1 — Install and validate (1–2 hours)

```bash
# Install the CLI binary (downloads via npm; no Rust needed)
npm install -g @agent-browser/cli   # or follow the install instructions at agent-browser.dev
agent-browser install               # downloads Chrome for Testing
npx skills add vercel-labs/agent-browser  # plants SKILL.md stub
```

Manually run `agent-browser open http://127.0.0.1:PORT/` against a live FLS dev server and verify that `agent-browser snapshot -i` returns a usable accessibility tree for FLS's login page and a course list page. Check snapshot size (token count) vs a Playwright MCP snapshot for the same pages.

**Pass criteria:** snapshot is parseable, refs (`@e1`, `@e2`) correctly identify key interactive elements, snapshot size is visibly smaller than Playwright MCP's output for the same pages.

### Step 2 — Drive one FLS flow; measure tokens (2–3 hours)

Write a minimal `do_qa_agentbrowser_spike.md` agent that:
1. Opens the FLS dev server at a given port
2. Logs in using credentials from `.claude/fls/config.md`
3. Navigates to a course list, clicks into one course, verifies one element
4. Takes a screenshot to disk
5. Reports `status: ok` with a token count from the Claude session

Run the same flow with the current Playwright MCP setup (Phase-1 tuned config) and record token counts.

**Pass criteria:** agent-browser total tokens < 20,000 for this 5-step flow; no element targeting failures (ref stability on FLS's Django/HTMX pages).

### Step 3 — Prove 2-session parallel isolation (2 hours)

Spawn two depth-1 workers from a depth-0 script, each using `--profile desktop` / `--profile mobile`. Each worker:
- Hits a separate runserver port
- Logs in as a different user
- Takes a screenshot
- Returns `{session, screenshot_path, user_email, status}`

Verify that the two screenshots show the correct user's data (no session leakage between profiles).

**Pass criteria:** zero cross-session leakage; both workers complete without daemon-level race conditions.

### Step 4 — Go/no-go decision

If Steps 1–3 all pass:
- Create `fls:qa-viewport-agent` with `Bash` tool and `agent-browser` skills
- Add `"Bash(agent-browser *)"` to `.claude/settings.json` allow list
- Prototype Phase 4 as agent-browser fan-out in a feature branch

If any step fails (element targeting flakiness, session leakage, token counts not better than tuned Playwright):
- Close the spike, keep Phase 4 as the external-orchestrator-with-Playwright approach
- Note specific failure modes in this file for future re-evaluation

**The spike is cheap (a day's work) and definitively answers whether the parallelism unlock is real enough to justify changing course.**

---

## References

- [GitHub: vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
- [agent-browser.dev sessions documentation](https://agent-browser.dev/sessions)
- [agent-browser.dev skills documentation](https://agent-browser.dev/skills)
- [Issue #1068: CDP BrowserContext support for cookie-isolated parallel sessions](https://github.com/vercel-labs/agent-browser/issues/1068)
- [Why Vercel's agent-browser Is Winning the Token Efficiency War — DEV Community](https://dev.to/chen_zhang_bac430bc7f6b95/why-vercels-agent-browser-is-winning-the-token-efficiency-war-for-ai-browser-automation-4p87)
- [Vercel's agent-browser: Why a CLI Beats MCP for Browser Automation — isagentready.com](https://isagentready.com/en/blog/vercel-agent-browser-why-a-cli-beats-mcp-for-browser-automation)
- [Playwright CLI vs agent-browser vs Claude in Chrome — token benchmark 2026 (ytyng.com)](https://www.ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026)
- [The Context Wars: Why Your Browser Tools Are Bleeding Tokens — paddo.dev](https://paddo.dev/blog/agent-browser-context-efficiency/)
- [How to run parallel AI agents for browser automation — howdoiuseai.com](https://www.howdoiuseai.com/blog/2026-03-21-how-to-run-parallel-ai-agents-for-browser-automati)
- [Parallel Browser Agents: How to Run Multiple Claude Code Instances — MindStudio](https://www.mindstudio.ai/blog/parallel-browser-agents-claude-code)
- [Introducing skills, the open agent skills ecosystem — Vercel changelog](https://vercel.com/changelog/introducing-skills-the-open-agent-skills-ecosystem)
- [Agent Browser vs Puppeteer & Playwright — Webfuse](https://www.webfuse.com/blog/agent-browser-vs-puppeteer-and-playwright)

---

status: ok
reason: all 6 research questions answered with citations; honest assessment of parallelism unlock, session isolation limitation, pre-1.0 churn risk, and migration cost; concrete spike plan provided
