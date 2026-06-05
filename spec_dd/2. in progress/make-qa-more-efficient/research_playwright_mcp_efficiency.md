# Research: Playwright MCP Efficiency for FLS QA

This document answers whether `@playwright/mcp` is the right browser-automation tool for the
FLS `/do_qa` command, and what concrete changes would make it cheaper and faster.

---

## 1. Token Cost Drivers in Playwright MCP

**The core problem: every tool call streams a full accessibility snapshot inline into the LLM context.**

Each `browser_snapshot` (or any navigation/interaction call that auto-attaches a snapshot)
returns the page's full accessibility tree as structured text. This accumulates in conversation
history and is re-sent to the model on every subsequent turn.

Measured costs from independent benchmarks (2026):

| Mode | Tokens per 8-step authenticated workflow |
|------|------------------------------------------|
| MCP (default) | ~114,000 |
| MCP (with screenshots) | up to 232,000+ (can exceed a 200k context window for a single full-page screenshot) |
| Playwright CLI (file-based) | ~27,000 |

**What drives the cost, in order of impact:**

1. **Inline snapshots on every turn.** After every action (`browser_click`, `browser_navigate`,
   etc.) the full accessibility tree is streamed back. A simple form page costs ~3,800 tokens
   per snapshot; a dense dashboard can hit 50,000+ tokens per snapshot.

2. **Snapshot accumulation.** Snapshots are not deduplicated. After 6 tests with 5 steps each,
   30 full snapshots are sitting in context. The model reprocesses stale, identical data
   on every new call.

3. **Screenshot embedding.** `browser_take_screenshot` base64-encodes the image and streams it
   directly into context. A single full-page screenshot at default resolution has been measured at
   232,000 tokens — more than a 200k context window can hold. The FLS `do_qa` command takes
   screenshots at every test step across 3 viewports, making this the single biggest token sink.

4. **Tool schema overhead.** ~4,200 tokens are consumed at session start by the tool definitions
   alone before any page interaction occurs.

**Snapshot vs vision mode:** The default (snapshot) mode is actually the *cheaper* mode.
Vision mode replaces the accessibility tree with pixel-based screenshots for interaction —
strictly more expensive for token cost. The snapshot approach is correct for FLS; the problem
is the *screenshots* taken for the QA report, not the snapshot-based interaction.

**Snapshot size in practice:** Accessibility tree snapshots are 50–100 KB of text. That
translates to roughly 3,800–50,000 tokens depending on page complexity. The playwright.dev
documentation claims "200–400 tokens per snapshot" but that appears to refer to a minimal/
targeted snapshot, not a full page tree; real-world measurements consistently show much larger
figures for content-rich pages.

---

## 2. Config Knobs to Cut Cost and Latency

The official `@playwright/mcp` server (as of v0.0.x, 2026) exposes these levers:

### In `.mcp.json` (config file passed via `--config`)

```json
{
  "imageResponses": "omit",
  "snapshot": {
    "mode": "incremental"
  },
  "capabilities": ["core"],
  "browser": {
    "headless": true,
    "isolated": true
  },
  "outputDir": "/tmp/pw-mcp-output",
  "outputMode": "file"
}
```

**`imageResponses`**: `"allow" | "omit" | "auto"` (default: `"auto"`)
- Set to `"omit"` to prevent screenshots from being base64-encoded and streamed into context.
  This is the single highest-leverage change for the FLS use case. Screenshots are still *taken*
  and saved to `outputDir`, but the image bytes do not enter the LLM context window.
  The QA report uses `![](screenshots/...)` markdown references anyway — the bytes don't need
  to be in context for that to work.

**`snapshot.mode`**: `"full" | "incremental" | "none"` (default: `"incremental"` in recent versions)
- `"incremental"` sends only the diff from the previous snapshot — the correct default for
  interactive sessions; it dramatically reduces repeated context.
- `"none"` disables automatic snapshot attachment to responses entirely. The agent must
  explicitly call `browser_snapshot` when it needs to see the page state. Useful for actions
  where you *know* no page inspection follows (e.g. a click that triggers a navigation you
  verify separately). Risky if overused — the agent loses situational awareness.
- `"full"` (old default) sends the entire tree every time — avoid this.

**`capabilities`**: comma-separated list
- Default loads all capabilities. Loading only `["core"]` or `["core", "testing"]` omits
  vision, PDF, devtools, network-logging tools from the tool schema, saving ~4,200 tokens of
  schema overhead per session and preventing accidental tool use.
- For FLS QA: `["core", "testing"]` is sufficient. "vision" should be excluded to discourage
  the agent from reaching for screenshot-based interaction tools.

**`headless: true`**
- Reduces system overhead; no visible browser window. Appropriate for CI and automated QA runs.
  FLS currently uses the default (headed). Switching saves CPU/memory but not tokens directly.

**`isolated: true`**
- Each session gets a fresh in-memory browser profile. Prevents state leakage between QA runs.
  Good hygiene; the current `.mcp.json` has no isolation setting.

**`outputDir`**
- Screenshots saved to this directory instead of streamed inline. Combine with
  `imageResponses: "omit"` to get file-based screenshot artifacts without context bloat.

**`outputMode: "file"`**
- Writes snapshots to disk as YAML files and returns file paths rather than inline content.
  This is the key difference between MCP and the Playwright CLI approach: the CLI *always*
  does this; MCP only does it when configured. When set, the agent can request a specific
  snapshot file if it needs to inspect page state, rather than receiving it automatically.

### Blocking images and CSS at the network level

The `@playwright/mcp` config supports `network.blockedOrigins` but not
resource-type-level blocking natively. However, resource blocking (images, stylesheets, fonts)
can be injected via `browser.contextOptions.extraHTTPHeaders` or an init script that calls
`route.abort()`. For a QA run against a local dev server this has limited value: the page
*looks* broken without CSS, which defeats visual QA. Do not block CSS for the FLS use case.

---

## 3. Parallelism within Playwright MCP

**Official `@playwright/mcp` is single-threaded per server instance.**

One MCP server controls one browser instance. Within that browser it supports multiple tabs
(via `browser_tabs` tool), but tabs share the same browser process and context unless explicitly
configured with `isolated: true` per session.

**Concurrent testing options:**

- **Multiple MCP server instances on different ports.** You can launch N processes of
  `@playwright/mcp --port 9001`, `--port 9002`, etc. and have parallel Claude Code agents
  connect to each. The orchestrating agent (depth-0) can fan out sub-agents each with their
  own MCP connection. This is the most viable parallelism approach.
  Constraint: each instance starts its own Chromium process — memory/CPU costs multiply.

- **`sharedBrowserContext: true`** (config option). Multiple HTTP clients share the same
  browser context. This is for multi-agent read-mostly collaboration, not parallelism — shared
  context means shared state and race conditions for a QA workflow.

- **Third-party forks for parallelism.** `concurrent-browser-mcp` and
  `playwright-parallel-mcp` (both on npm/GitHub, 2025) address this by spawning independent
  MCP backend processes per session. These are community forks, not the official Microsoft
  server, so they trail feature parity.

**For FLS `/do_qa`:** The command runs 3 viewports (desktop/mobile/tablet) sequentially.
Splitting these into 3 parallel sub-agents each with their own MCP instance on separate ports
would be the highest-impact parallelism change. Each viewport agent is independent — no shared
state required. This could cut wall-clock time by ~60% for the multi-viewport phase.

---

## 4. Alternatives and When They Win

### Playwright Test Runner (`@playwright/test` + codegen)

**What it is:** The deterministic test runner. You write `.spec.ts` files with `expect()`
assertions; Playwright runs them in parallel workers with HTML reports, trace viewer, and CI
integration. `npx playwright codegen <url>` records a browser session and generates the initial
`.spec.ts`.

**Token cost:** Near zero once tests are written. Running `npx playwright test` costs no LLM
tokens at all. The LLM is only involved in the one-time generation step (~$0.02–$0.08 per test
with a fast model like Claude Haiku).

**Speed:** Much faster for re-checking. A suite of 20 deterministic tests runs in parallel
workers in 10–30 seconds vs 5–15 minutes for MCP-driven QA.

**Tradeoff vs MCP:**

| | Playwright MCP (current) | Playwright test runner |
|--|--|--|
| Good for | Exploratory QA, new features, visual layout checks | Regression: re-verify after fixes |
| Human-likeness | High — explores, notices unexpected things | None — only checks what was specified |
| Token cost | Very high (114k+ per run) | Essentially zero (run-time) |
| Speed | Slow (sequential, interactive) | Fast (parallel, deterministic) |
| Viewport coverage | Flexible, ad-hoc resize | Must be configured per project |
| Maintenance | Zero (regenerates each run) | Tests break when UI changes (needs healer) |
| Best trigger | Feature PR, visual review | Fix verification, regression gate |

**Playwright Test Agents (v1.56, 2026)**
Microsoft added a built-in Planner/Generator/Healer agent pipeline to Playwright. The Planner
explores the live app and writes `test-plan.md`; the Generator compiles it into `.spec.ts`
files; the Healer repairs broken locators after failures. This is the official answer to
"MCP for exploration, test runner for execution." It still uses LLM tokens for generation,
but the generated tests are reusable — cost amortizes across many re-runs.

### Chrome DevTools MCP

An alternative MCP server that drives Chrome via the DevTools Protocol directly rather than
through Playwright's abstraction layer. Closer to the metal, can expose JS heap / performance
profiles, useful for debugging. Not a better choice for user-facing QA — less reliable for
interaction, fewer accessibility-tree conveniences. Not recommended for FLS.

### `browser-use` (Python)

A Python library that gives LLMs a browsing agent using Playwright under the hood, with
built-in vision + DOM combination approach. More suited to autonomous agent workflows than
structured QA. Heavier setup, introduces a Python agent loop. Not a good fit for FLS which
already has a well-structured `do_qa` command.

### The hybrid recommendation from practitioners

The consensus (2025–2026) is: **MCP for exploration / new territory, CLI/test runner for
repetition.** The moment a QA scenario is understood and stable, generate a `.spec.ts` for it.
The MCP run that produced the first QA report is the exploration step; subsequent re-runs to
verify a specific fix belong to the test runner.

---

## 5. Recommendations for FLS

### Immediate wins (change `.mcp.json` and the `do_qa` command today)

- **Set `imageResponses: "omit"` in `.mcp.json`.** This is the single highest-impact change.
  Screenshots are written to `outputDir` but do not enter the LLM context. The QA report
  references them as file paths anyway. Estimated saving: 50–70% of total tokens per run.

- **Set `snapshot.mode: "incremental"` in `.mcp.json`.** Already the default in recent versions,
  but make it explicit to future-proof against default changes. Prevents full-tree resends on
  every turn.

- **Set `capabilities: ["core", "testing"]`** (omit `vision`, `pdf`, `devtools`, `network`).
  Removes ~4,200 tokens of tool-schema overhead and prevents the agent reaching for
  screenshot-based interaction tools.

- **Set `headless: true`** for unattended QA runs. Saves CPU; no functional impact on QA output.

- **Set `isolated: true`** to prevent session state leakage between runs.

Updated `.mcp.json`:
```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--headless",
        "--isolated",
        "--image-responses", "omit",
        "--caps", "core,testing"
      ],
      "env": {}
    }
  }
}
```

Or via a config file (`playwright.mcp.config.json`) passed as `--config`:
```json
{
  "browser": {
    "headless": true,
    "isolated": true
  },
  "imageResponses": "omit",
  "snapshot": { "mode": "incremental" },
  "capabilities": ["core", "testing"],
  "outputDir": "./screenshots"
}
```

### Medium-term: Scope the QA run to only what changed

- The current `do_qa` command runs the full plan every time regardless of the diff. Add a
  pre-step that reads `git diff --name-only HEAD~1` and prunes the test plan to only the
  affected views/components before running. A CSS-only change in `student_interface` does not
  need educator-interface tests.

- Consider scoping desktop vs mobile/tablet by change type: template changes warrant all 3
  viewports; Python-only changes (model/view logic) need only one viewport for smoke testing.

### Medium-term: Parallelize the 3-viewport phases

- Run desktop, mobile, and tablet phases as 3 parallel sub-agents, each connecting to its own
  MCP server instance on a different port (e.g. 9001, 9002, 9003). This requires the depth-0
  `do_qa` agent to fan out 3 workers via the `Agent` tool and merge their reports.
- Expected wall-clock reduction: ~60% for the browser-interaction phase.

### Longer-term: Complementary fast-path with Playwright test runner

For the "re-check after fix" loop:

1. During the MCP-driven QA run, have the agent also emit a `spec_draft.ts` alongside the
   `qa_report.md` — a rough Playwright test covering the scenarios it just walked.
2. A human or LLM (with a cheap model) polishes the spec draft into a runnable `.spec.ts`.
3. On subsequent fix-verify loops: run `npx playwright test` instead of re-running `/do_qa`.
   Cost: near zero. Speed: <60 seconds. The full MCP run is reserved for the final sign-off.

This directly addresses the stated pain: "even for simple changes, QA takes a long time."
A fix that touches one view should be verifiable in under a minute, not 10–15 minutes.

### Keep Playwright MCP — it is the right tool for the exploration role

The `/do_qa` command's strength is its human-like exploratory quality: it notices unexpected
things, checks real rendered output, and adapts to missing data via `fls:qa-data-helper`. No
deterministic test runner can replicate this. The goal is not to replace MCP but to:
1. Make each MCP run cheaper (config changes above)
2. Move repeat-verification work off MCP and onto the test runner

---

## References

- [One screenshot, 232,000 tokens — Medium (May 2026)](https://medium.com/@7003425114klp/one-screenshot-232-000-tokens-0b37783438c7)
- [Playwright MCP Burns 114K Tokens Per Test — ScrollTest/Medium](https://scrolltest.medium.com/playwright-mcp-burns-114k-tokens-per-test-the-new-cli-uses-27k-heres-when-to-use-each-65dabeaac7a0)
- [Playwright MCP Setup and Cost: Why the CLI Is 4x Cheaper — MorphLLM](https://www.morphllm.com/playwright-mcp)
- [Playwright MCP Configuration Options — playwright.dev](https://playwright.dev/mcp/configuration/options)
- [Playwright MCP Snapshots — playwright.dev](https://playwright.dev/mcp/snapshots)
- [Playwright MCP Introduction — playwright.dev](https://playwright.dev/mcp/introduction)
- [GitHub: microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)
- [Token use optimization issue #1216 — microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp/issues/1216)
- [Optimize browser_snapshot issue #915 — microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp/issues/915)
- [Playwright MCP vs CLI vs Agents: What to Use in 2026 — Halmurat Tahir](https://www.halmurattahir.com/blog/ai-testing/playwright-mcp-vs-cli-vs-agents-2026/)
- [Playwright Test Agents & MCP: 2026 Architecture Guide — TestQuality](https://testquality.com/playwright-test-agents-mcp-architecture-2026/)
- [The Complete Playwright End-to-End Story — Microsoft Developer Blog](https://developer.microsoft.com/blog/the-complete-playwright-end-to-end-story-tools-ai-and-real-world-workflows)
- [Playwright AI Test Generation: Complete 2026 Guide — BuildBetter](https://blog.buildbetter.ai/playwright-test-generation-with-ai-complete-2026-guide/)
- [Playwright in 2026: Raw Scripts, AI Agents, or Both? — Qate AI](https://qate.ai/blog/playwright-vs-ai-testing)
- [Playwright MCP + LLM Architecture — ScrollTest](https://scrolltest.com/playwright-mcp-llm-architecture-ai-augmented-test-automation/)
- [Concurrent Browser MCP — mcpmarket.com](https://mcpmarket.com/server/concurrent-browser)
- [playwright-parallel-mcp — GitHub/sumyapp](https://github.com/sumyapp/playwright-parallel-mcp)
- [Fast Playwright MCP (tontoko) — npm](https://www.npmjs.com/package/@tontoko/fast-playwright-mcp)

---

status: ok
reason: all 5 research questions answered with cited sources; concrete FLS recommendations provided
