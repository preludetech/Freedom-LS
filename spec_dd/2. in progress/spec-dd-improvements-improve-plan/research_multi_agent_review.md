# Research: Multi-Agent Plan Review Orchestration

Research for collapsing `/plan_from_spec`, `/plan_security_review`, and `/plan_structure_review` into a single command that runs reviewers as subagents without inter-step user interruption.

## 1. How real-world tools sequence multiple reviewers

**GitHub Spec Kit** keeps planning explicitly human-in-the-loop. Plan generation, validation against a "Review & Acceptance Checklist", and refinement are separate user-driven steps; Spec Kit deliberately does *not* chain reviewers automatically, on the theory that "the first attempt should not be treated as final" ([github.com/github/spec-kit](https://github.com/github/spec-kit), [GitHub Blog](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)). That is the workflow we are explicitly trying to escape.

**obra/superpowers `subagent-driven-development`** is closer to what we want and is the most directly transferable pattern. It uses an **orchestrator + adversarial reviewer subagents**, runs reviewers **strictly sequentially** (spec-compliance review *first*, code-quality review *second* — running them in parallel or out of order is called out as a critical mistake), and crucially the reviewers **only flag, never edit**. The implementer subagent re-edits in response, then the reviewer re-runs. The orchestrator routes findings; it does not fix anything itself ([SKILL.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md), [spec-reviewer-prompt.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/spec-reviewer-prompt.md)).

**Aider's architect/editor split** separates *reasoning* from *editing* across two model invocations: the architect proposes, the editor turns the proposal into precise diffs. Splitting roles prevents one model from juggling both jobs and lifted Aider's benchmark from sub-80% to 85% ([aider.chat](https://aider.chat/2024/09/26/architect.html)). The lesson generalises: **reviewers and the editor that applies fixes should be different roles**, even if backed by the same model.

**Cursor 2.0 / Composer** runs up to eight agents in parallel using **git worktree isolation** so they never edit the same files simultaneously. Review is a deliberate, non-blocking pass *after* the agents complete (a "Find Issues" button, Bugbot on PRs), not interleaved into generation ([cursor.com/blog/2-0](https://cursor.com/blog/2-0), [agent-best-practices](https://cursor.com/blog/agent-best-practices)).

**Anthropic's own multi-agent guidance** describes the **orchestrator-subagent** pattern: one lead dispatches specialists, collects results, and synthesises a unified report. Parallel only works when subagents touch disjoint artefacts; otherwise sequence them ([Claude blog](https://claude.com/blog/multi-agent-coordination-patterns), [code.claude.com sub-agents](https://code.claude.com/docs/en/sub-agents)).

## 2. Auto-fix vs flag

Practitioners converge on a tiered rule: **auto-fix only when the fix is mechanical and unambiguous; flag when judgement is involved; never silently override architectural intent.** Our current `plan_security_review` and `plan_structure_review` already encode this — they edit directly when the fix is "clear" and insert `> **Security concern:**` / `> **Structure concern:**` callouts otherwise. That heuristic is well-supported in the literature ([paxrel.com agent prompts](https://paxrel.com/blog-ai-agent-prompts), [hamy.xyz 9-agent review](https://hamy.xyz/blog/2026-02_code-reviews-claude-subagents)).

For unattended chains specifically, the dominant pattern is **batch-and-summarise at the end**: collect all findings across reviewers, deduplicate, rank by severity, and present *once* ([hamy.xyz](https://hamy.xyz/blog/2026-02_code-reviews-claude-subagents) describes 9 parallel reviewers folded into a single Critical>High>Medium>Low list with "All Clear" agents collapsed to one-liners). Mid-flow interruption is reserved for blocking ambiguity (missing input, contradiction the orchestrator cannot resolve).

## 3. Convergence vs drift

The named failure mode is **"Logic Lock"** — reviewers with overlapping mandates undo each other's edits indefinitely ([towardsdatascience.com](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/), [cogentinfo.com 2026 playbook](https://cogentinfo.com/resources/when-ai-agents-collide-multi-agent-orchestration-failure-playbook-for-2026)). Practical guards:

- **Sectioned ownership / one-writer rule.** "Never let two agents edit the same file" ([addyosmani.com](https://addyosmani.com/blog/code-agent-orchestra/)). For a single plan document, this means either sequential application of edits, or each reviewer writes only into a reviewer-specific section/callout that the implementer sub-pass merges.
- **Sequential application with re-read.** Each reviewer reads the *current* plan (post any prior edits) before acting. obra/superpowers enforces this strictly ([SKILL.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md)).
- **Non-overlapping mandates.** Security checks security, structure checks app boundaries, testing checks test practice. Our existing commands are already well-disjoint.
- **Iteration cap + escalation.** Hard-stop after N rounds; surface to user. A "95% similarity 3x in a row" semantic-hash detector is overkill for our scale, but a simple 2-pass cap is not ([towardsdatascience.com](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/)).

## 4. Earning user trust without intermediate gates

Where users cannot review between steps, successful tools lean on:

- **Audit trail / decision log.** Every action, who triggered it, why, with what input ([adopt.ai glossary](https://www.adopt.ai/glossary/audit-trails-for-agents), [loginradius.com](https://www.loginradius.com/blog/engineering/auditing-and-logging-ai-agent-activity)). For our case: a `decisions.md` (or appended section in the plan) that lists every reviewer pass, what it edited, what it flagged, and any user input captured along the way.
- **Diff visibility / reversibility.** Cursor's value prop is that *all* agent edits land as reviewable diffs that can be rolled back ([cursor.com/blog/2-0](https://cursor.com/blog/2-0)). Git already gives us this for free — keep edits as commits or at minimum keep the pre-review plan recoverable.
- **End-of-flow summary with severity ranking** ([hamy.xyz](https://hamy.xyz/blog/2026-02_code-reviews-claude-subagents)).
- **In-document callouts that survive the run** so the user can scan without re-reading 800 lines of plan. Our current `> **Security concern:**` / `> **Structure concern:**` blockquote pattern is exactly this and should be preserved.

## 5. Recommendation

Adopt an **orchestrator + sequential reviewer pipeline + end-of-flow summary**, structured as:

1. **First-pass plan** (existing `plan_from_spec` logic, runs as the orchestrator's main thread).
2. **Sequential reviewer subagents**, each spawned as a separate Task: testing-practices → structure → security. Sequential, not parallel, because they all edit the same `2. plan.md` and parallel writers cause Logic Lock. Order matters: testing changes the *shape* of tasks (so it runs first, before structure looks at where code lives); security runs last so it sees the final shape.
3. **Reviewers flag and edit under the existing rules**: edit when mechanical, callout when judgement. No reviewer is allowed to remove another reviewer's callout — only the user resolves callouts.
4. **Decisions log appended to the plan** (`## Review log` section): reviewer name, timestamp, edits made, callouts added, any clarifying questions asked of the user mid-run.
5. **End-of-flow report** the orchestrator prints: severity-ranked list of all open callouts (Critical/High/Medium/Low), passing reviewers as one-liners, and a single "safe to proceed" / "user must resolve callouts first" verdict. Modelled directly on hamy.xyz's 9-agent synthesis.
6. **Mid-flow user input only for blocking ambiguity** (contradictions in the spec, missing inputs). Everything else batches to step 5.

In-document callouts **and** end-of-flow summary — both, not either. The summary is the trust signal ("here is everything that happened"); the callouts are the actionable artefacts the user works through next. This matches what every successful unattended chain in the research (obra/superpowers, hamy.xyz, Cursor's review pass) actually ships.

## Sources
- [github.com/github/spec-kit](https://github.com/github/spec-kit)
- [GitHub Blog — Spec-driven development](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [obra/superpowers SKILL.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md)
- [obra/superpowers spec-reviewer-prompt.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/spec-reviewer-prompt.md)
- [Aider architect/editor split](https://aider.chat/2024/09/26/architect.html)
- [Cursor 2.0 launch](https://cursor.com/blog/2-0)
- [Cursor agent best practices](https://cursor.com/blog/agent-best-practices)
- [Claude — multi-agent coordination patterns](https://claude.com/blog/multi-agent-coordination-patterns)
- [Claude Code subagents docs](https://code.claude.com/docs/en/sub-agents)
- [Addy Osmani — Code Agent Orchestra](https://addyosmani.com/blog/code-agent-orchestra/)
- [hamy.xyz — 9 parallel review subagents](https://hamy.xyz/blog/2026-02_code-reviews-claude-subagents)
- [Towards Data Science — bag-of-agents failure](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/)
- [Cogent — multi-agent failure playbook 2026](https://cogentinfo.com/resources/when-ai-agents-collide-multi-agent-orchestration-failure-playbook-for-2026)
- [Adopt AI — Audit Trails for Agents](https://www.adopt.ai/glossary/audit-trails-for-agents)
- [LoginRadius — Auditing AI agents](https://www.loginradius.com/blog/engineering/auditing-and-logging-ai-agent-activity)
- [Paxrel — AI agent prompt patterns 2026](https://paxrel.com/blog-ai-agent-prompts)
- [claudefa.st — sub-agent best practices](https://claudefa.st/blog/guide/agents/sub-agent-best-practices)
