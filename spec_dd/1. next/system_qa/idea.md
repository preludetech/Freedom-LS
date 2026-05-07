# System QA — exploratory cross-spec QA pass

A new slash command (working name `/system_qa`) that runs a broad, exploratory QA pass across the running app — *not* against a single spec. It's intended to catch regressions introduced by recent merges or merge-conflict resolution that no per-spec `/do_qa` run was scoped to find.

It is a sibling of `/do_qa` and reuses the same operational mechanics (Playwright MCP, port handling, `#debug-branch-badge` collision guard, viewport sweeps, screenshot compression, todo-list update, qa-data-helper for data). The difference is that the test plan is **discovered** at run time rather than read from a fixed `3. frontend_qa.md`.

## Why

Per-spec QA runs are scoped to one spec's deltas. They never re-test surfaces touched by *other* recent specs, and they miss multi-spec interaction bugs (e.g. spec A touching `_base.html` + spec B touching `partials/messages.html`). The `tangential observations` sections of recent `qa_report.md` files already show this happening — real cross-spec wobbles are being noted but never re-tested. `/system_qa` plugs that gap.

## When to run

Manually invoked. Typical moments:
- After a stack of merges has landed on `main`
- Before a release / cohort of work goes out
- When a few features have been merged in quick succession and nothing has explicitly checked their interactions

## Run shape (high level)

Three phases, all driven by a slash command that orchestrates sub-agents:

1. **Plan** — a planner pass scans recently completed specs, identifies hot-spots and tangentials, and emits a list of frozen *charters* (Session-Based Test Management style). Each charter declares mission, areas in scope, data prerequisites, oracle source, viewport(s), and a budget. Charters are immutable for the rest of the run so the testing agent cannot scope-creep.

2. **Execute** — for each charter, a testing agent acts like a human QA expert: drives the live site through Playwright MCP, takes screenshots, calls `qa-data-helper` whenever data is missing, and stops when its session budget runs out or it hits diminishing returns. Each session ends with a short PROOF debrief (Past / Results / Obstacles / Outlook / Feelings).

3. **Report** — a single `qa_report.md` is written to a timestamped run directory, with screenshots embedded via `![](path)` so they render and are clickable. The report is the only durable deliverable; the team triages it and turns confirmed bugs into follow-up specs.

## Inputs the planner uses

- `spec_dd/3. done/` — by default the **last 10 completed specs** (sorted by directory date prefix). Overridable via slash-command argument (e.g. `/system_qa --since 2026-05-01` or `/system_qa --last 20`).
- Each candidate spec's `1. spec.md`, `3. frontend_qa.md`, and (especially) `qa_report.md` "tangential observations" — already-noted-but-never-fixed cross-spec issues become first-class candidate regressions.
- A static FLS hot-spot map (shared chrome / `_base.html` / sidebar / `partials/messages.html` / educator panel framework / auth + middleware / multi-tenant / webhooks). Charters that hit hot-spots are weighted up.
- The list of `freedom_ls/qa_helpers/management/commands/` to know which scenarios are pre-baked.

## Run budget

- Total wall-clock budget is **user-supplied** with a sensible default (~45 min). Bigger arg → more sessions and/or longer sessions. Overrides per-charter caps proportionally.
- Stop conditions per session: budget exhausted, charter landmarks all visited, or 3 sterile steps in a row (diminishing returns).
- Stop conditions per run: total budget exhausted, all charters complete, or repeated cross-charter failures (e.g. server keeps crashing).

## Viewport handling

The planner decides viewports per charter:
- Charters touching shared chrome (sidebar, messages, header, base layout, registration completion) → desktop + mobile + tablet sweep.
- Other charters → desktop only by default.
- Admin-touching charters → desktop only (matches `/do_qa` convention).

This keeps the budget under control while still catching mobile-only regressions on the surfaces where they actually hide.

## Findings discipline (anti-slop)

To stop the agent generating "AI slop" findings:
- A **Bug** must have a screenshot AND an oracle citation (spec line, prior qa_report tangential, FEW HICCUPPS heuristic). Otherwise it's filed as a *Suspected bug* or *Observation*.
- Five report categories: `Bugs (confirmed)` / `Suspected bugs` / `Inconsistencies` / `Questions for the dev` / `Not tested`. Low-confidence stuff has somewhere honest to live without polluting the action list.
- Severity: `blocker / major / minor / cosmetic` only — no "high"/"critical" inflation. Each finding carries a one-line "why this severity" justification. Priority is left for human triage.
- "Not tested" section is mandatory and non-empty — forces coverage honesty so devs don't assume the agent looked everywhere.

## Hard rules carried over from `/do_qa`

- Site under test is **DemoDev**.
- Test data is created by **`qa-data-helper`**, never by the testing agent itself.
- `#debug-branch-badge` is checked before every session to guard against worktree port collisions.
- Screenshots are compressed via `compress_screenshots.py` before the report is written.
- Stop and report if Playwright MCP is unavailable.
- Findings describe **user-visible behaviour**, not CSS classes.
- Any TODO / @claude comment in the codebase remains untouched.

## Output

```
spec_dd/1. next/system_qa/runs/<YYYY-MM-DD_HH-MM>/
  qa_report.md
  screenshots/
    desktop_BUG-01_<short>.png
    mobile_BUG-02_<short>.png
    ...
  charters.md           # the frozen plan, kept for traceability
```

`qa_report.md` opens with run metadata (branch, base URL, site, charter index, total budget vs spent), a severity-count summary table, the top 3 findings with deep-links, then per-category sections. Findings carry stable IDs (`BUG-01`, `SUS-01`, `Q-01`) used in headings, screenshot filenames, and anchor targets so devs can deep-link from chat.

## Out of scope (for now)

- Auto-converting findings into Playwright test code (that's a separate "explore → replay" feature).
- Running on a schedule (manual trigger only).
- Posting findings to GitHub issues / external trackers.
- Backend-only checks (webhook payload contents, DB integrity) — `/system_qa` is a UI exploration, though it can flag webhook misfires it observes through the UI.

## Open questions for the spec phase

- Where should runs live long-term? `spec_dd/1. next/system_qa/runs/` makes sense for the idea phase, but `system_qa` isn't really a normal SDD spec and the directory will fill up. Consider promoting to `system_qa_reports/<run>/` at repo root once the command exists.
- Should the planner read git diffs (`git log --name-only` between merge points) directly, or rely entirely on the spec directories? Diffs are richer; spec dirs are cheaper and avoid noise.
- Should there be a "previous-run carry-over" — i.e. the planner reads the last run's `Suspected bugs` and re-checks them this run?
- How does the command behave when no UI-touching specs landed in the window (e.g. only test/tooling specs)? Skip with a friendly message, or fall back to a "garbage-collector tour" of the static hot-spot map?

## Research

Research outputs live alongside this idea:
- `research_exploratory_qa.md` — SBTM, charters, RCRCRC/SFDIPOT/FEW HICCUPPS/Whittaker tours, LLM-driven testing tools, stop conditions, failure modes.
- `research_repo_surface.md` — FLS surface inventory, recent spec patterns, existing `qa_report.md` conventions, plugin scripts, `qa_helpers` app, cross-spec hot-spots.
- `research_report_format.md` — bug report fields, severity taxonomies, finding categories, screenshot rules, anti-patterns, recommended report skeleton.
