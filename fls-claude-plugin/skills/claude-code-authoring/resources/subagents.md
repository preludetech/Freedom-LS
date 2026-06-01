# Subagent capabilities & limits (Claude Code 2.1.x)

Distilled from `research_subagent_capabilities.md`. Every claim here traces to that research.

## No nesting
Subagents **cannot spawn subagents**. If `Agent` is listed in a subagent's `tools`, it is ignored at
depth 1. Depth is capped at 1: main session → subagent. Workflows needing "nested delegation" must
keep all fan-out in the main session (depth 0) and use skills / read-and-follow helper files inside
the subagent instead.
Source: https://code.claude.com/docs/en/sub-agents (and issue #4182).

## No slash commands inside a subagent
There is **no `SlashCommand` tool** in a subagent. Slash commands are CLI/interactive constructs.
A subagent can use built-in tools, the `Skill` tool, and configured MCP tools — but never `/command`.
**Workaround:** implement reusable logic as a **skill**, or have the subagent **read the helper `.md`
and follow its steps**. (This is why the SDD mechanic follows `protected/update_todo.md` literally
rather than running `/sdd:...`.)
Source: https://code.claude.com/docs/en/sub-agents

## Input is spawn-time only
The `Agent` tool's `prompt` string is the **only** channel for passing data into a subagent. Compose
it dynamically (file paths, gathered answers, prior errors). There is **no mid-run messaging** — once
running, a subagent runs to completion and returns one result. (`SendMessage` under
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is experimental and out of scope.) "Resuming a subagent" in
practice = spawn a fresh one with more context.
Source: https://code.claude.com/docs/en/sub-agents

## Skills in subagents
- **Auto-invocation (default):** skill descriptions load into the subagent's context; it can invoke
  relevant ones via the `Skill` tool (which is in `tools` by default).
- **Preloading (explicit):** an agent file's `skills:` frontmatter injects the **full content** of
  named skills at startup.
- Subagents **inherit permissions** from the session; no extra grant needed for the `Skill` tool.
Source: https://code.claude.com/docs/en/skills

## Agent `.md` frontmatter
`name` + `description` required; all else optional. Key fields: `tools` (allowlist; omit = inherit
all), `disallowedTools` (denylist, applied before `tools`), `model`, `skills` (preload), `effort`
(`low`…`max`), `memory` (`user|project|local`), `color`, `maxTurns`, `isolation: worktree`.
**Model resolution order:** `CLAUDE_CODE_SUBAGENT_MODEL` → per-spawn `model` param → frontmatter
`model` → parent's model. Plugin subagents ignore `permissionMode`, `mcpServers`, and `hooks`.
Source: https://code.claude.com/docs/en/sub-agents
