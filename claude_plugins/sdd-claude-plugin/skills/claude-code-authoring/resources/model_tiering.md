# Model tiering & token efficiency (Claude Code 2.1.x)

## Per-agent `model:` is the reliable knob
A subagent file's `model:` accepts an alias (`haiku`/`sonnet`/`opus`, also `best`, `opusplan`,
`sonnet[1m]`, `opus[1m]`), a full dated ID (e.g. `claude-haiku-4-5`, `claude-sonnet-4-6`,
`claude-opus-4-8`), or `inherit`. If omitted it defaults to `inherit` (the main conversation's model).
Anthropic's cost guidance: *"For simple subagent tasks, specify `model: haiku`."*
Source: https://code.claude.com/docs/en/sub-agents · https://code.claude.com/docs/en/costs

## Default tiers for SDD
- **Haiku** (`sdd:sdd-mechanic`, + low/medium `effort`): test runs, git commits, todo ticking, file
  moves, worktree housekeeping — well-scoped, low-reasoning, tool-driven.
- **Sonnet** (`sdd:sdd-worker`): non-interactive fan-out units (research, review dimensions, scans).
- **Session model (depth 0):** interactive authoring/review commands (spec/plan/review) — so run the
  session itself on a strong model.
- Caveat: if a "mechanical" step must interpret an ambiguous failure, keep that judgement at depth 0
  and let Haiku only run-and-report.

## Inline-execution caveat (critical)
When a command/helper file is **read and followed inline** (not invoked as a slash command), its own
`model:` frontmatter is **inert** — the caller's model governs. So model tiering must live on
**spawnable agent files** (always run on their own `model:`), never on files that are inlined.
Source: https://code.claude.com/docs/en/model-config (per-command `model` applies only when the
command is invoked; spawned work runs on the subagent's model).

## `CLAUDE_CODE_SUBAGENT_MODEL` overrides everything
Official text: it is *"The model to use for all subagents and agent teams. Overrides the
per-invocation `model` parameter and the subagent definition's `model` frontmatter. Set to `inherit`
to use normal model resolution instead."* **Leave it unset (or `inherit`)** for per-agent tiering;
setting it flattens every agent to one model.
The Task per-spawn `model` parameter accepts only the bare enum `sonnet|opus|haiku` (issue #34821).
Source: https://code.claude.com/docs/en/model-config

## Aliases vs pinned IDs
Aliases are recommended-version pointers that advance over time (`opus`→Opus 4.8, `sonnet`→Sonnet
4.6, `haiku`→Haiku 4.5 on the Anthropic API as of mid-2026). For **frozen/reproducible automation**,
pin dated full IDs in frontmatter. Keep one model per agent (don't flip mid-context) to preserve
prompt-cache hits.
Source: https://platform.claude.com/docs/en/about-claude/models/overview

## Token hygiene levers
Delegate verbose ops (tests, fetches, log processing) to subagents so noise stays in their isolated
~200K context and only a short summary returns. Pass **file paths, not file contents**, between
steps. Give each worker a strict short return contract (`status:` + path). Move large reusable
instructions into skills (load on trigger) instead of inlining them in every command.
Source: https://code.claude.com/docs/en/costs ·
https://www.anthropic.com/engineering/effective-context-engineering-for-agents
