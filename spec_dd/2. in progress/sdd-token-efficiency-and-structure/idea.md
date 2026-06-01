# Idea: Make the SDD workflow more token-efficient and structurally sound

## Goal

Review the whole SDD workflow (the `fls-claude-plugin/commands/sdd/` commands and helpers) and make it
**more token-efficient, faster, and more robust** — without changing what the workflow produces.

This round is a **focused tune-up**, not a re-architecture. A larger re-architecture (e.g. migrating
commands to skills, rethinking the fresh-agent-per-step orchestration) is captured as a **separate
follow-up idea** to be written later.

## Background: what the research changed

Four research docs in this directory (`research_subagent_capabilities.md`, `research_model_selection.md`,
`research_cc_features.md`, `research_resilience_patterns.md`) verified current Claude Code behaviour
against the live docs. Several assumptions baked into today's workflow are now outdated or wrong:

- **Subagents *can* use skills** — auto-triggered, no special permission, and skills can be *preloaded*
  via a `skills:` frontmatter field. (The original idea asked this; the answer is yes.)
- **Custom commands have largely merged into skills.** Subagents can invoke **skills** (via the `Skill`
  tool) but still **cannot type slash commands**. The robust way for a subagent to run reusable workflow
  logic is therefore a skill, not a slash command. *(Whether to actually migrate is deferred to the
  spec phase — see Decisions.)*
- **Subagents cannot spawn subagents (nesting is blocked).** Fan-out must happen on the main thread.
- **Input to a subagent is spawn-time only.** There is no mid-run messaging in standard subagents
  (experimental "Agent Teams" `SendMessage` exists but is gated and out of scope here).
- **Model is controllable per step** — per-agent `model:` frontmatter (`haiku`/`sonnet`/`opus`/`inherit`),
  per-command `model:`, and the `CLAUDE_CODE_SUBAGENT_MODEL` env var. Haiku 4.5 is explicitly recommended
  for mechanical work (optionally with `effort: low`); Sonnet 4.6 / Opus 4.8 for reasoning-heavy work.

## Problems to address (in scope)

### 1. Instructions that ask for the impossible (the nesting bug)
Because subagents can't nest, only **one** level of fan-out exists (main thread → subagent). Today that
single level is consumed by the wrong thing: `next.md` runs each `(cmd)` step inside a **fresh subagent**,
so when that command (`spec_from_idea.md` Step 1, `plan_from_spec.md` Steps 4 & 6) tries to "create
subagents to…", it's already at depth 1 and the fan-out silently can't run.

**Fix (chosen): run commands on the main thread.** `next.md` stops spawning a subagent wrapper for
`(cmd)` steps and instead runs the next command **at depth 0** (on the main thread). Clean context — the
original reason for the wrapper — becomes the user's responsibility: **`/clear` before each `/sdd:next`**.
With every command running at depth 0, its own research/review fan-out is legal and works. This also
removes the `Agent` tool dependency and the "fresh agent per command" rationale from `next.md`.

Then audit every command for any remaining instruction the executing context can't perform (a subagent
typing a slash command, a subagent asking the user a question) and move those to the orchestrator/main
thread too.

### 2. Model tiering for speed and cost
Assign the right model tier per step, with sensible defaults that remain **overridable**:
- **Haiku** — mechanical steps: running tests, making commits, moving files, ticking the todo list,
  worktree/todo setup helpers.
- **Sonnet** — reviews and research.
- **Opus / inherit** — spec authoring, plan authoring, security reasoning.
Decide the mechanism in the spec (per-agent frontmatter vs per-command vs env var), favouring one that is
portable and easy to override.

### 3. Batch fragility — one failure shouldn't restart the batch
Where the workflow fans out work (parallel research, multi-dimension review), make it resilient:
spawn **one subagent per unit** (not one per batch), have each unit **write its own output file** so
completed units survive a sibling's failure, treat **resume as "skip units whose output already exists"**,
have units return a **structured pass/fail/blocked** result, and **retry only the failed units**.

### 4. Subagents that need user input they can't get mid-run
Adopt an **input-contract + re-spawn** pattern using only stable features:
- Each phase declares, up front, what user input it needs.
- The **orchestrator** gathers that input (e.g. via `AskUserQuestion`) **before** spawning, and bakes it
  into the subagent prompt.
- If a subagent still discovers it needs something, it returns a structured **`blocked: needs X`** result
  instead of stalling; the orchestrator collects X and re-spawns.

### 5. Token hygiene
- Trim padding and duplicated lines from command/helper files (they're paid for every time a file is
  read or inlined into a subagent prompt).
- Keep hand-offs compact: phases communicate through on-disk artifacts (idea/spec/plan/research/todo)
  plus a short return summary, not by dumping file contents into the orchestrator's context.
- Prefer file paths over file contents; don't re-read files just to "verify".

### 6. Correctness clean-ups surfaced along the way
- `/implement` referenced by an older path vs the actual `implement_plan.md` — reconcile naming so the
  checklist and command files agree.
- Make sure every "(cmd)" item in the generated `todo.md` maps to a command file that exists.

## Decisions taken (from review)

- **Scope:** focused tune-up now; full re-architecture (incl. any commands→skills migration) is a
  **separate later idea**.
- **Orchestration / nesting fix:** `next.md` runs `(cmd)` steps on the **main thread (depth 0)**, with no
  subagent wrapper. The user runs `/clear` before each `/sdd:next` to keep context clean. This frees the
  single nesting level for each command's own fan-out. (Simpler than tagging leaf vs. orchestrating
  commands — there's no wrapper, so the distinction isn't needed.)
- **Commands vs skills:** do **not** migrate in this round. Note the merger as the key option and decide
  concretely in the spec, after confirming behaviour on the pinned Claude Code version. The impossible
  instructions (problem 1) are still fixed now, by moving fan-out to the main thread.
- **Model tiering:** tiered defaults (Haiku / Sonnet / Opus-or-inherit) that are **configurable/overridable**.
- **Mid-run input:** input-contract + re-spawn, **stable features only** (no experimental Agent Teams).

## Out of scope

- Migrating commands to skills (deferred to the follow-up idea).
- Experimental Agent Teams / `SendMessage` / resumable live subagents.
- Changing the *outputs* of the workflow (spec/plan/QA artifacts) or the user-facing step sequence.

## Open questions for the spec phase

- Exact model-selection mechanism and where the override knob lives.
- Whether to confirm the Claude Code version/features the plugin should target (so we don't depend on
  behaviour that varies by version).
- Per-command audit: the full list of "impossible instruction" sites and how each is reworked.

## Success criteria

- No command instructs its executing context to do something it cannot (no nested-subagent asks, no
  subagent-typing-slash-commands, no subagent asking the user).
- Mechanical steps run on a cheaper/faster model by default, with a documented override.
- A single failed unit in a fan-out no longer forces the whole batch to restart.
- Subagents have the inputs they need at spawn time, or fail fast with a structured "needs X".
- Measurably less token overhead per run (trimmed command files, compact hand-offs) with no loss of
  workflow output quality.
