# Research: established best practices for chaining SDD commands

Sources are cited inline. Terms from other systems are attributed. "Applies here" lines refer to the SDD plugin (`claude_plugins/sdd`), whose constraints are already adopted in `claude-code-authoring` (no subagent nesting, `AskUserQuestion` orchestrator-only, file-based hand-off, resume via `status:` footers).

One correction to note first: the current Claude Code subagent docs say subagents CAN nest up to three layers by default (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, 1 disables nesting). The project's "no nesting" rule is therefore a deliberate design choice (and a safe one), no longer a platform fact. The skill's statement "the `Agent` tool is not exposed at depth 1" may be stale for current Claude Code. Worth flagging to whoever owns `claude-code-authoring`.

## 1. Chaining long pipeline steps

Practices:
- Prompt chaining with gates: split into sequential steps, each consuming the previous output, with programmatic checks ("gates") between steps. Trades latency for accuracy. (Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents)
- Persist plan and phase state externally; summarize finished phases; resume from the last good state rather than restarting; combine deterministic retries/checkpoints with agent adaptation. (Anthropic, multi-agent research system: https://www.anthropic.com/engineering/built-multi-agent-research-system)
- One durable artifact per stage with a completeness marker, so each stage is idempotent (re-running skips or cleanly overwrites).
- Explicit stop contract: the chain ends on completion or on a defined limit/blocker, not silently. (Building effective agents: stopping conditions and human checkpoints on blockers.)
- A chained step must stay runnable alone: the same input contract (paths, flags) whether called by the user or by the chain.

Applies here:
- Gates = the `status: ok|failed|blocked` footer plus the existing todo ticks: YES, already the project's contract; the chain should read the footer of each stage's artifact before proceeding.
- One artifact per stage: YES (`design`, `spec`, `plan`, QA report each have a fixed file).
- "Stop here if X": YES, define it as: stop the chain (and report) on `blocked`/`failed` after the retry budget, or when a stage needs a human decision that was not collected up front.
- Standalone-runnable: YES, the existing `mode: hook` input (inline-read command with `<spec-dir>`, `<todo-path>`) is exactly this pattern: hook mode skips rebase/todo tick; standalone does not. Reuse it rather than inventing a new one.

## 2. Front-loading human input in unattended runs

Practices:
- Autonomous/headless runs cannot ask: `claude -p` denies anything needing approval in Manual mode; with `--permission-prompts none` `AskUserQuestion` is removed from the tool set entirely; in `dontAsk` mode it is denied. Scheduled-task guidance: "be explicit about what success looks like"; the task cannot ask clarifying questions. (https://code.claude.com/docs/en/headless, https://code.claude.com/docs/en/common-workflows)
- Plan then execute: plan mode lets Claude read and propose with no edits until approved, so the human decision happens once, up front. (https://code.claude.com/docs/en/common-workflows#plan-before-editing)
- Subagents cannot use `AskUserQuestion` (removed from their tools); a subagent needing input must finish or report back and the main conversation asks. (https://code.claude.com/docs/en/sub-agents)
- Human checkpoints only at blockers or genuine decision points; otherwise proceed. (Building effective agents.)
- Question hygiene (general practice): batch all questions into one round, ask only what research/code cannot answer, give each a recommended default, and record any deferred or defaulted decision in an artifact so it is reviewable afterwards.

Applies here:
- Batch once at depth 0 at the start of `/sdd:start`: YES. Collect the union of questions the chained steps would ask (design registration, spec questions) in one `AskUserQuestion` round, then pass answers into the stage inputs. Already the fan-out recipe step 1.
- Ask once with a default: YES. For questions only discoverable mid-chain, proceed on the stated default.
- Record deferred/defaulted questions: YES, in an "Assumptions and open questions" section of the spec so the existing spec review can catch them. The idea says "so that nothing gets stored" (likely: nothing half-asked left dangling); a defaults log serves that.
- Pause vs proceed rule: pause only when the answer changes the spec's direction or is destructive/irreversible; proceed with a recorded default otherwise.
- Do NOT rely on `-p`/`--permission-prompts none`: the SDD commands are interactive slash commands, and this plugin runs at depth 0 in an interactive session; those flags are only relevant if someone scripts the chain headlessly (then `AskUserQuestion` is unavailable and all inputs must be pre-supplied).

## 3. Context protection via subagents

Practices:
- Each subagent has its own context window; verbose output (searches, logs, file reads) stays there and only a summary returns. A non-fork subagent starts fresh with only its prompt, CLAUDE.md and a git snapshot. (https://code.claude.com/docs/en/sub-agents)
- Many subagents returning detailed results can still consume significant context; the docs give no result-size limit in the portion read. So keep returns to one line and put detail in files.
- Subagents spawned from the main conversation run in the background by default; results arrive as a completion notification in a later turn; background subagents get a smaller tool set and permission prompts surface in the main session. In `claude -p`, the run stays open until background subagents finish. (sub-agents and headless docs)
- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` defaults to 20.
- Subagents store work in external systems and return lightweight references, avoiding lossy relay and token overhead; vague task descriptions cause duplicated work, so give each worker an objective, output format, tool guidance and boundaries; scale effort to task size; token cost is roughly 15x chat for multi-agent runs. (https://www.anthropic.com/engineering/built-multi-agent-research-system)
- Model tiering: cheap models for mechanical chores, stronger for synthesis.
- Delegate exploration so "only the findings come back". (https://code.claude.com/docs/en/common-workflows#delegate-research-to-subagents)

Applies here:
- File-based hand-off with one-line returns: YES, already adopted (`status=… path=… reason=…`).
- Tiering via spawnable agent files (`sdd-mechanic` Haiku, `sdd-worker` Sonnet): YES, already adopted; note inlined commands keep the caller's model.
- Effort scaling: YES, do not spawn a worker for a trivial step (e.g. a design registration that is a few file moves); spawn only where output volume or independence justifies it.
- Same-turn parallel spawns: YES for independent units; for chain steps that depend on each other (design registration before spec), run sequentially.
- Research caveat: Anthropic notes tightly coupled work, "most coding tasks", is a poor fit for heavy multi-agent parallelism. Relevant to section 4.

## 4. Parallel coding with git worktrees

Practices (Claude Code docs, https://code.claude.com/docs/en/worktrees, https://code.claude.com/docs/en/sub-agents):
- `isolation: worktree` in agent frontmatter (or asking Claude to "use worktrees for your agents") runs each subagent in a temporary worktree; removed automatically if the subagent made no changes, otherwise kept until a periodic sweep (`cleanupPeriodDays`) can remove it without losing work. Worktrees are locked while the agent runs.
- Base branch: by default new worktrees (including subagent worktrees) branch from the repository's DEFAULT branch on the remote (`worktree.baseRef: "fresh"`), NOT the current HEAD. Set `worktree.baseRef` to `"head"` to branch from the current local HEAD so the worktree carries unpushed commits and in-progress feature-branch state. This is the critical gotcha for slice workers in a feature branch like this one.
- A worktree is a fresh checkout: install dependencies and set up environment there; gitignored files (`.env`) are copied only if listed in `.worktreeinclude` (also applies to subagent worktrees).
- Shared with the main checkout: the `.git` directory (so commits work from a worktree and branches/commits are visible to the main checkout), project-scope plugins, permission approvals saved to the main checkout's `.claude/settings.local.json`, untracked skills/agents/commands read-through.
- A subagent in its own worktree takes its instruction files from the main conversation, not from the worktree; for worktrees under `.claude/worktrees/` it does not load the worktree-root `CLAUDE.md` or `.claude/rules/`.
- Isolation enforcement blocks edits/commands/git redirects targeting the main checkout, but does NOT track files written by shell commands like `cp` or redirects.
- Manual route: `git worktree add ../x -b branch`, `git worktree list`, `git worktree remove`; `claude -p` worktrees are not auto-cleaned and need `git worktree remove` (and `unlock` if locked).
- Partitioning to avoid conflicts (general practice, supported by Anthropic's caution that coding is tightly coupled): assign disjoint file ownership per slice, order slices by dependency (migrations/models before views/templates), give shared files (urls, settings, migrations, `__init__`, lockfiles, docs index) to exactly one owner or to the integrator, and keep slices small and vertical.
- Integration (general practice): each slice commits on its own branch; the orchestrator merges or rebases slice branches onto the feature branch one at a time in dependency order, runs the full test suite after every merge (or at least after the last), and resolves conflicts at depth 0. Migrations are the classic collision (two slices creating the same migration number): serialize or regenerate migrations in the integration step.
- Per-worktree resources (general practice): a separate database (e.g. a database name suffix per worktree so tests do not collide on one PostgreSQL test database), distinct dev-server ports, own virtualenv or `uv sync`, and copied env files.

Applies here:
- Worktrees for slices: CONDITIONALLY. Only worth it when a plan has 2+ slices with provably disjoint file sets and no migration overlap. Otherwise sequential in-tree is cheaper, less risky, and avoids the research system's noted weakness for tightly coupled coding. Make it opt-in per plan (the plan declares slices and owned paths), with a sequential fallback.
- Branch from HEAD: MUST configure `worktree.baseRef: "head"` (or create with `git worktree add -b` from the feature branch) because default is the remote default branch, which would miss the project's unmerged work; the FLS repo already uses long-lived worktrees named after the spec, so the "slice worktree" name must not clash with the spec worktree.
- Agent nesting: a coding subagent that itself fans out is out of scope; the integrator runs at depth 0.
- Per-worktree resources: needs `uv sync`, `.env` copy (`.worktreeinclude`), PostgreSQL 17 test database naming, and Tailwind build only if the slice touches templates. These must be written into the slice worker's prompt.
- CLAUDE.md git rules: commits use `uv run git commit`, pre-commit hooks apply in slice worktrees too; keep worktree-local commit authority, but pushing stays with the orchestrator.
- Cleanup: remove slice worktrees and branches after merge; because `-p`/unmerged-change worktrees are not auto-removed, the orchestrator removes them by name (same discipline as "delete scratch files by name" in the fan-out recipe).

## 5. QA immediately after implementation, independently re-runnable

Practices:
- Automated tests give ground truth coding agents can iterate on; always gather ground truth from the environment, and keep human review for fit with broader requirements. (Building effective agents)
- Chain by calling QA as a hook of implement (not a separate state), with its own artifact; QA reads the spec/plan from disk, not from implementer conversation, so it is stateless and re-runnable. Verification criteria (test command, expected results) belong in the plan so both runs use the same check. (https://code.claude.com/docs/en/best-practices on giving Claude a check to run)
- Reviewer separate from the writer: independent verification context catches what the implementer missed (writer/reviewer pattern in the best-practices page).
- Idempotent QA: each run writes a fresh dated or overwritten report with a status footer; a second run after code changes replaces it.

Applies here:
- Run QA as a hook at the end of `/sdd:implement_plan` using `mode: hook`, with `/sdd:qa` (standalone) remaining a normal command: YES.
- QA fan-out (independent checks in parallel subagents, each its own output file): YES, consistent with the fan-out recipe.
- QA must not depend on implementer context: YES, pass only paths.
- Stop rule: a failing QA does not auto-trigger more implementation by default; report and stop (bounded loops only if explicitly requested, per the "limits on iterations" guidance).

## Other chain candidates (idea item 3)

Pattern-based suggestions, not researched sources: any step whose preconditions are met by the previous artifact and that needs no new human decision can chain (for example spec review after spec writing, plan review after plan writing), provided each keeps a human approval gate where the project requires it and the batched-questions rule above holds. Approval gates that exist for human sign-off should stay gates.

## Reference URLs

- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/worktrees
- https://code.claude.com/docs/en/common-workflows
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/best-practices
- https://www.anthropic.com/engineering/building-effective-agents
- https://www.anthropic.com/engineering/built-multi-agent-research-system

Not read: `resources/fanout_recipe.md` (the skill summary was used instead); the best-practices page was only skimmed via its intro.

status: ok · reason: web-sourced practices gathered with URLs; one stale constraint (subagent nesting) flagged
