# Claude Code Features for the SDD Workflow — Research

**Researched:** 2026-05-30. Targets Claude Code 2.x. The v2.0 line shipped 2025-09-29
("Enabling Claude Code to work more autonomously") with **checkpoints/rewind, background tasks,
subagents, and hooks**; the 2.1.x line (current, ~v2.1.15x as of April–May 2026) refined plan
mode, AskUserQuestion, structured outputs, dynamic multi-agent workflows, and added the
`disallowedTools` frontmatter and `MessageDisplay` hook event. Docs now live under
`code.claude.com/docs` (Claude Code) and `platform.claude.com/docs` (Agent SDK); the old
`docs.claude.com` paths 301-redirect there.

## Summary

The SDD workflow (idea → spec → spec review → plan → security/structure review → implement →
code review → QA → finish, driven by a `todo.md` and per-phase sub-agents with "(User) review
and approve" gates) maps cleanly onto current Claude Code primitives. Highest-leverage findings:

- **Hooks** give *deterministic* enforcement (run tests/lint, block edits to protected files,
  validate that a phase actually produced its artefact, auto-tick todos) instead of trusting the
  model to remember. Single biggest reliability win.
- **AskUserQuestion** turns the freeform "(User) approve" gates into structured multiple-choice
  prompts. **Critical caveat:** it is **NOT available inside Task-spawned subagents** — so approval
  gates must be driven by the *orchestrator* session, not by a phase subagent.
- **Permission modes / plan mode** (`defaultMode` in settings.json): run review phases in `plan`
  mode for a hard read-only guarantee; run implement in `acceptEdits`.
- **Structured outputs** (JSON-schema-validated agent results with retry-on-mismatch) are a real
  feature, but in the **Agent SDK**, not the interactive-CLI subagent/Task path (open request:
  GitHub issue #20625). For the slash-command flow, keep **file-based hand-off** (`spec.md`,
  `plan.md`, `todo.md`) and validate artefacts with a hook.
- **Checkpoints/rewind** + **background tasks** make implement/QA safer and faster.
- **SlashCommand tool** lets the `next` orchestrator invoke phase commands programmatically;
  **disable-model-invocation** / **disallowedTools** give least-privilege control per phase.

Confidence is high on the documented mechanics; items relying on secondary sources are flagged.

---

## 1. Hooks

**What it is.** User shell commands fired at lifecycle events, configured in `settings.json` under
`"hooks"` with a `matcher` (tool name/regex such as `Write|Edit` or `mcp__playwright__.*`). Events
documented for current Claude Code: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`,
`SubagentStop`, `StopFailure`, `Notification`, `PreCompact`, `SessionStart`, `SessionEnd`, plus the
newer `MessageDisplay` (v2.1.152, transform/hide assistant text). Events run at three cadences:
once per session (`SessionStart`/`SessionEnd`), once per turn (`UserPromptSubmit`/`Stop`), and on
every tool call (`PreToolUse`/`PostToolUse`). A `Stop` hook declared in a subagent's frontmatter is
auto-converted to a `SubagentStop` scoped to that subagent.

Hooks receive event JSON on stdin (`session_id`, `transcript_path`, `cwd`, `tool_name`,
`tool_input`, `tool_response`…). Control mechanisms:
- **Exit codes:** `0` = success (stdout shown), `2` = blocking error (stderr fed back to Claude),
  other = non-blocking error. For `PreToolUse`, exit 2 **blocks the tool call**; for
  `UserPromptSubmit` it blocks/erases the prompt; for `Stop`/`SubagentStop` it **blocks stopping
  and forces the agent to continue**.
- **JSON output (advanced):** `continue`, `stopReason`, `suppressOutput`, `systemMessage`.
  `PreToolUse` supports `hookSpecificOutput.permissionDecision: "allow" | "deny" | "ask"`
  (newer builds also `"defer"`) with a reason, and can **modify tool input** before execution.
  `PostToolUse` and `UserPromptSubmit` support `decision: "block"` + `reason` and can inject
  `additionalContext`. v2.1.139 added exec-form hooks (`args: string[]`, no shell parsing).

**Concrete SDD application.**
- *Enforce tests/lint deterministically:* `PostToolUse` on `Edit|Write` runs `uv run pytest` /
  linters in the implement phase, feeding failures back (exit 2) so the agent cannot proceed on red.
- *Protect approved artefacts:* `PreToolUse` on `Edit|Write` `deny`s edits to `spec.md`/`plan.md`
  after their phases are approved, or blocks writes outside the worktree.
- *Auto-tick todos:* `SubagentStop`/`PostToolUse` updates `todo.md` when a phase finishes, instead
  of relying on the model.
- *Validate phase output (the structured-handoff substitute):* a `SubagentStop`/`Stop` hook greps
  the produced artefact for required sections/front-matter and blocks (exit 2) with a corrective
  message if malformed — deterministic validation without true JSON schemas.
- *Inject phase state:* `SessionStart`/`UserPromptSubmit` loads current `todo.md` so a fresh
  session always knows where the workflow stands.

**Confidence:** High (official hooks reference).

---

## 2. Plan Mode & Permission Modes

**What it is.** Five permission modes (set via `permissions.defaultMode` in `settings.json`, or
cycled with Shift+Tab): `default` (prompt per tool), `acceptEdits` (auto-accept file edits),
`plan` (research/propose only — reads files and runs read-only shell exploration but **must not
edit source**), `dontAsk` (auto-deny anything not in `allow`), and `bypassPermissions` (skip
checks; protected paths like `.git`/`.claude` still prompt). Plan mode is actively maintained
across the 2.1.x line and is the natural home for clarifying questions. The model leaves plan mode
via the internal **`ExitPlanMode`** tool, which presents the plan and asks the user to approve;
plan-mode turns are required to end with either `AskUserQuestion` (clarify) or `ExitPlanMode`
(approve) — it is forbidden to ask for approval any other way. In plan mode, codebase research is
delegated to built-in **Explore** (Haiku-powered, token-efficient search) and **Plan** subagents.

**Concrete SDD application.**
- Run the read-only phases (idea refinement, spec review, plan, security review, structure review,
  code review) in **`plan` mode** so they physically cannot write code — exactly the guarantee
  those gates want.
- Run **implement** with `defaultMode: "acceptEdits"` for autonomy, fenced by `deny` rules and
  `PreToolUse` hooks.
- Use the built-in **`ExitPlanMode` approval prompt** as the "(User) approve the plan" gate for the
  planning phase rather than re-implementing approval in prose.
- The Explore subagent is a free token-efficiency win for the research-heavy idea/spec phases.
- Different phases can ship their own `.claude/settings.json` `defaultMode` or declare restricted
  `allowed-tools`/`disallowed-tools`.

**Confidence:** High on modes/settings; medium on `ExitPlanMode` internals (documented as the
plan-presentation tool, corroborated by secondary sources, not a user-typed command).

---

## 3. Structured Outputs from Agents / Sub-agents

**What it is.** Structured outputs **do** exist: you declare a JSON Schema and the agent is forced
to call a structured-output tool, with validation at the tool-call layer and **automatic retry on
mismatch**, so you get validated JSON rather than parsing free text. **However**, this is an
**Agent SDK** feature (programmatic `query`/output-format option), **not** currently exposed for
Claude Code's interactive-CLI subagents spawned via the **Task tool** — those return free-form
text to the parent (open request: GitHub issue #20625, "Support structured output schemas for
Claude Code subagents"). The built-in subagents also **cannot nest** (a subagent can't spawn
subagents).

**Concrete SDD application / why-not.**
- In the slash-command/Task-subagent flow, do **NOT** rely on a subagent emitting clean
  schema-validated JSON for hand-off — it isn't enforced there.
- Keep the robust pattern the workflow already uses: **file-based hand-off** with fixed-name
  artefacts (`spec.md`, `plan.md`, `todo.md`) as the durable, inspectable contract between phases.
- Approximate structured reliability by (a) giving each phase command a strict output template
  (required headings/front-matter) and (b) adding a `SubagentStop`/`PostToolUse` **validation hook**
  (section 1) that blocks on malformed artefacts. This moves validation from "hope it complied" to
  deterministic enforcement.
- If a specific step genuinely needs machine-readable validated JSON (e.g. a programmatic planner
  feeding control flow), implement *that* step via the **Agent SDK** with an output schema, outside
  the interactive slash-command flow.

**Confidence:** High that schema-validated output is SDK-only today and Task subagents return text;
based on official structured-outputs docs (snippet), issue #20625, and corroborating articles.

---

## 4. AskUserQuestion / Interactive Prompting

**What it is.** Built-in tool (added ~v2.0.21) that pauses and asks the user **1–4 questions**,
each with a short **`header` (max ~12 chars)**, full question text, and **2–4 selectable
`options`**; supports `multiSelect: true`, an auto-added **"Other"** free-text choice, a
**"(Recommended)"** marker on the suggested option, and a `previewFormat` (`markdown`/`html`) for
option previews. **Limitations:** **60-second timeout**; and crucially it is **NOT available inside
subagents spawned via the Task tool** — only the main/orchestrator session can ask. It is heavily
used in plan mode to clarify requirements before `ExitPlanMode`.

**Concrete SDD application.**
- Replace each "(User) review and approve" gate with `AskUserQuestion`, e.g. *"Approve the spec?"*
  → `Approve` / `Request changes` / `Reject`, branching on the choice. Deterministic decision
  points instead of parsing prose.
- Collect early scoping decisions in idea/spec phases (e.g. "Which app owns this model?",
  "HTMX partial or full page?") as multiple-choice.
- Use it at the security/structure review gate to explicitly accept/reject a flagged cross-app
  dependency, recording the choice.
- **Architectural consequence:** because AskUserQuestion can't run in a Task subagent, the
  **approval gates must live in the orchestrator** (the `next`/`start` session that spawns phase
  agents), not inside the phase subagent itself. Phase subagents do the work and write artefacts;
  the parent runs the approval question. This is a concrete structural recommendation for the SDD
  commands.

**Confidence:** High on existence and the subagent limitation; field constraints (header length,
counts) from the published tool description and Agent SDK user-input docs (official docs page for
the tool itself is acknowledged as thin — CC issues #10346/#20275).

---

## 5. Background Tasks

**What it is.** Long-running processes (dev servers, watchers, long test runs) run in the
background without blocking the session; introduced 2.0.0, multiple simultaneous background tasks
added in 2.0.10, with later fixes for pinned/idle background sessions (2.1.147). Listed/killable
via `/bashes`.

**Concrete SDD application.**
- Start `uv run python manage.py runserver` and `npm run tailwind_build` (watch) as background
  tasks for the **QA / Playwright** phase so the agent drives the browser while the server runs.
- Run a long `uv run pytest` suite in the background during implement and reap results later.

**Confidence:** High (changelog + autonomy announcement).

---

## 6. Checkpoints / Rewind

**What it is.** Claude Code 2.0 auto-saves code state before each edit. Rewind via `/rewind` or
double-`Esc`; the menu lists each prompt and offers: restore code+conversation, restore
conversation only, restore code only, or "Summarize from here." **Only direct file edits made
through Claude's editing tools within the current session are tracked** — it is **not** a git
substitute and won't capture external/terminal changes.

**Concrete SDD application.**
- During **implement**, checkpoints let an agent attempt an ambitious change and cleanly revert if
  the post-edit test hook fails — safer autonomous iteration.
- Complements **git worktree** isolation: the worktree isolates the *feature*; checkpoints give
  *within-session* undo. `finish_worktree` still owns durable git history.

**Confidence:** High (checkpointing docs + autonomy announcement).

---

## 7. Output Styles & settings.json

**What it is.** *Output styles* (`outputStyle` in settings; managed via `/output-style` or
`/config`) swap parts of Claude Code's system prompt/persona. Built-ins include **default**,
**Proactive** (acts immediately, fewer pauses), **Explanatory** (adds teaching "Insights"), and
**Learning** (asks you to write `TODO(human)` snippets). They differ from CLAUDE.md (adds context)
and slash commands (one-shot prompts) by changing base behavior for the whole session; selection
saves to `.claude/settings.local.json`. `settings.json` (precedence: enterprise > CLI args >
`.local.json` > project `.json` > user) also controls `permissions` (`defaultMode`,
`allow`/`deny`/`ask`, `additionalDirectories`), `hooks`, `disableAllHooks`, `model`, `env`.

**Concrete SDD application.**
- Ship a **project `.claude/settings.json`** encoding the guardrails: `deny` rules for protected
  paths, test/lint `hooks`, and a sensible `defaultMode`. The SDD guarantees then travel with the
  repo for every contributor.
- Output styles are **low value** here — SDD behavior belongs in command files + hooks, not a
  persona. Minor possible use: a terse style to cut token chatter in long runs. (Nice-to-have.)

**Confidence:** High on settings; the output-styles relevance is a judgement call.

---

## 8. CLAUDE.md Memory, Imports & Token-Efficient Command/Skill Files

**What it is.** Hierarchical memory: enterprise → project `./CLAUDE.md` → user `~/.claude/CLAUDE.md`
(`CLAUDE.local.md` deprecated). Files support `@path` **imports** (relative/absolute/home),
**recursive up to 5 hops**, not evaluated inside code spans/blocks. Subtree `CLAUDE.md` files load
**on-demand** when working in that directory. Slash-command files have front-matter
(`allowed-tools`, `disallowed-tools`, `argument-hint`, `description`, `model`,
`disable-model-invocation`), support `$ARGUMENTS`/`$1`, `!`-prefixed bash (output injected), and
`@file` references. Skills load their body only when triggered by their `description`, and as of
v2.1.152 can declare `disallowedTools` to remove tools while active.

**Concrete SDD application (token efficiency — the spec's own goal).**
- Keep root `CLAUDE.md` lean; push deep/rare detail into `@imports` or **subtree `CLAUDE.md`** so
  it loads only when relevant.
- Structure each phase as a **slash command** with a tight `description`, least-privilege
  `allowed-tools`/`disallowed-tools` (review commands read-only), and `model` per phase (cheaper
  model for mechanical phases, stronger for spec/plan). Use `@`-references to pull in only the
  relevant artefact rather than restating it.
- Use `!`-prefixed bash in command front-matter to inject *just* the needed state (current
  `todo.md`, `git status`) instead of extra tool round-trips.
- Move large reusable instructions into **skills** (loaded on trigger) so they don't sit in every
  command's context; each command references the skill rather than inlining it.

**Confidence:** High (official memory/slash-command docs).

---

## 9. Other Relevant Features

**SlashCommand tool.** Lets Claude invoke custom slash commands programmatically; eligible commands
need a `description`, opt out per-command with `disable-model-invocation: true`, and a character
budget limits how many command descriptions are shown to the model. **SDD use:** the `next`
orchestrator can call SlashCommand to run the next phase command directly instead of a human typing
it — the backbone for "figure out the next step and run it." Mind the description budget across many
`sdd:*` commands; trim descriptions or set `disable-model-invocation` on helper commands.

**Dynamic workflows / multi-agent orchestration (v2.1.154).** Claude can now orchestrate "tens to
hundreds of agents in the background," with `/workflows` showing run history; subagents receive a
`CLAUDE_CODE_SESSION_ID` env var (v2.1.147). **SDD use:** the parallelizable review phases
(security + structure) could fan out as concurrent subagents, with the orchestrator gating on
both results.

**Subagents (general).** Defined as Markdown + YAML front-matter in `.claude/agents/`
(`name`, `description`, optional `tools`, `model` alias or `inherit`); own clean context window;
**cannot nest**; **cannot use AskUserQuestion**; return free-form text to the parent. Right
primitive for per-phase isolation — set least-privilege `tools` and pick `model` by phase
cost/complexity.

**MCP.** Hooks and tool restrictions understand MCP tools (`mcp__server__tool`). The project
already uses Playwright MCP — the QA phase can be gated/allowed precisely via `mcp__playwright__.*`
matchers in hooks and `allowed-tools`.

**Confidence:** High on SlashCommand, subagents, MCP; dynamic-workflow specifics from the
changelog (v2.1.154).

---

## References

- Hooks reference — https://code.claude.com/docs/en/hooks
- Hooks (Agent SDK) — https://platform.claude.com/docs/en/agent-sdk/hooks
- Subagents — https://code.claude.com/docs/en/sub-agents
- Slash commands (incl. SlashCommand tool) — https://code.claude.com/docs/en/slash-commands
- Permission modes — https://code.claude.com/docs/en/permission-modes
- Settings — https://code.claude.com/docs/en/settings
- Output styles — https://code.claude.com/docs/en/output-styles
- Memory (CLAUDE.md, @imports) — https://code.claude.com/docs/en/memory
- Checkpointing — https://code.claude.com/docs/en/checkpointing
- Checkpointing (Agent SDK) — https://platform.claude.com/docs/en/agent-sdk/file-checkpointing
- AskUserQuestion / handle approvals & user input — https://code.claude.com/docs/en/agent-sdk/user-input
- AskUserQuestion tool description (community mirror) — https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-askuserquestion.md
- AskUserQuestion docs gap (issues) — https://github.com/anthropics/claude-code/issues/10346 ; https://github.com/anthropics/claude-code/issues/20275
- Structured outputs from agents — https://code.claude.com/docs/en/agent-sdk/structured-outputs (redirects to https://platform.claude.com/docs/en/agent-sdk/structured-outputs)
- Structured output for CC subagents (feature request) — https://github.com/anthropics/claude-code/issues/20625
- "Enabling Claude Code to work more autonomously" (CC 2.0; 2025-09-29) — https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously
- Changelog — https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md
- Release notes — https://platform.claude.com/docs/en/release-notes/claude-code
