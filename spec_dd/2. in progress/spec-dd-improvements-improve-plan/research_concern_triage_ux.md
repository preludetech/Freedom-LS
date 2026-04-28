# Research: Triage and Presentation of Reviewer-Found Concerns

How should the next-version `plan` command surface concerns from three internal reviewer subagents (testing-practices, structure, security) without overwhelming the user?

## 1. Concern triage in agentic workflows

Production tools converge on a small number of axes: **severity**, **confidence**, and **whether the agent can act unilaterally**.

- **GitHub Copilot Code Review** tags each finding with severity (Critical / High / Medium / Low) and attaches *one-click* suggested fixes inline; only ~71% of reviews surface comments at all, the rest are silent — agents are explicitly told to stay quiet when they have nothing useful ([GitHub blog: 60M reviews](https://github.blog/ai-and-ml/github-copilot/60-million-copilot-code-reviews-and-counting/)).
- **Anthropic's own `/code-review` plugin** ([source](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)) splits fixes by *size*: small fixes (<6 lines) ship as committable suggestion blocks, larger ones become described findings — a practical "auto-applicable vs needs decision" heuristic.
- **Sourcegraph's Sherlock** "produces a concise summary of potential security concerns and prioritizes them by severity" ([Sourcegraph blog](https://sourcegraph.com/blog/lessons-from-building-sherlock-automating-security-code-reviews-with-sourcegraph)).
- **Spec Kit** doesn't classify by severity at all — instead it uses inline `[NEEDS CLARIFICATION: ...]` markers and "Pre-Implementation Gates" that fail loudly, forcing the user to either fix or document the deviation ([spec-kit/spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)).
- **obra/superpowers' code-reviewer agent** uses three buckets — Critical / Important / Suggestions — and explicitly demands actionable recommendations per finding ([source](https://github.com/obra/superpowers/blob/main/agents/code-reviewer.md)).

The consistent heuristic: **auto-fix when the change is small, mechanical, and confidence is high; flag for decision when the trade-off is real; FYI when style or preference.**

## 2. Severity / priority schemes for small teams

P0–P4 is overengineered for a 3-reviewer plan run. The well-known failure mode is *priority inflation*: teams "assign P0/P1/P2 but everything ends up P0 or P1 because there were no clear criteria" ([Tech Lead Curiosity](https://techleadcuriosity.substack.com/p/a-comprehensive-guide-to-priority-codes-in-technical-development-cee93c1414a3)). Bug tracker conventions confuse severity with priority ([BlueLabel](https://www.bluelabellabs.com/blog/dont-confuse-a-bugs-priority-with-its-severity/)).

A widely-referenced *small-team* convention is **BLOCKER / FAST-FOLLOW / NIT** — blocker stops merge, fast-follow ships in a separate PR, nit is take-it-or-leave-it (cited via the search above; see also Google's eng-practices on `Nit:` prefixes — [eng-practices](https://google.github.io/eng-practices/review/reviewer/standard.html)). For a *plan-review* phase (not code review) the analogous three buckets are:

- **Must address** — the plan can't proceed safely without a decision.
- **Should consider** — a real trade-off, but the plan would still work.
- **FYI / nit** — context, observation, optional.

Three buckets, named in human language. No numbers.

## 3. End-of-flow summaries

Anthropic's own code-review command ends with a flat terminal summary listing each issue with a brief description and, on success, a single line: *"No issues found."* ([source](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)). The community guidance for Claude Code subagent batch reviews matches: "findings should be synthesized into a single summary with priority-ranked issues, where each issue should include the file, line number, and recommended fix" ([PubNub best practices](https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/)).

The minimum-cognitive-load format that recurs:

1. **Header line**: counts per bucket ("3 must-address, 2 should-consider, 4 FYI").
2. **What I changed already** — short bulleted list of auto-applied fixes (the user can skim and trust).
3. **Decisions needed from you** — numbered, each with a one-sentence problem + a concrete proposed answer to react to.
4. **FYI** — collapsed/short.

Numbered tables are noisier than they look; numbered lists with bold lead-ins win in CLI rendering.

## 4. Question batching vs mid-flow interruption

LangGraph and Microsoft Agent Framework both expose **interrupt** primitives but explicitly warn against placing them after non-deterministic steps because "nodes re-run and produce different results" ([Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop), [TDS HITL](https://towardsdatascience.com/building-human-in-the-loop-agentic-workflows/)). The rule of thumb: *interrupt only as a gate before an irreversible action*; otherwise batch.

For our case, the three reviewers are **read-only, idempotent, parallelisable** — there is no irreversible action between them. Mid-flow interruption is unjustified. Batch.

The one exception: if a reviewer discovers something that would **invalidate the work the next reviewer is about to do** (e.g. structure reviewer says "this whole approach is wrong, replan"), then halt early and ask. This is "fail fast on blockers" — borrowed from Spec Kit's gate pattern.

## 5. The inline `> **Security concern:**` callout pattern

Inline callouts are the right primitive *when there is one reviewer and the user reads the plan top-to-bottom*. With three reviewers running together, three problems appear:

- **Density**: callouts can outnumber the plan content, making the doc unreadable.
- **Locality is noisy**: a security concern about auth and a structure concern about app boundaries don't belong on the same line.
- **Resolution tracking is manual**: the user has to grep for callouts to verify they've all been addressed.

But callouts have one irreplaceable virtue: **they sit next to the thing they're about**. Removing them entirely loses traceability.

Spec Kit resolves this by keeping inline `[NEEDS CLARIFICATION]` markers *only for ambiguity in the plan itself*, while gate failures live in a dedicated "Complexity Tracking" section. That split is the right model.

## 6. Recommendation

**Keep inline callouts only for "Must address" items**, since those block progress and need to live next to the relevant section. Move "Should consider" and "FYI" into a dedicated `## Reviewer findings` section at the bottom of the plan. Print a separate end-of-run summary to the terminal.

- **Auto-fixed issues**: silently apply, **then** log them in a "What I changed" section. Both. Silent application without a log destroys auditability; logging without applying wastes the agent's leverage.
- **Inline callouts**: only for must-address. Everything else lives in an end-of-plan section.
- **Mid-flow interrupt**: only when a reviewer's finding would invalidate downstream reviewers' work. Otherwise batch.
- **Final terminal summary template**:

```markdown
## Plan complete — 3 reviewers ran (testing, structure, security)

**Auto-applied (5):** Fixed in the plan, no action needed.
- testing: added missing factory for `CourseRegistration` in test plan section 4.2
- structure: moved `ContentSnapshot` to `content_engine` per existing app boundaries
- security: added CSRF note to HTMX form section
- ... (collapsed if >5)

**Decisions needed (2):** See inline `> Must address` callouts in plan.md.
1. **security § auth**: API key rotation isn't covered. Proposed: add to Phase 2. OK?
2. **structure § cross-app import**: plan imports from `student_progress` into `content_engine`. Proposed: invert via signal. OK?

**Worth considering (3):** See `## Reviewer findings` at bottom of plan.
- testing: consider Playwright coverage for the new wizard flow
- structure: `MarkdownContent` could be reused instead of new model
- security: rate-limit on registration endpoint

**FYI (4):** Listed in `## Reviewer findings`. No response required.
```

The user reads ~10 lines, knows exactly what's auto-done, what blocks them, and what's optional. Inline callouts remain navigable because there are few of them. Trust is preserved by always logging auto-fixes.

## Sources

- [About GitHub Copilot code review (GitHub Docs)](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [60 million Copilot code reviews and counting (GitHub Blog)](https://github.blog/ai-and-ml/github-copilot/60-million-copilot-code-reviews-and-counting/)
- [Anthropic claude-code /code-review plugin source](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)
- [obra/superpowers code-reviewer agent](https://github.com/obra/superpowers/blob/main/agents/code-reviewer.md)
- [Sourcegraph Sherlock — automating security code reviews](https://sourcegraph.com/blog/lessons-from-building-sherlock-automating-security-code-reviews-with-sourcegraph)
- [GitHub Spec Kit — spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)
- [Aider architect mode](https://aider.chat/2024/09/26/architect.html)
- [Google eng-practices — review standard](https://google.github.io/eng-practices/review/reviewer/standard.html)
- [Priority vs Severity (BlueLabel)](https://www.bluelabellabs.com/blog/dont-confuse-a-bugs-priority-with-its-severity/)
- [Comprehensive Guide to Priority Codes (Tech Lead Curiosity)](https://techleadcuriosity.substack.com/p/a-comprehensive-guide-to-priority-codes-in-technical-development-cee93c1414a3)
- [Microsoft Agent Framework — Human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Building Human-In-The-Loop Agentic Workflows (TDS)](https://towardsdatascience.com/building-human-in-the-loop-agentic-workflows/)
- [Best practices for Claude Code subagents (PubNub)](https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/)
