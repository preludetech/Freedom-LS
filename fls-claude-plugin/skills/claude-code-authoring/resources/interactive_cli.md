# Interactive-CLI notes (Claude Code 2.1.x)

Distilled from `research_cc_features.md`. Every claim traces to that research.

## AskUserQuestion is orchestrator-only
`AskUserQuestion` pauses and asks the user 1–4 questions (each a short `header`, full text, 2–4
`options`, optional `multiSelect`, auto-added "Other", "(Recommended)" marker). **It is NOT available
inside Task-spawned subagents** — only the main/orchestrator session can ask. **Architectural
consequence:** every approval gate and input-gathering step must live at **depth 0**; phase subagents
do the work and write artifacts, then fail-fast with `status: blocked` + `needs: [...]` when they
lack input.
Source: https://code.claude.com/docs/en/sub-agents (subagent limits) ·
https://code.claude.com/docs/en/agent-sdk/user-input

## Structured output is SDK-only → use file-based hand-off
Schema-validated JSON output (forced tool call + retry-on-mismatch) is a real feature, but in the
**Agent SDK**, **not** for interactive-CLI subagents spawned via the Task tool — those return
free-form text (open request: issue #20625). So the workflow uses **file-based hand-off**: fixed-name
artifacts (`1. spec.md`, `2. plan.md`, `todo.md`, `.sdd-work/*.md`) plus a `status:` footer as the
durable, inspectable contract between phases.
Source: https://platform.claude.com/docs/en/agent-sdk/structured-outputs · issue #20625

## Exists, deferred — reference only (do NOT adopt in the current workflow)
These are documented for completeness; adopting them is explicitly out of scope:

- **Hooks** — deterministic lifecycle enforcement (run tests on `PostToolUse`, protect artifacts on
  `PreToolUse`, auto-tick todos on `SubagentStop`, validate artifacts). The biggest *potential*
  reliability lever, but it is new enforcement infra. Source: https://code.claude.com/docs/en/hooks
- **Plan mode / permission modes** (`permissions.defaultMode`: `default`, `acceptEdits`, `plan`,
  `dontAsk`, `bypassPermissions`) — could make review phases hard read-only. Source:
  https://code.claude.com/docs/en/permission-modes
- **Agent-SDK structured outputs** — see above; for a step genuinely needing validated JSON, build it
  via the SDK outside the slash-command flow.

The current SDD refactor *documents* these so future work can decide; it does **not** wire them in.
