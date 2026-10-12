# Research: autonomous pipeline patterns

Scope: how other spec-driven / agentic workflows keep running without a human and front-load questions. Web-sourced; where a page was silent this says so. Fetched via summarising tool, so wording is paraphrase, not verbatim, unless quoted.

## spec-kit

- Spec template rule: ambiguity is marked inline as `[NEEDS CLARIFICATION: specific question]` rather than guessed; a completeness checklist requires no markers remain before the spec counts as complete. (https://github.com/github/spec-kit/blob/main/spec-driven.md)
- `clarify` is a bounded interview run once after `specify`: max 5 questions per session, asked one at a time, each with a "why it matters" line and a recommended option (multiple choice 2-5 options, or a short answer of at most 5 words) that the user accepts with "yes"/"recommended". (https://github.com/github/spec-kit/blob/main/templates/commands/clarify.md)
- It scans a fixed coverage taxonomy (functional scope, data model, UX flow, non-functional, integrations, edge cases, constraints, terminology, ...) marking each Clear/Partial/Missing, and only asks about high-impact gaps. It stops early if none are critical. (same clarify.md)
- Recording: each answer goes under `## Clarifications` / `### Session YYYY-MM-DD` as "Q: ... -> A: ...", AND is applied into the relevant spec section, replacing contradicted text. The user may skip, but the agent must warn about rework risk. (same clarify.md)
- `analyze` is strictly read-only. It runs after `tasks`, before `implement`, and cross-checks spec/plan/tasks for duplication, ambiguity, underspecification, constitution conflicts, coverage gaps (requirement with no task, task with no requirement) and terminology drift, with CRITICAL/HIGH/MEDIUM/LOW severities. It edits nothing; fixes happen only if the user approves a remediation plan. (https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md)
- `implement` runs phase by phase through `tasks.md`, marks tasks done, and halts only on defined conditions: unchecked checklist items prompt "proceed anyway? (yes/no)", and a failed non-parallel task stops the run. Parallel `[P]` task failures are reported while others continue. Retry/rollback policy is undefined. (https://github.com/github/spec-kit/blob/main/templates/commands/implement.md)
- Checklists are described as "unit tests for the spec" (self-review), and tests-approved-by-user is a constitution article, i.e. a configurable human gate. (spec-driven.md above)

## Kiro, OpenSpec, BMAD, Claude Code plan mode

- Kiro: Feature Specs go requirements -> design -> tasks (or design-first). Quick Spec generates all three "without approval gates between them", implying normal specs have approval between phases. Optional "Analyze Requirements" checks for inconsistencies, ambiguities and gaps before design. Tasks can be run individually or all at once. The docs fetched say nothing on how questions or assumptions are recorded. (https://kiro.dev/docs/specs/ , https://kiro.dev/docs/specs/feature-specs/)
- OpenSpec: change folder with `proposal.md`, spec deltas, optional `design.md`, `tasks.md`; flow explore -> propose -> apply -> sync -> archive; `explore` is a pre-artifact thinking step. I found nothing on how it records open questions or assumptions. (https://openspec.dev/docs/getting-started , https://pyshine.com/OpenSpec-Spec-Driven-Development-For-AI-Coding-Agents/)
- BMAD: "advanced elicitation" is a second-pass refinement skill other workflows call at natural pauses (user picks a method, confirms changes); "party mode" is a multi-agent discussion. I found no source for a no-pause/YOLO mode. (https://tessl.io/registry/skills/github/bmad-code-org/BMAD-METHOD/bmad-advanced-elicitation , https://docs.bmad-method.org/zh-cn/explanation/party-mode/)
- Claude Code plan mode: read-only exploration, proposes a plan, no edits until the user approves. A single approval gate before execution. (https://code.claude.com/docs/en/common-workflows)
- Claude Code non-interactive/scheduled runs: docs say an autonomous task "can't ask clarifying questions", so the prompt must state what success looks like and what to do with results. (https://code.claude.com/docs/en/common-workflows)

## Anthropic guidance on long-running agents

- "Building effective agents": agents work independently once the task is clear, "potentially returning to the human for further information or judgement", and may pause at checkpoints or blockers. Evaluator-optimizer (one call generates, another critiques in a loop) fits when criteria are clear; add iteration caps as stopping conditions. (https://www.anthropic.com/engineering/building-effective-agents)
- "Effective harnesses for long-running agents": continuity comes from artifacts, not a human: git commits with descriptive messages (revertable), a progress file read at session start, a JSON feature list, an init script. Agents mark a feature passing only after end-to-end testing. The post does not describe human-in-the-loop review. (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

## Ask-early-then-assume patterns

- Evidence that agents silently guess: models default to non-interactive behaviour unless told to ask; one benchmark reports resolve rate 37.94% on underspecified tasks vs 59.52% when asking was allowed (AMBIG-SWE, secondary summary, treat as preliminary). Sources argue for calibrated asking: check the repo first, ask only high-risk ambiguities. (https://codex.danielvaughan.com/2026/04/13/ambig-swe-silent-guessing-problem-codex-cli/ , https://www.alphaxiv.org/abs/2603.26233 , https://charlielabs.ai/blog/for-agents-there-really-are-dumb-questions/)
- Decision ledger / assumption ledger: a skill that logs every guess with rationale, confidence, and the question that would have been asked, sorted by uncertainty so the human can audit the riskiest first. No vendor-standard format exists. (https://mcpmarket.com/tools/skills/decision-ledger-1)
- Interviewer-then-builder: an interviewer agent asks until dangerous ambiguity is gone, then turns answers into a spec the coding agent builds against. (https://dev.to/lars_winstand/i-thought-i-needed-a-smarter-coding-prompt-but-i-actually-needed-my-agent-to-interrogate-me-for-an-2o1h)
- spec-kit's own version: bounded batch of questions with recommended defaults, answers folded into the spec plus a dated Q->A log (clarify.md above).

## Checkpoints vs gates

- Checkpoint pattern: commit stage artifacts and progress logs so work is auditable and revertable later (Anthropic harness post above); spec-kit `analyze` replaces a human cross-artifact review with a read-only report.
- Where a human gate pays off: practitioner consensus (opinion, not controlled evidence) is that the spec/plan is the high-leverage gate because direction is cheaper to change before code exists, with the PR as a lighter, risk-tiered check. (https://latent.space/p/reviews-dead , https://notes.dsebastien.net/30+Areas/33+Permanent+notes/33.02+Content/AI-Assisted+Development+Workflow , https://augmentcode.com/blog/review-the-intent-not-the-code)
- Counter-view: more talk than evidence of dropping human code review; "fresh eyes" AI reviewers share blind spots; review time rises with AI volume (figures unverified). Risk-tiering by blast radius is one proposed answer. (https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews , https://latent.space/p/reviews-dead)
- Fixed specs miss decisions made during implementation; one proposal is to capture those as acceptance criteria for later review. (https://latent.space/p/reviews-dead)

Combined documentation steps: none of the fetched pages (spec-kit, Kiro, OpenSpec, BMAD) describe a docs step at all; OpenSpec's `archive` folds finished change specs into the main specs, the nearest analogue. No evidence either way on one vs several docs steps.

## What transfers to this project

- Idea -> spec (`spec_from_idea`): adopt clarify's shape as one up-front batch: capped count (spec-kit uses 5), each question with a recommended default and why it matters, scan a fixed gap taxonomy, ask only high-impact gaps (clarify.md).
- Idea -> spec: record answers as a dated Q->A "Clarifications" section AND fold them into the spec body, replacing contradicted text (clarify.md).
- Every later stage: when a question is not high-risk, proceed under a logged assumption (decision ledger: rationale, confidence, would-have-asked question) in a stage artifact instead of stopping; the human audits the ledger at the PR (mcpmarket ledger above).
- Spec review: replace the separate review step with an in-step critic subagent plus a spec-kit-style completeness checklist and "no unresolved markers" rule (spec-driven.md; evaluator-optimizer, Anthropic).
- Plan stage: fold structure and new-threat checks into plan-time subagents, using an `analyze`-style read-only cross-artifact check (spec vs plan coverage, terminology drift, severity levels) that reports and lets the planner fix, not a human gate (analyze.md).
- `/sdd:next` `(user)` items: keep only those with a defined halt condition (spec-kit halts on failed non-parallel task / unchecked checklist), and convert the rest to checkpoints; use an iteration cap on critic loops so they cannot spin (Anthropic building-effective-agents).
- Implement: per-change reviewer subagent covering comment/docstring hygiene and test standard fits the evaluator-optimizer pattern; mark tasks done as they pass and commit per task so a failure is revertable (harness post, implement.md).
- Human gate placement: if one gate must remain, evidence-by-opinion favours spec/plan approval before code, then PR review; note the cited consensus is not controlled evidence.
- Docs: no outside precedent for a combined docs step; the case for it rests on the project's own idea, not on these tools. Keep the "only if needed" fls-plugin update conditional.
- Stage artifacts + progress log committed so a post-hoc audit at the PR is possible (harness post).

## References

- https://github.com/github/spec-kit/blob/main/spec-driven.md
- https://github.com/github/spec-kit/blob/main/templates/commands/clarify.md
- https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md
- https://github.com/github/spec-kit/blob/main/templates/commands/implement.md
- https://kiro.dev/docs/specs/
- https://kiro.dev/docs/specs/feature-specs/
- https://openspec.dev/docs/getting-started
- https://pyshine.com/OpenSpec-Spec-Driven-Development-For-AI-Coding-Agents/
- https://tessl.io/registry/skills/github/bmad-code-org/BMAD-METHOD/bmad-advanced-elicitation
- https://docs.bmad-method.org/zh-cn/explanation/party-mode/
- https://code.claude.com/docs/en/common-workflows
- https://www.anthropic.com/engineering/building-effective-agents
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://codex.danielvaughan.com/2026/04/13/ambig-swe-silent-guessing-problem-codex-cli/
- https://www.alphaxiv.org/abs/2603.26233
- https://charlielabs.ai/blog/for-agents-there-really-are-dumb-questions/
- https://mcpmarket.com/tools/skills/decision-ledger-1
- https://dev.to/lars_winstand/i-thought-i-needed-a-smarter-coding-prompt-but-i-actually-needed-my-agent-to-interrogate-me-for-an-2o1h
- https://latent.space/p/reviews-dead
- https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews
- https://notes.dsebastien.net/30+Areas/33+Permanent+notes/33.02+Content/AI-Assisted+Development+Workflow
- https://augmentcode.com/blog/review-the-intent-not-the-code

status: ok
