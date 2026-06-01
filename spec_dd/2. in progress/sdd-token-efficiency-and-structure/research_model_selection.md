# Research: Claude Code Model Selection & Token Efficiency

Research date: 2026-05-30. Sourced from the current official Claude Code docs (now served
from `code.claude.com/docs`) and `platform.claude.com/docs`, plus Anthropic engineering
posts/model announcements. Goal: inform redesign of a multi-step spec-driven development
(SDD) slash-command workflow that spawns sub-agents for research, spec-writing, planning,
running tests, and git commits.

> Docs location note: `docs.claude.com/en/docs/claude-code/*` now 301-redirects to
> `code.claude.com/docs/en/*`, and `docs.claude.com/en/docs/about-claude/*` redirects to
> `platform.claude.com/docs/en/about-claude/*`. URLs below use the current canonical hosts.

## Summary

- A sub-agent (`.claude/agents/*.md`) can set `model:` in frontmatter. Accepted values:
  aliases `haiku` / `sonnet` / `opus` (also `best`, `opusplan`, `sonnet[1m]`, `opus[1m]`),
  a full model name (same values as the `--model` flag, e.g. `claude-haiku-4-5`), or
  `'inherit'`. If omitted, it defaults to the configured subagent model (effectively
  `inherit` — the main conversation's model).
- A slash command (`.claude/commands/*.md`) can set `model:` in frontmatter; it takes a
  model alias/name and otherwise inherits the session model. (Note: Claude Code has merged
  custom commands into skills; `.claude/commands/foo.md` and a skill both create `/foo` and
  share the same frontmatter, including `model`.)
- The Task tool DOES support a per-spawn `model` parameter, but it is restricted to the
  hardcoded enum `["sonnet","opus","haiku"]` (custom aliases not supported — GitHub issue
  #34821, closed not-planned). The env var `CLAUDE_CODE_SUBAGENT_MODEL` overrides BOTH the
  per-invocation `model` parameter AND the agent's frontmatter `model` for all subagents.
- Anthropic explicitly endorses the orchestrator-worker pattern and "control costs by
  routing tasks to faster, cheaper models like Haiku." The official cost doc says: "For
  simple subagent tasks, specify `model: haiku`."
- Sub-agents are the primary token-efficiency lever: each runs in its own ~200K context
  window and returns only a summary, keeping the orchestrator context (and cost) small.

---

## 1. Per-sub-agent model

Yes. Sub-agents are Markdown files in `.claude/agents/` (project) or `~/.claude/agents/`
(user) with YAML frontmatter; only `name` and `description` are required. Supported fields
include `name`, `description`, `tools`, `model`, and `effort`.

Official doc text (code.claude.com sub-agents, "Choose a model"):
- `model` can be a model alias (`sonnet`, `opus`, `haiku`), a full model name ("Accepts the
  same values as the `--model` flag", e.g. `claude-opus-4-8`, `claude-sonnet-4-6`), or
  `'inherit'` to use the same model as the main conversation.
- **If omitted, it defaults to `inherit`** (uses the same model as the main conversation).
- The sub-agents doc explicitly lists "**Control costs** by routing tasks to faster,
  cheaper models like Haiku" as a benefit.

The model aliases themselves (from the model-config doc) currently resolve, on the
Anthropic API, as: `opus` → Opus 4.8, `sonnet` → Sonnet 4.6, `haiku` → Haiku 4.5; plus
`best` (most capable, = `opus`), `opusplan` (Opus in plan mode, Sonnet in execution),
`sonnet[1m]` / `opus[1m]` (1M-token context variants).

**Per-spawn override via the Task tool — YES, with hard limits.** When Claude spawns a
sub-agent via the Task tool, the call accepts `subagent_type`, `description`, `prompt`,
`run_in_background`, and an optional **`model`** parameter — but that parameter is a
hardcoded enum of exactly `["sonnet","opus","haiku"]` (GitHub issue anthropics/claude-code
#34821; closed as not planned). Custom/dated aliases passed there are not honored.

Subagent model resolution (per the official `CLAUDE_CODE_SUBAGENT_MODEL` docs):
1. **`CLAUDE_CODE_SUBAGENT_MODEL` env var — wins over everything.** Official text: it is
   "The model to use for all subagents and agent teams. Overrides the per-invocation
   `model` parameter and the subagent definition's `model` frontmatter. Set to `inherit`
   to use normal model resolution instead."
2. Otherwise: the Task-tool per-spawn `model` parameter / the agent's frontmatter `model`.
3. Otherwise: `inherit` (the main conversation's model).

(`ANTHROPIC_SMALL_FAST_MODEL` is deprecated in favor of `ANTHROPIC_DEFAULT_HAIKU_MODEL`,
which sets what the `haiku` alias and background functionality resolve to.)

**Implication for SDD:** Bake the tier into each agent file — a `test-runner` /
`commit-runner` with `model: haiku`, a `spec-author` / `planner` with `model: opus` (or
`sonnet`). This is the robust default because the Task `model` parameter only accepts the
three base aliases. Do NOT set `CLAUDE_CODE_SUBAGENT_MODEL` globally if you want
per-agent tiering — it overrides every agent's frontmatter and flattens all subagents to
one model (set it to `inherit` to keep normal resolution). Pin dated full model names in
frontmatter (e.g. `claude-haiku-4-5`) for reproducible automation, since aliases advance.

## 2. Per-slash-command model

Yes. Slash commands (`.claude/commands/*.md`, equivalently skills) support frontmatter:
`allowed-tools`, `argument-hint`, `description`, `model`, `disable-model-invocation` (and
`effort`). The `model` field takes a model alias/name; when omitted the command runs on the
current session model, and when set the command temporarily switches to that model for its
execution.

Relevant nuance from the docs: "**Custom commands have been merged into skills.** A file at
`.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create
`/deploy` and work the same way. Your existing `.claude/commands/` files keep working."

**Implication for SDD:** Each SDD step is a slash command, so you can pin a cheap model
directly on mechanical commands (move files / tick the todo / commit) with no sub-agent at
all. Important: when a slash command spawns a sub-agent via the Task tool, it is the
**sub-agent's** model (resolution in §1) that governs that work, not the command's
`model:`. Pin tiers in whichever layer actually does the token-heavy work.

## 3. Cheap models for cheap work (model tier ↔ task)

Anthropic explicitly endorses matching tier to task. Official guidance:

- Costs doc, "Choose the right model": "Sonnet handles most coding tasks well and costs
  less than Opus. Reserve Opus for complex architectural decisions or multi-step reasoning.
  ... **For simple subagent tasks, specify `model: haiku`.**"
- Sub-agents doc lists "**Control costs** by routing tasks to faster, cheaper models like
  Haiku" as a core benefit.
- Costs doc, "Manage agent team costs": agent teams use ~7x more tokens than standard
  sessions; "Use Sonnet for teammates ... Keep teams small."
- Claude Haiku 4.5 announcement: "Sonnet 4.5 can break down a complex problem into
  multi-step plans, then orchestrate a team of multiple Haiku 4.5s to complete subtasks in
  parallel." And: Haiku 4.5 gives "similar levels of coding performance but at one-third
  the cost and more than twice the speed" vs the prior Sonnet 4.
- Also relevant: **effort levels.** Use `low`/`medium` effort (`/effort`,
  `--effort`, or `effort:` in subagent/skill frontmatter) for mechanical steps to cut
  thinking-token spend; reserve `high`/`xhigh` for authoring/planning.

**Feasibility for the listed mechanical steps** — running a test suite, making a git
commit, ticking a checklist, moving files: all are well-scoped, low-reasoning, tool-driven
"worker" tasks and map exactly onto Anthropic's "simple subagent tasks → Haiku" guidance.

**Implication for SDD:**
- `model: haiku` (+ low/medium `effort`) for: test-runner, git-commit, todo-ticking,
  file-move / worktree-housekeeping steps (and the `/next` dispatcher if it's pure routing).
- `model: opus` or `sonnet` (high effort) for: spec_from_idea, plan_from_spec, spec_review,
  plan_security_review, plan_structure_review, improve_idea.
- Caveat: if a "mechanical" step must interpret ambiguous failures (e.g. decide how to
  react to a confusing test failure), keep that judgement on a stronger model and let Haiku
  only run-and-report.

## 4. Models / tiers currently available (mid 2026)

Latest tier (Models overview + model-config; Anthropic API resolution):

| Model | Alias resolves to | Full API ID | Input $/MTok | Output $/MTok | Latency | Context |
|-------|-------------------|-------------|--------------|---------------|---------|---------|
| **Opus** | `opus` → Opus 4.8 | `claude-opus-4-8` | $5 | $25 | Moderate | 1M |
| **Sonnet** | `sonnet` → Sonnet 4.6 | `claude-sonnet-4-6` | $3 | $15 | Fast | 1M |
| **Haiku** | `haiku` → Haiku 4.5 | `claude-haiku-4-5` (`-20251001`) | $1 | $5 | Fastest | 200K |

Profiles (official descriptions): Opus = "most capable model for complex reasoning and
agentic coding"; Sonnet 4.6 = "best combination of speed and intelligence"; Haiku 4.5 =
"fastest model with near-frontier intelligence." Opus 4.8 requires Claude Code v2.1.154+.

Relative cost (output dominates agent cost): Haiku 1x → Sonnet 3x → Opus 5x.
Relative speed: Haiku fastest → Sonnet fast → Opus moderate.

Provider note: on the Anthropic API `opus`=4.8/`sonnet`=4.6; on Claude Platform on AWS
`opus`=4.7; on Bedrock/Vertex/Foundry `opus`=4.6/`sonnet`=4.5 unless pinned. Legacy but
still available: Opus 4.7, 4.6, 4.5, 4.1; Sonnet 4.5. Aliases are recommended-version
pointers that move over time — pin full IDs for stable automation.

**Implication for SDD:** Output tokens dominate agent cost, so the biggest savings come
from (a) putting verbose/iterative steps on Haiku and (b) making every agent return short
structured output (§5). Pin dated/full model IDs in agent/command frontmatter so workflow
behavior doesn't drift when an alias rolls to a new version.

## 5. Token-efficiency techniques in Claude Code workflows

Drawn from the official "Manage costs effectively" (costs) doc, the sub-agents doc, and
Anthropic's "Effective context engineering for agents" post.

- **Delegate verbose ops to subagents (headline lever).** Costs doc: "Running tests,
  fetching documentation, or processing log files can consume significant context. Delegate
  these to subagents so the verbose output stays in the subagent's context while only a
  summary returns to your main conversation." Each subagent has its own ~200K context window
  and returns only its final summary — intermediate noise never touches the orchestrator.
- **Keep the orchestrator small / "right altitude".** Use just-in-time loading: pass
  lightweight identifiers (file paths, queries) and let each agent load content only when
  needed, rather than dumping large files into the parent context.
- **Avoid re-reading large files.** Costs doc recommends **code-intelligence plugins**
  (precise symbol navigation) so "go to definition" replaces grep-plus-reading multiple
  candidate files. Keep references, load on demand inside the worker that needs them.
- **Structured / compact outputs.** "Write specific prompts" — vague requests trigger broad
  scanning; specific requests minimize file reads. Have each step return a small structured
  result (status + path), which is both a context and an output-cost win.
- **Compaction & clearing.** Auto-compaction summarizes history near the context limit;
  `/compact <instructions>` (or CLAUDE.md compact instructions) controls what's preserved;
  `/clear` resets context between unrelated tasks. `/usage` and `/context` show what's
  consuming space.
- **Preprocess with hooks.** A PreToolUse hook can filter test output to only failures
  ("reducing context from tens of thousands of tokens to hundreds") before Claude sees it.
- **Trim base context.** Move detailed workflow instructions out of CLAUDE.md into skills
  (load on-demand); keep CLAUDE.md under ~200 lines. MCP tool defs are deferred by default
  (only names enter context until used); prefer CLI tools (gh, etc.) over MCP servers.
- **Tune extended thinking / effort.** Thinking tokens bill as output; lower `/effort`
  (low/medium) or `MAX_THINKING_TOKENS` for simple tasks to cut spend.
- **Prompt caching.** Claude Code uses prompt caching automatically to cut cost on repeated
  content (system prompt, tool defs). It rewards a stable prefix — keep early context
  constant and append new content at the end. Switching models or mutating early context
  invalidates the cache, so keep a given agent on one pinned model. (Can be toggled via
  `DISABLE_PROMPT_CACHING*` env vars.)
- **Agent-team cost warning.** Agent teams (separate Claude instances) cost ~7x a standard
  session in plan mode; subagents (single session, isolated context) are the cheaper
  context-isolation mechanism for SDD.

**Implications for SDD:**
- Make each SDD step a sub-agent that does its heavy lifting in isolation and writes its
  real output to a file (spec.md, plan.md, todo.md) while returning only a terse
  status/summary. The orchestrator (`/next`) stays tiny and cheap.
- Pass file paths between steps, not file contents. Don't have the orchestrator read full
  spec/plan files; let each worker read what it needs.
- Define a strict, short return contract per agent (e.g. "reply with PASS/FAIL + one-line
  reason + path written") to bound output tokens.
- For the test-runner step, consider a PreToolUse hook that filters pytest output to
  failures only — large savings on the most verbose step.
- Use todo.md as external memory/state so the orchestrator never holds the whole workflow
  history in context; `/clear` between unrelated specs.
- Pin one model per agent (don't flip mid-context) to preserve prompt-cache hits; prefer
  full/dated model IDs.
- Avoid setting `CLAUDE_CODE_SUBAGENT_MODEL` globally if you want per-step tiering (it
  overrides frontmatter for all subagents).

---

## References

- Create custom subagents — Claude Code Docs: https://code.claude.com/docs/en/sub-agents
- Slash commands — Claude Code Docs: https://code.claude.com/docs/en/slash-commands
- Extend Claude with skills (commands merged into skills) — https://code.claude.com/docs/en/skills
- Model configuration (aliases, /model, CLAUDE_CODE_SUBAGENT_MODEL, effort, prompt caching) — https://code.claude.com/docs/en/model-config
- Manage costs effectively (reduce token usage) — https://code.claude.com/docs/en/costs
- Settings / environment variables — https://code.claude.com/docs/en/settings and https://code.claude.com/docs/en/env-vars
- Agent teams — https://code.claude.com/docs/en/agent-teams
- Models overview (current + legacy IDs, pricing) — https://platform.claude.com/docs/en/about-claude/models/overview
- Pricing — https://platform.claude.com/docs/en/about-claude/pricing
- Effort — https://platform.claude.com/docs/en/build-with-claude/effort
- Context windows — https://platform.claude.com/docs/en/build-with-claude/context-windows
- How Claude Code uses prompt caching — https://code.claude.com/docs/en/prompt-caching
- Effective context engineering for agents — https://www.anthropic.com/engineering/effective-context-engineering-for-agents
- Claude Code best practices — https://www.anthropic.com/engineering/claude-code-best-practices
- Claude Haiku 4.5 announcement — https://www.anthropic.com/news/claude-haiku-4-5
- GitHub issue #34821 — custom model aliases for subagent spawning via Task tool (closed not-planned): https://github.com/anthropics/claude-code/issues/34821
- GitHub issue #10993 — CLAUDE_CODE_SUBAGENT_MODEL behavior clarification: https://github.com/anthropics/claude-code/issues/10993
