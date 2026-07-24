---
name: claude-code-authoring
description: How Claude Code actually works when authoring commands, skills, and agents — what works
  and what doesn't. Use when writing/editing a slash command, skill, or agent definition, designing
  subagent fan-out, choosing a model tier, or whenever you need to know how Claude Code
  subagents/skills/models behave. Targets Claude Code 2.1.x.
allowed-tools: Read, Grep, Glob
---

# Authoring Claude Code commands, skills, and agents

This skill is the **single source of truth** for the Claude Code behaviour the SDD workflow depends
on. Author commands/skills/agents against these constraints instead of restating them in every file.

> **Target: Claude Code 2.1.x.** Per-agent/per-command `model:` frontmatter, `AskUserQuestion`,
> non-nesting subagents, and "custom commands merged into skills" all hold on this line. There is no
> runtime version check — this is a documented target.

For the *why* and the source citations behind each rule, see the `resources/` files:
[subagents](resources/subagents.md), [model tiering](resources/model_tiering.md),
[the fan-out recipe](resources/fanout_recipe.md), [interactive-CLI notes](resources/interactive_cli.md).

---

## Subagent limits (the load-bearing constraints)

- **No nesting / no fan-out from a subagent.** The `Agent` tool is not exposed at depth 1 — a
  subagent cannot spawn subagents. All fan-out must happen at depth 0 (the orchestrator / main
  thread). Keep orchestration flat.
- **Subagents can't type slash commands.** There is no `SlashCommand` tool inside a subagent.
  **Headline rule: prefer skills (or "read-and-follow this helper file") to slash commands for any
  reusable logic a subagent must run.** A subagent *can* read a helper `.md` and follow its steps; it
  just can't invoke it as `/command`.
- **Spawn-time input only.** The `Agent` tool's `prompt` string is the only channel for passing data
  in. There is no supported mid-run messaging (Agent Teams `SendMessage` is experimental and out of
  scope). Bake every input the worker needs into its prompt.
- **Subagents can't ask the user.** `AskUserQuestion` is orchestrator-only — see Interactive notes.
- **Subagents *can* use skills.** They auto-trigger by description, and an agent file's `skills:`
  frontmatter **preloads** full skill content at startup.
- **Agent `.md` frontmatter:** `name` + `description` required; optional `tools`, `model`, `skills`,
  `effort`, `disallowedTools`, `memory`, `color`, etc. **Model resolution order:**
  `CLAUDE_CODE_SUBAGENT_MODEL` env var → per-spawn `model` parameter → agent frontmatter `model` →
  parent's model (`inherit`).

## Model tiering

- **Per-agent `model:` frontmatter is the reliable knob.** Aliases `haiku` / `sonnet` / `opus`, a
  full dated ID (e.g. `claude-haiku-4-5`), or `inherit`. Default split: mechanical chores → `haiku`;
  non-interactive fan-out → `sonnet`; interactive authoring/review → the session model (depth 0).
- **Inline-execution caveat (critical).** A command/helper file that is *read and followed inline*
  (not invoked as a slash command) keeps the **caller's** model — its own `model:` frontmatter is
  **inert**. So tiering must live on **spawnable agent files**, which always run on their own `model:`.
- **`CLAUDE_CODE_SUBAGENT_MODEL` overrides everything.** If set, it forces one model for *all*
  subagents, flattening every per-agent `model:`. Leave it **unset (or `inherit`)** for normal tiering.
- **Aliases vs pinned IDs.** Aliases (`haiku`/`sonnet`) read well but advance over time; pin dated
  IDs (e.g. `claude-haiku-4-5`) for frozen/reproducible automation.

## Fan-out at depth 0 — the resilience recipe

Fan-out is only legal at depth 0. The resilient shape (full detail in
[resources/fanout_recipe.md](resources/fanout_recipe.md)):

1. **Declare inputs up front**, gather them via `AskUserQuestion` (depth 0 only), bake into prompts.
2. **One output file per unit** (durable artifacts keep real names; intermediate → `.sdd-work/`).
3. **Resume = skip** units whose output already ends `status: ok`.
4. **One subagent per unit** (never one looping over the batch), spawned in parallel.
5. **Structured returns:** `ok` done · `failed` retry the same unit (≤2, include prior error) ·
   `blocked` → gather `needs` via `AskUserQuestion`, re-spawn with answers.
6. **Synthesis is a separate step** that reads the *files* (pass paths, never dump contents).
7. **Clean up `.sdd-work/` on success**; an abandoned scratch dir is what makes resume cheap.

## Interactive-CLI notes

- **`AskUserQuestion` is orchestrator-only** — not available in Task-spawned subagents. Approval and
  input-gathering gates must live at depth 0; subagents fail-fast with `status: blocked`.
- **No enforced structured output in the CLI subagent path** — schema-validated JSON is SDK-only. Use
  **file-based hand-off** (fixed-name artifacts + a `status:` footer) as the durable contract.
- **Exists, deferred (reference only — do not adopt here):** hooks, plan mode / permission modes,
  Agent-SDK structured outputs. Documented in [resources/interactive_cli.md](resources/interactive_cli.md);
  adopting them is explicitly out of scope for the current workflow.

---

## Living examples in this repo

- `claude_plugins/sdd-claude-plugin/commands/README.md` — how the SDD workflow applies all of the above.
- `claude_plugins/sdd-claude-plugin/agents/sdd-mechanic.md` (Haiku) and `sdd-worker.md` (Sonnet) — the tiering agents.
- `claude_plugins/django-stack-claude-plugin/agents/code-reviewer.md` and `claude_plugins/fls-dev-claude-plugin/agents/qa-data-helper.md` — existing `model: opus` agents.
