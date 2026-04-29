# Scoped agents for SDD tasks

## Problem

The SDD slash commands (`/spec_from_idea`, `/spec_review`, `/threat_model`, `/plan_from_spec`, `/plan_security_review`, `/plan_structure_review`, `/plan_testing_review`, `/plan_dev`, `/plan_qa`, `/implement_plan`, `/do_qa`, `/security-review`, etc.) currently run as the main Claude session or as ad-hoc `Task` subagents. Each invocation inherits whatever tool grants and model the parent session happens to have. This means:

- A reviewer that should only need `Read` on the spec directory can in practice call `Bash`, `WebFetch`, or `Write` anywhere on disk.
- Models are not chosen per task — a cheap mechanical review and a heavy planning pass run on whatever the user picked at session start.
- There is no single place to audit "what is this agent allowed to do, and on what model".

This is the security constraint that gap **G-01** in the `spec-dd-improvements-improve-plan` threat model called out, plus the related model-cost / model-fit problem.

## Idea

Create one purpose-built agent per SDD task, each with:

1. A **minimal, explicit tool allow-list** — e.g. reviewers get `Read` scoped to the spec directory and `Edit` only on the plan file; QA agents get Playwright MCP but no `Bash`; the orchestrator gets `Bash` for `uv run git commit` but not `WebFetch`.
2. A **pre-defined model** chosen per task — a small fast model for shape-validation and mechanical reviews, a stronger model for planning and threat modelling, etc. The model is pinned in the agent definition, not chosen at runtime.
3. A **single source of truth** — agent definitions live under `fls-claude-plugin/agents/` with frontmatter that names the model and tools. Slash commands invoke these agents via `Task` rather than carrying their own ad-hoc prompts and tool grants.

## Rough scope

Agents to create (one per SDD task, names indicative):

- `sdd-spec-author` — runs `/spec_from_idea`
- `sdd-spec-reviewer` — runs `/spec_review`
- `sdd-threat-modeller` — runs `/threat-model`
- `sdd-planner-dev` — runs `/plan_dev` orchestration
- `sdd-planner-qa` — runs `/plan_qa`
- `sdd-plan-security-reviewer` — runs `/plan_security_review` (and its subagent mode under `/plan_dev`)
- `sdd-plan-structure-reviewer` — runs `/plan_structure_review` (and subagent mode)
- `sdd-plan-testing-reviewer` — runs `/plan_testing_review` (and subagent mode)
- `sdd-implementer` — runs `/implement_plan`
- `sdd-qa-runner` — runs `/do_qa` (Playwright MCP)
- `sdd-code-security-reviewer` — runs `/security-review`

Each gets:

- `allowed-tools:` frontmatter listing the minimum set.
- `model:` frontmatter pinning the model.
- A short prompt that delegates to the existing slash-command body or replaces it.

## Open questions

- Which model tier maps to which agent? Reviewers and shape-validators on Haiku, planners and threat-modellers on Opus, implementer on Sonnet — to be decided.
- Do existing slash commands stay as thin wrappers that invoke the agents, or do the agents replace the slash commands entirely?
- How are tool allow-lists enforced when an agent is invoked via `Task` vs. as a top-level command? Confirm the harness honours the agent-definition frontmatter in both cases.
- Migration: do we cut over all SDD commands at once, or one at a time?

## Why now

The `spec-dd-improvements-improve-plan` spec is making `/plan_dev` orchestrate reviewer subagents and apply their findings. Without scoped agents, a prompt-injected reviewer can in principle call `Bash` or `WebFetch` and exfiltrate or modify anything reachable from the worktree. Pinning models per task also lets the planning phase use a stronger model than the mechanical review passes without the user having to switch models manually.

## Out of scope

- Changing what each SDD command *does* — this spec is purely about packaging the existing commands as scoped agents.
- Building new SDD commands.
- Anything outside the SDD workflow (`fls:init`, `fls:app_map`, etc. are unaffected unless we choose to fold them in later).
