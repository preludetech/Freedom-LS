# Sub-agent Capabilities Research (Claude Code, May 2026)

## Summary

Claude Code v2.1.63+ supports sub-agents with specialized isolation, tool restrictions, and skill injection. Sub-agents cannot spawn their own sub-agents (no nesting), and skills auto-trigger inside sub-agents based on their description unless disabled. Sub-agents receive delegated work only through the Agent tool with a prompt string; there is no mid-run messaging, but they can be resumed with their full history intact. Slash commands cannot be invoked from within sub-agents—only built-in tools and skills apply. Custom agent definitions use YAML frontmatter (name, description, tools, model, skills, etc.) in `.claude/agents/*.md` files or passed via CLI/SDK.

---

## 1. Skills in Sub-agents: Auto-invocation, Access, and Exposure

**Question:** Can a Task/Agent sub-agent use Skills? Do skills auto-trigger inside sub-agents? Do sub-agents need permission to use a skill? How are skills exposed to sub-agents vs the main agent?

### Concrete Answer

- **Sub-agents can use skills two ways:**
  1. **Auto-invocation (default)**: Skills with `disable-model-invocation: false` (default) are automatically available to sub-agents. Their descriptions are loaded into the sub-agent's context, and the sub-agent can invoke them via the Skill tool during execution if relevant to its task.
  2. **Preloading (explicit)**: The `skills` frontmatter field in an agent definition injects the *full content* of named skills into the sub-agent's context at startup, so the sub-agent arrives with that knowledge ready to apply.

- **Permissions:** Sub-agents inherit permissions from the parent session. No additional permission is needed to use the Skill tool within a sub-agent, as long as Skill is in the sub-agent's `tools` list (which it is by default unless explicitly denied).

- **Skill descriptions loaded into context:** Every sub-agent receives a listing of available skills (by description) in its startup context, similar to the main session. Long skill descriptions are truncated to fit the context budget (1% of model window by default).

- **Difference vs main session:**
  - **Main session:** Skill descriptions loaded automatically; full skill content loads only when invoked.
  - **Sub-agent (default):** Same as main session—descriptions in context, full content on invocation.
  - **Sub-agent (preloaded):** Full skill content injected at startup via `skills` field; no lazy loading.

### Implication for SDD Slash-Command Workflow

If an SDD slash command runs in a sub-agent context (e.g., `context: fork` in a skill), the sub-agent can invoke other skills during execution as needed. However, slash commands themselves cannot be invoked by sub-agents—only skills and built-in tools work inside sub-agent contexts. This means:

- **Design recommendation:** If an SDD slash command spawns a sub-agent, use skills (not slash commands) inside the sub-agent to delegate focused subtasks.
- **Preloading skills:** Use the `skills: [skill-name]` frontmatter to inject task-critical knowledge into the sub-agent at startup, reducing the need for the sub-agent to discover skills during execution.

---

## 2. Slash Commands from Sub-agents: Invocation and Tool Support

**Question:** Can a sub-agent invoke a slash command? Is there a `SlashCommand` tool letting an agent invoke slash commands programmatically? Can sub-agents use it or only the main agent? Constraints?

### Concrete Answer

- **Sub-agents cannot invoke slash commands directly.** There is no `SlashCommand` tool. Slash commands (e.g., `/commit`, `/run`, `/debug`) are CLI/interactive-mode constructs that do not exist as callable tools within sub-agent contexts.

- **What sub-agents can invoke:**
  - Built-in tools: Read, Write, Edit, Bash, Grep, Glob, Skill, Agent (if in `tools` list)
  - Skills via the Skill tool
  - MCP tools (if configured in the sub-agent's `mcpServers` field)
  - **No slash commands, no `/` syntax**

- **Skills as a workaround:** A skill with `disable-model-invocation: false` can be invoked by a sub-agent, effectively replicating a slash command's behavior. For example, `/commit` can be implemented as a skill, and sub-agents can invoke it with `Skill(commit)`.

### Implication for SDD Slash-Command Workflow

- **SDD slash commands must run in the main session, not in sub-agents.** If `/fls:sdd:next` needs to invoke another slash command (e.g., `/fls:sdd:plan_from_spec`), do it from the main conversation, not from within a sub-agent.
- **Skill-based delegation inside sub-agents:** For self-contained subtasks, use skills (e.g., a skill that runs test validation) rather than relying on slash command invocation.
- **Sequential workflows in main session:** Chain slash commands in the main agent to maintain full control over the workflow.

---

## 3. Passing Input into Sub-agents: Data Flow and Resumption

**Question:** How is info passed when spawning via the Task tool—only the prompt string at spawn time? Can the orchestrator inject data it just collected from the user? Once running, can the orchestrator send a sub-agent more messages mid-run (SendMessage / resumable / continue-by-id)? Document any resume/continue mechanism.

### Concrete Answer

**At spawn time:**
- The Agent tool accepts a `prompt` parameter containing a text string. This is the **only channel** for passing data from orchestrator to sub-agent at invocation time.
- The orchestrator can compose this prompt dynamically, including file paths, error messages, JSON, or any other context collected from the user.
- No structured data payload or variable injection beyond the prompt string.

**Mid-run communication:**
- **No direct mid-run messaging.** Once a sub-agent starts, the orchestrator cannot send it additional messages until it completes. The sub-agent runs to completion (or hits `maxTurns` limit) and returns a single final result.
- **SendMessage tool for resumption (experimental):** Available when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set. Used to resume a stopped sub-agent by sending it a new message and its agent ID.

**Resumption mechanism:**
- When a sub-agent finishes, Claude receives its `agentId` in the Agent tool result.
- To resume: pass `resume: sessionId` in the next query's options, include the agent ID in the prompt, and re-invoke the Skill tool or Agent tool with the agent ID.
- Resumed sub-agents retain **full conversation history** (all previous tool calls, results, reasoning) and continue from exactly where they left off, not from scratch.
- Subagent transcripts persist in separate files from the main conversation, independent of main-session compaction.

### Implication for SDD Slash-Command Workflow

- **Stateless sub-agent invocations:** Each sub-agent spawn is passed all context it needs in the prompt. The orchestrator cannot hand off data mid-execution.
- **Recommendation for SDD:** If the `/fls:sdd:plan_from_spec` phase generates a plan, include that plan in the prompt when delegating to a sub-agent for implementation (`/fls:sdd:implement_plan`). Do not attempt mid-run updates.
- **Persistent sub-agents:** If a step needs iterative refinement (e.g., back-and-forth on a plan), consider running it in the main session or resuming a named sub-agent across multiple turns with `SendMessage` (experimental feature).
- **Session capture:** Always save the session ID when spawning sub-agents so you can resume them later if needed.

---

## 4. Nested Sub-agents: Nesting Depth Limits

**Question:** Can a sub-agent spawn its own sub-agents? Depth limits?

### Concrete Answer

- **No nesting allowed.** Sub-agents cannot spawn their own sub-agents. If `Agent` is included in a sub-agent's `tools` list, it is ignored, and the sub-agent cannot invoke the Agent tool.
- **No depth limit** because depth is capped at 1: main session → sub-agent. That's it.
- **Documented restriction:** "Subagents cannot spawn other subagents. If your workflow requires nested delegation, use [Skills](/en/skills) or [chain subagents](#chain-subagents) from the main conversation."

### Implication for SDD Slash-Command Workflow

- **Hierarchical workflows must stay in the main session:** If `/fls:sdd:start` needs to spawn multiple specialized sub-agents (e.g., one for planning, one for implementation), the main session orchestrates those spawns; each sub-agent runs independently.
- **Skill-based composition:** Complex workflows inside sub-agents can be built by invoking multiple skills in sequence, since skills can call each other indirectly.
- **Sequential chaining from main session:** For deep workflows, keep the orchestration loop in the main agent and chain sub-agent invocations from there.

---

## 5. Agent Definitions: `.claude/agents/*.md` Frontmatter Fields

**Question:** `.claude/agents/*.md` frontmatter fields (name, description, tools, model) and how `tools` and `model` work.

### Concrete Answer

**Frontmatter fields (all optional except `name` and `description`):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique lowercase identifier (e.g., `code-reviewer`). Used to reference the agent. Filename does not have to match. |
| `description` | string | Yes | Natural language description of when to use this agent. Claude matches tasks to agents based on this. |
| `tools` | list/string | No | Allowed tools (allowlist). If omitted, inherits all tools from parent. Syntax: `tools: Read, Grep, Glob, Bash` or YAML list. |
| `disallowedTools` | list/string | No | Tools to deny (denylist). Removed from inherited or specified list. If both `tools` and `disallowedTools` are set, `disallowedTools` is applied first, then `tools` is resolved against the remainder. |
| `model` | string | No | Model override: `sonnet`, `opus`, `haiku`, a full model ID (e.g., `claude-opus-4-8`), or `inherit` (default). Sub-agents use this model instead of the parent's. |
| `skills` | list | No | Skill names to preload into the agent's context at startup. Full skill content is injected (not just the description). Sub-agents can still invoke unlisted skills through the Skill tool. |
| `permissionMode` | string | No | Permission mode: `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, or `plan`. Ignored for plugin sub-agents. |
| `mcpServers` | list | No | MCP servers available to this agent. Each entry is a server name (string) or inline config (object). Ignored for plugin sub-agents. |
| `hooks` | object | No | Lifecycle hooks (PreToolUse, PostToolUse, Stop). Ignored for plugin sub-agents. |
| `maxTurns` | number | No | Maximum agentic turns before the sub-agent stops. |
| `memory` | string | No | Memory scope: `user`, `project`, or `local`. Enables persistent cross-session learning. |
| `background` | boolean | No | Run as a background task when invoked (default: false). |
| `effort` | string | No | Effort level: `low`, `medium`, `high`, `xhigh`, `max`. Overrides session effort for this agent. |
| `isolation` | string | No | Set to `worktree` to run the agent in a temporary git worktree, giving it an isolated repo copy. |
| `color` | string | No | Display color for the agent in task list: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan`. |
| `initialPrompt` | string | No | Auto-submitted as the first user turn when this agent runs as the main session (via `--agent` flag or `agent` setting). |

**How `tools` and `model` work:**

- **`tools` (allowlist):** Only listed tools are available to the sub-agent. If `tools` is omitted, the sub-agent inherits all tools from the parent conversation. To restrict a sub-agent, list only the tools it needs. To block specific tools while allowing others, use `disallowedTools` instead.
  - Example: `tools: Read, Grep, Glob` means the sub-agent can only read files and search code; no Bash, Edit, or Write.
  - Special case: `Agent(worker, researcher)` in `tools` restricts which sub-agents can be spawned (allowlist of sub-agent types). If `Agent` is omitted entirely, the sub-agent cannot spawn any sub-agents (always the case—nesting not allowed).

- **`model` resolution order:**
  1. `CLAUDE_CODE_SUBAGENT_MODEL` environment variable (if set)
  2. Per-invocation `model` parameter passed to the Agent tool
  3. Sub-agent definition's `model` frontmatter field
  4. Parent conversation's model
  - Aliases (`sonnet`, `opus`, `haiku`) are resolved at runtime. `inherit` means use the parent's model.

**Example agent definition:**

```yaml
---
name: security-reviewer
description: Expert code review for security vulnerabilities. Use when reviewing code for potential security issues.
tools: Read, Grep, Glob, Bash
model: opus
permissionMode: plan
skills:
  - security-best-practices
  - owasp-checklist
maxTurns: 10
background: false
---

You are a senior security code reviewer specializing in OWASP Top 10 and secure coding practices.

When reviewing code:
1. Identify security vulnerabilities
2. Check for common attack vectors
3. Verify authentication and authorization
4. Ensure input validation

Be thorough and specific in your findings.
```

### Implication for SDD Slash-Command Workflow

- **Define SDD agents in `.claude/agents/`:** Create project-scoped agents for SDD phases (e.g., `sdd-planner`, `sdd-implementer`) with clear descriptions and appropriate tool restrictions.
- **Model selection:** For planning phases, use Opus for deep reasoning; for implementation, Sonnet for speed. Set `model` in the agent definition.
- **Preload skills:** If an SDD phase always needs specific skills (e.g., FLS conventions), list them in the `skills` field so the agent arrives with that knowledge.
- **Tool isolation:** Limit tools per phase (e.g., plan phase gets Read-only; implement phase gets Read+Edit+Write+Bash) to prevent accidental side effects.
- **Scope to project:** Use `.claude/agents/` (not `~/.claude/agents/`) so agent definitions are version-controlled and shared with the team.

---

## References

- [Create custom subagents](https://code.claude.com/docs/en/sub-agents.md) – Full subagent documentation including configuration, invocation, and context management.
- [Extend Claude with skills](https://code.claude.com/docs/en/skills.md) – Skills documentation including preloading into subagents and auto-invocation control.
- [Tools reference](https://code.claude.com/docs/en/tools-reference.md) – Complete tool reference including Agent tool behavior.
- [Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents.md) – Programmatic subagent definition and invocation in TypeScript/Python SDKs, including resumption with SendMessage.
- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview.md) – SDK getting started and general agent patterns.
- [Changelog](https://code.claude.com/docs/en/changelog.md) – Version history; Task tool renamed to Agent in v2.1.63.
