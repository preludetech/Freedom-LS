# Research: Exploratory & Autonomous QA for `/system_qa`

This document gathers practitioner-level research to inform the design of a new `/system_qa`
command for FLS. The command needs to behave like a human exploratory tester: discover what to
test by inspecting recently merged specs, drive the app via Playwright MCP, lean on an existing
`qa-data-helper` sub-agent for seed data, and emit a markdown report with embedded screenshots.
The recommendations below are pragmatic — they translate established QA practice into mechanics
that a single LLM agent run can actually execute and stop on time.

---

## 1. Session-Based Test Management (SBTM)

### Key findings

- SBTM was created at HP by Jonathan and James Bach as an "activity-based" alternative to
  artifact-heavy test management. It pairs **time-boxed sessions** with **charters** and a
  structured **debrief** so that exploratory testing remains accountable and measurable.
  ([Satisfice](https://www.satisfice.com/download/session-based-test-management),
  [Wikipedia](https://en.wikipedia.org/wiki/Session-based_testing))
- A **charter** is a mission statement, not a script. Common shape:
  *"Explore <area> with <resources> to discover <information>."* It must be specific enough to
  focus the tester but loose enough to let new ideas surface mid-session.
  ([Ministry of Testing](https://www.ministryoftesting.com/software-testing-glossary/session-based-test-management-sbtm))
- **Session length**: 60–90 min is the sweet spot. ≤30 min lacks depth; >2 hours degrades
  observation. Bach's original work uses S/M/L sizing (~45/90/120 min).
  ([tmap.net](https://www.tmap.net/wiki/exploratory-testing-et/),
  [Wikipedia](https://en.wikipedia.org/wiki/Session-based_testing))
- **TBS time breakdown** (tracked per session):
  Test design & execution / Bug investigation & reporting / Session setup. Reported as
  percentages, plus "% on charter vs. opportunistic exploration."
  ([Wikipedia](https://en.wikipedia.org/wiki/Session-based_testing))
- **Debrief mnemonic — PROOF**:
  Past (what happened) / Results (what was achieved) / Obstacles / Outlook (what's left) /
  Feelings (gut-feel signal).
  ([Testsigma](https://testsigma.com/blog/session-based-testing/),
  [Wikipedia](https://en.wikipedia.org/wiki/Session-based_testing))

### What a charter looks like for an LLM agent

Treat the charter as a **prompt fragment** with hard constraints. Useful fields:

```yaml
charter_id: cohort_progress_2026-05-06_01
mission: |
  Explore the educator cohort progress dashboard to discover regressions
  in score aggregation and student visibility after the recent
  scoring-strategy and site-aware filtering changes.
areas_in_scope:
  - educator_interface.cohort_detail
  - student_progress.aggregation
data_prereqs:
  - DemoDev site, 1 cohort with >=5 students, mixed completion states
budget:
  max_minutes: 15
  max_steps: 60
oracles:
  - spec: spec_dd/0. done/<recent>/spec.md
  - heuristic: FEW HICCUPPS
stop_when:
  - budget exhausted
  - 3 confirmed bugs filed
  - same screen revisited 3+ times without new finding
```

### Recommendations for `/system_qa`

- One run = many small sessions, each with its own charter. Sessions are
  independent — if one stalls, others still produce value.
- Always emit a **PROOF debrief** per session into the final report.
- Track **TBS percentages** by tagging each agent step (`design`, `bug_invest`, `setup`).
  This makes it obvious in the report whether the run was actually testing or thrashing.
- Charters should be generated up-front by a "planner" pass that scans recent specs, then
  frozen for the rest of the run so the agent cannot scope-creep mid-session.

---

## 2. Exploratory testing heuristics

### Key findings

- **Hendrickson / Lyndsay / Emery — Test Heuristics Cheat Sheet** (the canonical 2-page
  reference) collects boundary attacks (Numbers, Strings, Time/Date, Paths/Files), web heuristics
  (Navigation, Input, A11y), API mnemonics (BINMEN, POISED, VADER), and high-level
  meta-heuristics. Every LLM-driven UI agent should have access to this list as a prompt
  resource.
  ([Cheat Sheet article — Ministry of Testing](https://www.ministryoftesting.com/articles/test-heuristics-cheat-sheet),
  [O'Reilly *Explore It!* Appendix 2](https://www.oreilly.com/library/view/explore-it/9781941222584/f_0098.html))
- **RCRCRC** (Hendrickson) for regression scoping: **R**ecent, **C**ore, **R**isky,
  **C**onfiguration-sensitive, **R**epaired, **C**hronic. Maps directly to "what to retest after
  recent merges" — exactly FLS's situation.
  ([Tentamen](https://blog.tentamen.eu/testing-heuristics-cheat-sheet/))
- **FEW HICCUPPS** (Bolton, extending Bach) — oracles to spot a bug:
  **F**amiliarity, **E**xplainability, **W**orld /
  **H**istory, **I**mage, **C**laims, **C**omparable products, **U**ser expectations,
  **P**roduct (internal consistency), **P**urpose, **S**tatutes/standards.
  Useful when no spec or formal oracle is available.
  ([Ministry of Testing](https://www.ministryoftesting.com/articles/test-heuristics-cheat-sheet))
- **Bach's HTSM — SFDIPOT** (product-element coverage):
  **S**tructure, **F**unction, **D**ata, **I**nterfaces, **P**latform, **O**perations, **T**ime.
  A coverage outline rather than an attack list — good for ensuring the run touches more than
  just "happy path features."
  ([Satisfice HTSM](https://www.satisfice.com/download/heuristic-test-strategy-model),
  [Sharon O'Boyle — using SFDIPOT](https://www.sharonob.com/blog/sfdipot))
- **Whittaker's Tours** ("Exploratory Software Testing") — narrative scoping patterns:
  - **Money tour** — flagship features customers paid for.
  - **Landmark tour** — pre-pick key screens, visit in varying order.
  - **Back-alley tour** — least-used features.
  - **Garbage-collector tour** — methodical sweep, revisit historically buggy areas.
  - **Intellectual tour** — ask hard questions, push limits, attack error handling.
  - **Feature tour / FedEx tour / antisocial tour / obsessive-compulsive tour** — many more
    available.
  ([softwaretestinghelp.com](https://www.softwaretestinghelp.com/exploratory-testing-tours/),
  [Xray blog](https://www.getxray.app/blog/test-tours-exploratory-testing-strategy-qa-teams),
  [Trailhead Tech](https://trailheadtechnology.com/tour-testing-structured-approach-to-exploratory-testing/))
- **Whittaker's "How to Break Software" attacks** — input-domain attacks (force errors, default
  values, repeated input, interacting inputs), output-domain attacks (force invalid outputs,
  refresh), system-interface attacks (file/permission/network faults).
  ([UAA course PDF](http://www.math.uaa.alaska.edu/~afkjm/cs470/handouts/breaking.pdf))

### Which heuristics translate well to an LLM-driven UI agent

| Heuristic | LLM fit | Why |
| --- | --- | --- |
| **RCRCRC** | Excellent | Maps cleanly to git history / recent specs. Use it as the **scoping** layer. |
| **SFDIPOT** | Good | Useful as a **coverage checklist** in the planner. Agent ensures each session touches at least one of S/F/D/I/P/O/T angles. |
| **FEW HICCUPPS** | Excellent | Pure oracle reasoning. Give the LLM this list and ask "given the screenshot + spec, does anything violate any of these?" |
| **Whittaker tours** | Excellent | Tours are *named prompts*. "Run a money tour over the cohort progress feature" produces a rich, focused exploration. |
| **Hendrickson cheat sheet (data attacks)** | Excellent for forms | Easy to drop into prompts when seeing an input field. |
| **Whittaker attacks** | Good but needs guardrails | Some attacks (network faults, file-permission tampering) require infra access. Stick to UI-input attacks. |

### Recommendations for `/system_qa`

- Bake a **canned heuristic library** into the command: include the cheat sheet, FEW HICCUPPS,
  SFDIPOT, RCRCRC, and a curated list of ~6 Whittaker tours as part of the system prompt or
  a referenced markdown file.
- Each charter must declare **which tour and which oracles** it will use. This both focuses the
  agent and makes the report richer.
- For form-heavy screens, automatically inject the data-type attack list (boundary numbers,
  empty/whitespace strings, max-length, bidi/Unicode, dates around DST, etc.).

---

## 3. AI/LLM-driven UI testing tools — how they scope

### Key findings

- **Mabl (2026)** — "Agentic Tester" autonomously explores the app to discover failure points;
  separate "Test Creation Agent" turns NL goals into stable scripted tests. Scoping is driven by
  user-provided application URL + an "exploration goal" prompt; the agent reports back
  candidate flows and findings rather than running until exhaustion.
  ([Mabl breakthrough announcement](https://www.mabl.com/breakthrough-agentic-ai-capabilities-redefining-software-quality),
  [QA Blogs — Mabl 2025](https://qablogs.com/blogs/mabl-2025-testing-revolution-ai-agents-qa-efficiency))
- **Functionize** — "autonomous testing": NL-to-script, self-healing, root-cause analysis. Their
  scoping pitch is *"reduce manual scripting, adapt to UI changes"* rather than truly open-ended
  exploration.
  ([Functionize](https://www.functionize.com/automated-testing/what-is-autonomous-testing))
- **Reflect (SmartBear)** — AI element selection + NL test creation; primarily authoring help,
  not unattended exploration.
  ([Reflect AI docs](https://support.smartbear.com/reflect/docs/en/recording/test-with-ai))
- **Skyvern** — open-source browser agent built on Playwright + LLM + computer vision. Uses an
  **explore → replay** pattern: the LLM figures out a flow once (high cost), then replays it
  deterministically (low cost). This is the closest analogue to what `/system_qa` is doing.
  ([Skyvern repo](https://github.com/Skyvern-AI/skyvern),
  [Skyvern blog: AI Web Agents 2025](https://www.skyvern.com/blog/ai-web-agents-complete-guide-to-intelligent-browser-automation-november-2025/))
- **Browserbase** — managed browser infra + agent orchestration. Notable for proving that **the
  hard problem is infrastructure & determinism**, not LLM reasoning per se.
  ([Browserbase docs](https://www.browserbase.com/))
- **Testim** — record-and-playback augmented with ML for locator stability; not really an
  autonomous exploration tool.
  ([Mabl vs Testim comparison](https://aitestingguide.com/mabl-vs-testim/))

### Scoping strategies these tools use to avoid running forever

1. **User-supplied scope + budget** — every commercial tool requires the operator to declare
   "explore this URL/this user journey" plus a max time or step count.
2. **Goal-as-prompt** — agents are given a positive goal ("verify checkout works") rather than
   "find anything wrong," which naturally bounds the search.
3. **Explore → Replay** — separate the expensive discovery phase from cheap re-execution. Once
   a flow is found, save it as a deterministic script.
4. **Element-graph caching** — once an agent has mapped a page's interactive elements, it
   doesn't re-LLM the layout on revisits.
5. **Coverage feedback** — Mabl's agentic tester reports flows it covered and asks the user to
   confirm priorities before deeper runs.

### Recommendations for `/system_qa`

- Don't try to be Mabl. Lean into the **explore-and-report** mode: each run is a fresh
  exploratory pass, the artefact is the markdown report, persistence between runs is via
  follow-up specs (not a saved test database).
- Adopt **explore-then-summarise** instead of explore-then-replay: the report itself is the
  "replay" — reviewers decide what to convert into proper Playwright tests.
- Borrow **goal-as-prompt** rigorously: every charter must have a positive "verify X works"
  framing alongside the negative "look for bugs" framing. This stops the agent from drifting
  into nonsense.

---

## 4. Risk-based test selection from change history

### Key findings

- **Test Impact Analysis (TIA)** uses VCS hooks + dependency graphs to map changed files to the
  tests that exercise them. Mature pipelines (Microsoft, Google, Facebook) cite 30–85%
  regression-time reduction with TIA.
  ([Parasoft — TIA](https://www.parasoft.com/blog/test-impact-analysis/),
  [Augment Code](https://www.augmentcode.com/learn/regression-testing-defined-purpose-types-and-best-practices))
- **Risk-based testing** ranks features by likelihood × impact and tests highest-risk first.
  Inputs: change frequency, defect history, business criticality, complexity.
  ([TestCollab](https://testcollab.com/blog/risk-based-testing-guide),
  [testomat.io](https://testomat.io/blog/risk-based-testing/))
- **RCRCRC as a change-history scoping heuristic** — explicitly designed for "what to retest":
  Recent changes, Core flows, Risky areas, Configuration-sensitive bits, Repaired (recently
  fixed → regression-prone), Chronic (perennially buggy).
- **Signals that matter most** in practice:
  1. Files changed in the last N commits (proxy for "Recent").
  2. Files touched by merge-conflict resolution (high regression risk — exactly the FLS
     concern).
  3. Areas with TODO/`@claude` comments (known-incomplete).
  4. Specs marked done in `spec_dd/0. done/` since the last QA pass.
  5. App areas with recent migrations.
  ([Springer — Change Impact Analysis](https://link.springer.com/chapter/10.1007/978-3-642-19423-8_17),
  [Testriq — Regression Impact Analysis](https://www.testriq.com/blog/post/regression-impact-analysis-optimizing-test-coverage))

### Recommendations for `/system_qa`

The planner phase should produce a **risk-ranked area list** by combining several cheap signals:

1. **`spec_dd/0. done/` specs newer than a watermark** (e.g. last `/system_qa` run, or N days).
   Each completed spec maps to an "area" via the spec's frontmatter / mentioned apps.
2. **`git log --since` on key dirs** (`freedom_ls/<app>/`, `templates/`, `static/`) — count
   commits per app. High commit count → high "Recent" weight.
3. **Merge commit detection** — `git log --merges --since` and `git diff` of merge bases. Files
   that appeared in a conflict resolution get extra weight.
4. **Migration files added recently** — strong signal for data-shape changes.
5. **TODO scan** in changed files — bumps "Risky" weight.

Combine into a simple score per app/feature; allocate session budget proportionally.

Concretely: emit `qa_plan.json` with `[{area, score, rationale, suggested_charter, suggested_tour}]`,
and let the user inspect/edit before the agent burns tokens executing it.

---

## 5. Stopping criteria & budget control

### Key findings

- **Time-box is the primary stopping rule** in human SBTM (60–90 min). For an LLM, time is a
  weak signal — token cost and step count matter more.
  ([tmap.net](https://www.tmap.net/wiki/exploratory-testing-et/))
- **Loop guardrails** are mandatory for autonomous agents. The harness — not the agent — must
  enforce termination: max iterations, repetitive-output detection, semantic-completion checks,
  circuit breakers on cost.
  ([dev.to — Stop your AI agents from looping](https://dev.to/pavelgj/stop-your-ai-agents-from-crashing-looping-and-burning-through-tokens-2g70),
  [Fixbrokenaiapps — Why agents loop](https://www.fixbrokenaiapps.com/blog/ai-agents-infinite-loops))
- **Token budgets** in agentic workflows can vary 10× run-to-run on the same task. Per-session
  caps + global run cap are both needed.
  ([truefoundry — Agentic token explosion](https://www.truefoundry.com/blog/llm-cost-attribution-agentic-cicd),
  [aisecuritygateway — Token budget strategies](https://aisecuritygateway.ai/blog/llm-token-budget-strategies-for-agents))
- **Bug-find-rate** as a stopping signal: if N consecutive sessions/steps yield no new findings,
  the agent is exploring sterile ground. Mature human practitioners reframe rather than press on.
- **Ralph Loop pattern** — when iteration limit is reached, instead of hard-killing, swap in a
  "summarizer" agent to write up partial findings cleanly.
  ([Ralph Loop blog](https://ice-ice-bear.github.io/posts/2026-03-06-ralph-loop-ai-automation/))

### Practical stopping rules for `/system_qa`

Apply **all** simultaneously, whichever fires first:

1. **Hard caps**:
   - Total wall-clock cap (e.g. 30 min).
   - Total step cap across all sessions (e.g. 200 tool calls).
   - Per-session step cap (e.g. 40 tool calls).
2. **Coverage targets**:
   - Stop a session when its charter's named landmarks have all been visited at least once
     **and** the SFDIPOT angle has been touched.
3. **Diminishing returns**:
   - Stop a session if 3 consecutive steps produce no new screen, no new bug, and no new data.
   - Skip remaining sessions if 2 consecutive sessions both yielded zero findings.
4. **Repetition detection**:
   - Stop a session if the same URL is visited >3 times without finding.
   - Stop a session if the same DOM element has been clicked twice with no state change.
5. **Soft escalation**:
   - On any cap hit, do **not** terminate silently — invoke a "summarise" sub-step that flushes
     in-flight observations into the report.

---

## 6. Common failure modes of autonomous QA agents

### Key findings

Documented agentic failure modes from recent research and field reports:

- **Hallucinated bugs / false positives** — agent declares a defect where none exists, often by
  over-interpreting normal behaviour (e.g. "the page didn't update" when it did, but the agent
  missed the diff).
  ([Galileo](https://galileo.ai/blog/llm-testing-strategies),
  [Evidently AI](https://www.evidentlyai.com/blog/llm-hallucination-examples))
- **Confident wrong answers / overexcitement** — agent declares success after partial work.
  ([arxiv 2512.07497](https://arxiv.org/html/2512.07497v2))
- **Context drift on long horizons** — multi-step reasoning loses sight of the original
  charter, agent ends up clicking around aimlessly.
- **Bias toward training-data defaults** — agent expects WordPress-style URL or Stripe-style
  flow, raises bugs because the FLS app doesn't match its prior.
- **Wrong adaptation to missing values** — agent invents data ("substituted similar company")
  when the right answer was "fail and report."
- **Failure cascades** — one early step fails, every later step also "fails" for unrelated
  reasons; report is full of duplicate/spurious bugs.
- **Flakiness mistaken for bugs** — slow page load, animations, async HTMX swaps treated as
  defects.
- **Whole-subsystem blind spots** — agent never visits the admin or the API, even though
  those are in scope, because nothing in the charter pointed there.
- **Style-as-bug noise** — agent flags pixel alignment, font-size differences, or "ugly"
  layouts that aren't actually bugs.
- **Resource exhaustion / loops** — agent burns tokens in tight loops over the same screen.
  ([dev.to loops](https://dev.to/pavelgj/stop-your-ai-agents-from-crashing-looping-and-burning-through-tokens-2g70))

### Mitigations that actually work

| Failure mode | Mitigation |
| --- | --- |
| Hallucinated bugs | Each finding must cite an oracle (FEW HICCUPPS letter / spec line / contradicting screenshot). No oracle → not a bug, file as "observation." |
| Confident wrong answers | Require a screenshot for every claim. Reviewer can spot-check. |
| Context drift | Per-session charter is reloaded as the system message of every step; charter is short and bounded. |
| Training-data bias | System prompt explicitly states FLS conventions (multi-tenant, HTMX, kebab-case URLs). Add a "do not flag these as bugs" list. |
| Invented data | `qa-data-helper` is the **only** legitimate path to seed data. Agent forbidden from typing arbitrary IDs/UUIDs into URL bars. |
| Cascading failures | Each session is independent; failure-cascade detection (≥3 sequential errors) → abandon the session, mark "blocked," continue. |
| Flakiness as bugs | Mandatory "retry once after 1s" before raising any "missing element / not loaded" bug. UI-state-dependent findings need 2 confirmations. |
| Subsystem blind spots | Planner enforces SFDIPOT coverage across charters — at least one charter targets each in-scope app. |
| Style-as-bug noise | Memory rule already in project: "no style assertions." Bake into agent prompt: only flag styling if it breaks readability/accessibility. |
| Loops | Step caps + repetition detection + Ralph-loop-style "summarise on cap hit." |

### Recommendations for `/system_qa`

- The **bug-filing rule** is the single most important guardrail:
  *"A finding is only a bug if (a) it has a screenshot, AND (b) it cites a specific oracle —
  spec line, FEW HICCUPPS letter, or contradiction with another observed behaviour."*
  Everything else is filed as an "Observation" in a separate report section.
- Maintain an **explicit do-not-flag list** in the prompt:
  - cosmetic alignment, font choice, colour preferences (per `feedback_no_style_assertions`)
  - features marked TODO / `@claude` (per project rule: don't delete TODOs, don't flag them)
  - debug toolbar, admin-only widgets unless charter targets them
- Force a **brief self-review pass** before report write: the agent re-reads its findings and
  marks any with weak evidence as "needs human review" rather than "bug."

---

## Recommended approach for FLS

A concrete shape for the `/system_qa` command. This is intentionally narrow — broaden later
once the basic loop proves itself.

### Phase 1 — Plan (cheap, no browser)

1. **Compute change footprint**:
   - List specs in `spec_dd/0. done/` newer than a watermark
     (`.claude/system_qa_last_run` or last 7 days).
   - `git log --since=<watermark> --name-only` per app under `freedom_ls/`.
   - Detect merge commits in that range; flag files that appeared in conflict resolution.
   - List recent migrations.
2. **Score & rank areas** using RCRCRC weights:
   - Recent (commit count) ×3
   - Core (always-on apps: accounts, student_interface, educator_interface) ×2
   - Risky (had merge conflicts, has TODO/`@claude`) ×3
   - Configuration-sensitive (sites/multi-tenant changes, settings.py touched) ×2
   - Repaired (files mentioned in recent bugfix commits) ×2
   - Chronic (frequent QA findings — pull from past `/system_qa` reports if any) ×1
3. **Generate charters** — one per top-N area. Each charter:
   ```yaml
   id: <area>_<date>_<n>
   mission: <one sentence>
   tour: money | landmark | back-alley | garbage-collector | intellectual
   sfdipot_angle: F | D | I | P | O | T
   data_prereqs: [...]   # passed to qa-data-helper
   oracles: [<spec paths>, FEW HICCUPPS]
   budget: { max_steps: 40, max_minutes: 8 }
   ```
4. **Emit `qa_plan.md`** for human review (optional gate). The user can run with
   `--no-confirm` to skip.

### Phase 2 — Execute sessions (expensive, browser-driven)

For each charter, in order of score:

1. Call **`qa-data-helper`** with `data_prereqs` to seed the DemoDev site.
2. Run an **exploratory loop**:
   - Step = (LLM call, tool call, observation).
   - System prompt loads: charter + heuristic library + FLS guardrails (no-style, no-TODO,
     do-not-flag list).
   - Each step the agent must answer: "what landmark/SFDIPOT angle am I touching now? what
     oracle am I checking?"
   - Take a screenshot at every state-changing action; save with stable filename.
3. **Apply guardrails** every step:
   - step counter, repetition detector, error-cascade detector, no-progress detector.
4. **Filing rules**: Bug requires screenshot + oracle citation. Otherwise → Observation.
5. **End of session**: write a PROOF debrief block.

### Phase 3 — Report

Single markdown file `system_qa_report_<UTC-timestamp>.md` with:

```markdown
# System QA Report — <date>

## Run summary
- Watermark: <prev-run-or-date>
- Specs reviewed: <count> (list)
- Areas covered: <count> | not covered: <count>
- Sessions: <count>  Bugs: <count>  Observations: <count>
- Total budget used: <wall>min, <steps> steps, ~<tokens> tokens
- TBS breakdown: design <%> / bug-invest <%> / setup <%>

## Plan
(compact view of the qa_plan with per-area scores & rationale)

## Sessions

### Session 1 — <charter id>
**Charter**: <mission>
**Tour**: money  **SFDIPOT angle**: F
**Budget used**: 6m / 32 steps

#### Findings
- **BUG** Score aggregation off-by-one on cohort detail
  - Oracle: contradicts `spec_dd/0. done/scoring/spec.md` line 42
  - Steps to reproduce: 1. ... 2. ...
  - ![cohort score off-by-one](screenshots/s1_b1_cohort.png)
- **OBS** Slow render on /educator/cohorts/ (~3s) — flag for perf, not a bug.

#### PROOF debrief
- **P**ast: visited dashboard, opened 3 cohorts, exported CSV.
- **R**esults: 1 bug, 1 observation.
- **O**bstacles: needed to seed a 5-student cohort; took 2 retries.
- **O**utlook: did not test bulk-edit; recommend follow-up charter.
- **F**eelings: confident in finding; aggregation logic feels brittle.

### Session 2 — ...

## Coverage map
| App | Touched? | SFDIPOT angles hit |
| --- | --- | --- |
| accounts | yes | F, D |
| ... | | |

## Areas NOT covered
- <area>: <reason>

## Recommended follow-ups
- New charters / specs to schedule next time.
```

### Key design decisions baked in

| Decision | Rationale |
| --- | --- |
| **Charter is mandatory and immutable per session** | Prevents context drift, keeps reports auditable. |
| **Heuristic library is a first-class prompt resource** | RCRCRC + FEW HICCUPPS + SFDIPOT + tours give the agent vocabulary. |
| **Bug = screenshot + oracle citation, else Observation** | Single biggest hallucination/false-positive control. |
| **`qa-data-helper` is the only seed path** | Stops the agent from inventing IDs and writing fictitious flows. |
| **Three independent stop conditions per session** | Caps + diminishing-returns + repetition detector. |
| **Plan phase is human-reviewable** | Catches bad scoping before tokens are spent. |
| **Report has explicit "not covered" section** | Forces honesty; readers know what was skipped. |
| **No persistent test database between runs** | Avoids drift, keeps each run reproducible-ish. Saved tests live in proper Playwright suites, written by humans from the report. |

### What we are deliberately NOT doing (yet)

- No self-healing locators.
- No replay / explore-replay split (Skyvern-style). Each run is a fresh exploration.
- No cross-run memory of "chronic" areas beyond "look at past reports."
- No automatic bug-filing into an external tracker — the markdown report is the artefact.
- No attacks that require infra access (network faults, file-permission attacks). UI-input
  attacks only.

These are sensible expansions for v2 once the v1 loop is reliable.

---

## Source list

- [Satisfice — Session-Based Test Management](https://www.satisfice.com/download/session-based-test-management)
- [Satisfice — Heuristic Test Strategy Model](https://www.satisfice.com/download/heuristic-test-strategy-model)
- [Wikipedia — Session-based testing](https://en.wikipedia.org/wiki/Session-based_testing)
- [Ministry of Testing — SBTM glossary](https://www.ministryoftesting.com/software-testing-glossary/session-based-test-management-sbtm)
- [Ministry of Testing — Test Heuristics Cheat Sheet](https://www.ministryoftesting.com/articles/test-heuristics-cheat-sheet)
- [O'Reilly — *Explore It!* Appendix 2](https://www.oreilly.com/library/view/explore-it/9781941222584/f_0098.html)
- [Tentamen — Testing Heuristics Cheat Sheet](https://blog.tentamen.eu/testing-heuristics-cheat-sheet/)
- [Sharon O'Boyle — Using SFDIPOT](https://www.sharonob.com/blog/sfdipot)
- [Testsigma — Session Based Testing](https://testsigma.com/blog/session-based-testing/)
- [tmap.net — Exploratory Testing](https://www.tmap.net/wiki/exploratory-testing-et/)
- [Whittaker — How to Break Software (course handout)](http://www.math.uaa.alaska.edu/~afkjm/cs470/handouts/breaking.pdf)
- [softwaretestinghelp — Exploratory Testing Tours](https://www.softwaretestinghelp.com/exploratory-testing-tours/)
- [Xray — Test tours strategy](https://www.getxray.app/blog/test-tours-exploratory-testing-strategy-qa-teams)
- [Trailhead Tech — Tour Testing](https://trailheadtechnology.com/tour-testing-structured-approach-to-exploratory-testing/)
- [Mabl — Agentic AI announcement](https://www.mabl.com/breakthrough-agentic-ai-capabilities-redefining-software-quality)
- [QA Blogs — Mabl 2025 testing revolution](https://qablogs.com/blogs/mabl-2025-testing-revolution-ai-agents-qa-efficiency)
- [Functionize — Autonomous Testing](https://www.functionize.com/automated-testing/what-is-autonomous-testing)
- [Skyvern — GitHub](https://github.com/Skyvern-AI/skyvern)
- [Skyvern — AI Web Agents Guide (Nov 2025)](https://www.skyvern.com/blog/ai-web-agents-complete-guide-to-intelligent-browser-automation-november-2025/)
- [Reflect — AI test docs](https://support.smartbear.com/reflect/docs/en/recording/test-with-ai)
- [TestCollab — Risk-Based Testing](https://testcollab.com/blog/risk-based-testing-guide)
- [testomat.io — Risk-Based Testing](https://testomat.io/blog/risk-based-testing/)
- [Testriq — Regression Impact Analysis](https://www.testriq.com/blog/post/regression-impact-analysis-optimizing-test-coverage)
- [Parasoft — Test Impact Analysis](https://www.parasoft.com/blog/test-impact-analysis/)
- [Springer — Change Impact Analysis for Regression Testing](https://link.springer.com/chapter/10.1007/978-3-642-19423-8_17)
- [dev.to — Stop your AI agents from looping](https://dev.to/pavelgj/stop-your-ai-agents-from-crashing-looping-and-burning-through-tokens-2g70)
- [Fixbrokenaiapps — Why AI agents loop](https://www.fixbrokenaiapps.com/blog/ai-agents-infinite-loops)
- [Ralph Loop pattern](https://ice-ice-bear.github.io/posts/2026-03-06-ralph-loop-ai-automation/)
- [aisecuritygateway — LLM token budget strategies](https://aisecuritygateway.ai/blog/llm-token-budget-strategies-for-agents)
- [truefoundry — Agentic token explosion](https://www.truefoundry.com/blog/llm-cost-attribution-agentic-cicd)
- [Galileo — LLM testing strategies](https://galileo.ai/blog/llm-testing-strategies)
- [arxiv 2512.07497 — How LLMs fail in agentic scenarios](https://arxiv.org/html/2512.07497v2)
- [Evidently AI — LLM hallucination examples](https://www.evidentlyai.com/blog/llm-hallucination-examples)
- [Cem Kaner — Oracle Problem](https://kaner.com/?p=190)
- [Association for Software Testing — The often-overlooked test oracle](https://associationforsoftwaretesting.org/2023/01/10/the-often-overlooked-test-oracle/)
