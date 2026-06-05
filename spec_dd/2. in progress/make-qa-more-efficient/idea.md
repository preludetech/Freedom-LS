# Make QA more efficient

## Problem

The `do_qa` step of our SDD process takes a **long** time and burns a **lot** of tokens, even
for trivial changes. Two distinct things are going wrong:

1. **Cost & latency.** `/do_qa` drives Playwright MCP through a full desktop/mobile/tablet matrix
   for every run regardless of what changed. The dominant token sinks are: screenshots streamed
   into context (a single full-page screenshot can exceed a 200k context window), full
   accessibility snapshots re-sent on every turn, and the whole report-assembly tail running on
   the strong session model. A simple one-view change costs as much as a full feature.

2. **Churn / getting stuck.** Parallel tool batches **cascade-cancel** when any one call is
   rejected (a denied permission prompt, or the `security-guard.sh` hook returning exit 2 on
   `rm -rf`). After a hook block, Claude tends to stall and wait for a nudge. `cd X && …`
   compound commands trigger their own permission prompts. Together these made early QA runs loop
   and churn even on the simplest tasks.

## Goals

- Cut tokens and wall-clock for the common case (small changes) without losing the human-like
  exploratory quality that makes `/do_qa` valuable.
- Stop the cascade-cancel / hook churn so QA runs don't get stuck.
- When QA finds a clear, fixable bug, **fix it automatically (TDD-style) and re-verify**, instead
  of just filing a todo for a human.

## Decisions taken (from idea review)

- **Scope: everything**, including the parallel multi-session browser harness — but sequenced so
  the cheap, high-ROI wins land first and parallelism comes last.
- **The TDD bug-fix loop runs automatically inside `/do_qa`** (triage → fix → re-verify in one
  run), not as a separate human-gated command.
- **Screenshots are file-first but vision stays available**: screenshots are written to disk for
  the report and kept out of context by default, but the agent may deliberately pull a screenshot
  into context when it genuinely needs to judge a visual layout (mobile/tablet overflow/overlap).

## Hard constraints to respect (these shape every option below)

- Fan-out is **depth-0 only**; subagents cannot nest or spawn further subagents.
- **Playwright MCP is granted to `/do_qa` (depth 0) only** — `sdd-worker`, `qa-data-helper`, etc.
  do not have it. One MCP server = one browser, so the three viewports are serial within a single
  session.
- Subagents can't call `AskUserQuestion`; they fail-fast with `status: blocked`.
- Model tiering only works on **spawnable agent files** (`model:` frontmatter). A command/helper
  followed *inline* keeps the caller's (session) model.
- The `security-guard.sh` hook blocks `rm -rf`, raw SQL, and unsafe-HTML/eval patterns and
  **cannot** be overridden by an allow-list — prefer script-wrapping over weakening it. Pre-commit
  runs ruff+mypy+pytest on every commit.

## The plan, sequenced by ROI

### Phase 1 — Cheap wins (config + scoping + resilience)

These are mostly config/wording changes with the biggest payoff per unit of effort.

- **Tune the Playwright MCP config** (`.mcp.json` / a `--config` file): file-based screenshot
  output to keep image bytes out of context by default, explicit incremental snapshot mode, trim
  capabilities to `core,testing` (drops ~4k tokens of tool schema and the vision interaction tools
  we don't want), `headless`, `isolated`. Keep vision *available* so the agent can choose to view a
  screenshot when judging layout (per the decision above). Expected ~50–70% token cut.
- **Diff-scoping gate** before the server starts: classify `git diff main...HEAD --name-only` as
  `FULL` / `ADMIN_ONLY` / `BACKEND_ONLY` and skip or shrink the responsive viewports accordingly.
  Admin-only and backend-only changes rarely need mobile/tablet. Biggest wall-clock win for the
  common case, and it largely removes the *need* for viewport parallelism.
- **Smoke gate** before the full matrix: load home + the primary changed page; abort early with a
  report if there's a 500/404/missing element, instead of walking 20 tests after a crash-on-load.
- **Resilience / anti-churn rules** baked into `/do_qa` plus allow-list additions:
  - Add a "batching safety" rule block: never batch a permission-prone Bash call with a Playwright
    call; issue server-start, cleanup, and `Agent` spawns **solo**; no `cd` before commands (use
    absolute / CWD-relative paths); never run raw `rm -rf` — only committed wrapper scripts.
  - Add allow-list entries in `.claude/settings.json` for the QA scripts/commands so they never
    prompt (runserver, port finder, cleanup, compress). Consolidating QA scripts under
    `.claude/fls/scripts/` lets one wildcard cover them.

### Phase 2 — Model tiering of the cheap tail

Move the non-judgement steps off the strong session model onto spawned agents (the only place
tiering works):

- Screenshot compression → `fls:sdd-mechanic` (Haiku).
- Report assembly → have depth-0 write a structured scratch list (`{test_id, viewport, status,
  screenshot_path, notes}`) as it goes, then `fls:sdd-worker` (Sonnet) renders `qa_report.md` from
  the *file* — keeping the long synthesis off the saturated depth-0 context.
- Confirm the `todo.md` update already spawns `fls:sdd-mechanic` rather than inlining it.
- Discipline: pass **file paths, not snapshot/screenshot contents** between steps; never replay raw
  Playwright output back into the depth-0 context.
- The browser-driving itself stays at depth 0 on the session model — that judgement is the core
  value and must not be tiered down.

### Phase 3 — Automatic TDD bug-fix + re-verify loop

Close the README's "Command for reacting to QA-reported bugs" TODO, in-line inside `/do_qa`:

- **New spawnable agent `fls:qa-bugfixer`** (`model: sonnet`; tools: Bash, Read, Edit, Write,
  Glob, Grep). TDD sequence: write a **failing** test that reproduces the bug → confirm RED →
  minimal fix → confirm GREEN → run full `pytest` → `uv run git commit` (pre-commit gate fires).
  Reports via a structured `.sdd-work/bugfix_<slug>.md` (status/root-cause/fix/commit/suite-result).
- **Triage at depth 0 before spawning** ("make good decisions about what bugs to fix"). Green lane
  (auto-fix) only when *all* hold: clear functional regression in the feature under test •
  unit-testable without a browser • root cause in one app • no product/UX decision • no schema
  migration • not security-adjacent. Otherwise red lane → record UNRESOLVED + human todo.
- **Re-verify** after a successful fix: trust the fixer's pytest pass for the regression layer,
  then depth-0 re-drives **only the specific Playwright flow** that failed, plus 2–3 adjacent
  spot-checks if the fix touched shared code. Not the whole plan.
- **Loop guard:** max 1 fix attempt per bug per run. On fixer failure / broken suite / re-check
  failure → safe revert (`git checkout -- <files>`, never `reset --hard` without explanation) and
  escalate to a human todo. `qa_report.md` ends with each bug marked FIXED (with commit) or
  UNRESOLVED.

### Phase 4 — Viewport parallelism (highest effort, do last)

Genuinely parallel desktop/mobile/tablet needs an **external orchestrator** launching separate
top-level Claude sessions, each with its **own** Playwright MCP server (distinct `--user-data-dir`
or `playwright-parallel-mcp`) on its **own** runserver port, then a merge step combining three
reports. It cannot be done from inside one session or via subagents (no MCP at depth 1). Build this
**only after Phases 1–3** — the diff-scoping gate already eliminates the viewport matrix for most
runs, so this is the last lever to pull and only pays off when the full matrix is genuinely the
bottleneck.

**Before building Phase 4, run the `agent-browser` spike.** `vercel-labs/agent-browser` is a
**Bash-driven CLI** (not an MCP server), so — unlike Playwright MCP — it *can* be driven by depth-1
subagents. That would turn parallel viewport QA into an ordinary depth-0 fan-out (a new
`fls:qa-viewport-agent` with `Bash` + a single `Bash(agent-browser *)` allow-list entry) instead of
the external multi-session orchestrator above, and it's markedly cheaper per flow (~7k tokens vs
Playwright's ~27–50k after Phase-1 tuning). Catches, in fairness: true session isolation needs
`--profile` (separate Chrome processes, so it's *not* actually lighter than three Playwright
instances), it's **pre-1.0 with weekly breaking-change risk**, and adopting it forfeits the official
Playwright codegen/Healer ecosystem. So this is a **go/no-go spike, not a commitment**: after Phases
1–3, run the 4-step spike in `research_agent_browser_alternative.md` (install → drive one FLS flow &
measure tokens → prove 2-`profile` parallel isolation → decide). Pass → build Phase 4 as
agent-browser fan-out; fail → fall back to the Playwright external-orchestrator approach.

## Out of scope / explicitly rejected

- Weakening `security-guard.sh` to permit `rm -rf` — wrap deletions in committed scripts instead.
- Tiering the browser-driving steps below the session model — visual judgement is the point.
- Replacing Playwright MCP wholesale (Chrome DevTools MCP, browser-use) — MCP is the right tool for
  the exploratory role; we tune it and add a deterministic fast-path, we don't replace it. The one
  exception under *active evaluation* is `vercel-labs/agent-browser`, gated behind the Phase 4 spike
  above — not adopted now, but not dismissed either.
- A reusable Playwright test-runner fast-path for re-verification is an attractive *future* idea
  (near-zero token re-checks) but is not part of this work; the pytest suite already covers the
  cheap deterministic regression layer for the bug-fix loop.

## Backing research

Full findings, measurements, and citations live alongside this file:

- `research_playwright_mcp_efficiency.md` — token sinks, the exact MCP config knobs, MCP vs the
  test runner.
- `research_parallel_qa_and_model_tiering.md` — what's actually parallelizable, diff-scoping gates,
  which steps can move to Haiku/Sonnet.
- `research_qa_bugfix_tdd_agent.md` — the `qa-bugfixer` agent shape, triage rubric, re-verify loop,
  loop guard.
- `research_resilient_tool_batching.md` — cascade-cancel semantics, `cd`/`rm -rf`/hook trips, the
  exact allow-list entries and batching rules to add.
- `research_agent_browser_alternative.md` — `vercel-labs/agent-browser` evaluated against our
  constraints: the Bash-driven depth-1 parallelism unlock, token comparison, the `--session` vs
  `--profile` isolation catch, pre-1.0 risk, and the go/no-go spike plan gating Phase 4.
