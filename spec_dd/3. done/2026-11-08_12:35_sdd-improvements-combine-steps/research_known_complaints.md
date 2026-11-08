# Research: known complaints (chained commands, front-loaded questions, parallel subagents, worktrees, implement-then-QA)

Method: web searches only. Several sources are vendor or blog posts and secondhand; marked "anecdotal" where so. I did not re-read `implement_plan.md` or `do_qa.md` line by line. The "Prevent" lines name the `claude_plugins/sdd/` files a spec would constrain, based on the file list and `claude-code-authoring/SKILL.md`.

## 1. Long autonomous chains

| # | Symptom | Usual cause | Prevent (spec constraint) |
|---|---|---|---|
| 1.1 | After auto-compaction the agent forgets the plan and earlier decisions, and drifts. | Compaction summarises 100K+ tokens into a few K. Early decisions are the most at risk. A plan that lives only in chat is lost. Plan-mode plans were reported lost after compact (anthropics/claude-code #24686). | Every stage hands off through files (spec, plan, todo), never chat. Each command must re-read its inputs from disk on entry. Constrains `commands/start.md`, `implement_plan.md`, `commands/README.md`. |
| 1.2 | Run silently stops, e.g. auto-compact does not fire and the CLI halts (#66144). | Context ceiling. Chaining 5+ stages in one session raises the odds. | Chain with an on-disk progress marker (the todo tick) so a re-run resumes. Document that a chain can be re-invoked. Constrains `start.md`, `implement_plan.md`. |
| 1.3 | Agent claims "done, tests pass" and it is not true. A 2026 survey reports about 1 in 11 such claims failed re-verification (anecdotal). | Self-report bias. The agent that wrote the code also writes the tests and judges them. | Final status comes from a file artifact with a `status:` footer written by a separate worker or run, not the orchestrator's prose. Constrains `do_qa.md`, `implement_plan.md`, `agents/sdd-worker.md`. |
| 1.4 | Cost blow-up. | Each extra stage and each parallel worker adds tokens. Subagent sessions draw on the same plan quota. | Use Haiku for mechanical chores and Sonnet for fan-out (existing tiering). The spec should state the maximum fan-out width per command. Constrains `resources/model_tiering.md`, `fanout_recipe.md`. |
| 1.5 | A wrong early assumption (from idea or design) propagates through spec, plan, code and QA. | No human gate between stages once chained. | Keep one gate, a cheap review, between spec and plan (`spec_review`). The chain must stop on `blocked` or `failed`, never skip past it. Constrains `start.md`, `spec_from_idea.md`, `spec_review.md`. |

## 2. Front-loaded question batches

| # | Symptom | Usual cause | Prevent |
|---|---|---|---|
| 2.1 | `AskUserQuestion` inside a subagent fails or vanishes. It is unavailable to subagents (#12890, #40263, #34592, #18721), and the docs conflict on foreground pass-through. | Tool is filtered out at spawn. | Already recorded in `claude-code-authoring/SKILL.md`. The spec must require workers to return `blocked` plus `needs`, and the orchestrator asks. Do not rely on pass-through. Constrains `agents/sdd-worker.md`, `register_design.md`, `spec_from_idea.md`. |
| 2.2 | Too many questions up front. The user cannot answer some yet because they depend on research or earlier answers. | Collecting questions from several commands before any work has run. | Ask only what research cannot answer. Start work first and ask in one batch while workers run (matches recipe step 1). Dependent questions are deferred, not guessed. Constrains `fanout_recipe.md`, `spec_from_idea.md`. |
| 2.3 | Bad defaults are chosen silently, or the user walks away and the prompt waits. | Pre-answered or timed defaults hide the decision. | Record every defaulted answer in the spec as an explicit "assumed" line the reviewer sees. Cap questions to one batch, so the user is not interrupted mid-run. Constrains `spec_from_idea.md`, `writing_standard.md`. |
| 2.4 | Pre-gathered answers are lost ("so that nothing gets stored" in the idea). | Answers held in orchestrator context only. | Write answers to a named scratch file under `.sdd-work/` so the hooked commands and a resumed run both read them. Constrains `start.md`, `register_design.md`. |

## 3. Parallel subagents

| # | Symptom | Usual cause | Prevent |
|---|---|---|---|
| 3.1 | Results truncated or detail lost when returned. I found no direct source. This is inferred from the context-isolation design. | The parent only gets the child's final message. | Existing recipe returns paths, not contents. Keep it. Constrains `fanout_recipe.md`. |
| 3.2 | Duplicated work, or workers cannot see each other's files. | Each worker has its own context and spawn-time prompt only. Mid-run messaging is unsupported. | One unit per worker with disjoint output paths, and the plan split by file ownership before fan-out. Constrains `implement_plan.md`. |
| 3.3 | Rate limits and quota burn. One user reported hitting the Pro limit in about 15 minutes after five unrequested parallel sessions (dev.to onlineeric). Ten parallel agents use quota ten times faster (cloudzero, secondhand). | N workers equals N times the token rate, and provider limits bound throughput. | Cap parallel width. On a rate-limit failure, retry the unit (existing `failed` rule), not the whole batch. Constrains `fanout_recipe.md`. |
| 3.4 | Model tier mismatch. A helper expected to run on Haiku runs on the caller's model, or `CLAUDE_CODE_SUBAGENT_MODEL` flattens everything. | An inlined file's `model:` is inert, and the env var overrides all. | Already documented. New chained steps must be spawnable agent files if they need their own tier. Constrains `agents/*.md`, `model_tiering.md`. |

## 4. Git worktrees for parallel agents

| # | Symptom | Usual cause | Prevent |
|---|---|---|---|
| 4.1 | Merge conflicts when branches rejoin. | Tasks touch the same files. | Allow parallel coding only for plan steps with disjoint file sets. Merge one at a time, rebasing each onto the updated base. Constrains `implement_plan.md`. |
| 4.2 | Lockfile churn (`uv.lock`, `package-lock.json`). | Each worktree resolves dependencies independently. | Workers never add dependencies. The orchestrator owns lockfile changes (inference). Constrains `implement_plan.md`. |
| 4.3 | Two worktrees create migrations with the same number. | Parallel `makemigrations` against the same app. | Only one worker per app touches models and migrations, or the orchestrator makes migrations serially after the merge (inference from Django behaviour). Constrains `implement_plan.md`, `plan_from_spec.md`. |
| 4.4 | Shared dev database and ports. Files are isolated but runtime is not. A schema change in one worktree lands in the shared DB. Dev servers fight over a port (upsun, mindstudio, fast.io posts). | Worktrees isolate code, not runtime. | Per-worktree database and port in the worktree's env. Short-lived workers should not run migrations against the shared DB. Constrains `start.md` (setup) and any new worker-worktree step. |
| 4.5 | `.gitignore`d files (`.env`, `.venv`, `node_modules`) are missing in the new worktree. Symlinking `node_modules` breaks when dependencies differ. | Git does not carry ignored files. | Reuse the existing `start.md` setup routine. Copy a template for `.env` and do not symlink credentials. Constrains `start.md`. |
| 4.6 | Per-worktree install time cancels the speed-up. Pre-commit hooks slow every worker. | Full install and hooks per worktree. | Worker worktrees commit with hooks deferred and the orchestrator runs hooks once at merge. This conflicts with the project's `uv run git commit` rule, so the spec must decide it explicitly. Constrains `resources/commit_and_push.md`. |
| 4.7 | Forgotten worktrees and branches. | A crash before cleanup. | Name them by a fixed pattern, list and prune them on resume, and have `finish_worktree.md` remove stragglers. Constrains `finish_worktree.md`, `implement_plan.md`. |

## 5. Implement then immediately QA

| # | Symptom | Usual cause | Prevent |
|---|---|---|---|
| 5.1 | QA runs against a stale server or DB. I found no direct source. | Code changed, server not restarted or migrated. | `do_qa.md` must start by migrating and restarting from the current tree, or fail with `blocked`. |
| 5.2 | QA finds bugs the implementation should have caught. 2026 write-ups cite a case where an agent implemented a feature, wrote its own tests and reported pass, then QA found a wrong calculation (towardsai). | Same agent wrote the code and the tests. | QA is a separate worker with its own context. The implementer must run the plan's own checks first. Constrains `do_qa.md`, `implement_plan.md`. |
| 5.3 | QA reports nobody reads. | Report is written to a file and the chain ends. | The chain's closing message must surface the report path and counts. A failing QA must not read as success. Constrains `implement_plan.md`. |
| 5.4 | QA cannot be re-run in isolation. | Chained step depends on in-memory state from implement. | `do_qa.md` reads only on-disk inputs (spec, plan, todo), and `implement_plan` calls it as a hook with `mode: hook`. Standalone use stays valid. Constrains `do_qa.md`. |

## 6. Chained commands

| # | Symptom | Usual cause | Prevent |
|---|---|---|---|
| 6.1 | A chained command cannot be run on its own. | It assumes inputs only the caller has. | Every hookable command opens with "Inputs from the caller" and works without `mode: hook`. This is already the convention in `claude-code-authoring/SKILL.md`. Constrains `start.md`, `register_design.md`, `spec_from_idea.md`. |
| 6.2 | A re-run repeats work already done (re-registers a design, regenerates a spec, duplicates commits). | No completion marker. | Each step checks its own output for `status: ok` and skips (recipe step 3). Todo ticks are the markers. Constrains `fanout_recipe.md`, `start.md`. |
| 6.3 | A subagent cannot invoke a slash command, so a chain built from slash commands breaks inside workers. | There is no `SlashCommand` tool at depth 1. | Chain at depth 0 by reading and following helper files, not by invoking `/commands` inside workers. Constrains `start.md`. |

## Sources
- https://claudeissues.com/issue/12890-bug-askuserquestion-tool-not-available-to-subagents-regardless-of-configuration
- https://claudeissues.com/issue/40263-foreground-subagent-askuserquestion-pass-through-does-not-work-tool-not-availabl
- https://claudeissues.com/issue/34592-askuserquestion-unavailable-in-all-sub-agent-contexts-despite-docs-stating-foreg
- https://claudeissues.com/issue/18721-docs-missing-warning-and-workflow-guidance-for-askuserquestion-limitation-in-sub
- https://claudeissues.com/issue/24686-bug-plans-made-in-plan-mode-are-lost-after-compacting-context
- https://claudeissues.com/issue/66144-bug-auto-compact-does-not-trigger-at-100-context-window-and-claude-code-stops-it
- https://www.mindstudio.ai/blog/claude-code-compact-command-context-management
- https://dev.to/onlineeric/claude-code-sub-agents-burn-out-your-tokens-4cd8
- https://cloudzero.com/blog/claude-code-agents/
- https://www.verdent.ai/zh-CN/guides/claude/code-subagents
- https://developer.upsun.com/posts/ai/git-worktrees-for-parallel-ai-coding-agents
- https://fast.io/resources/cline-git-worktrees-parallel-agents/
- https://www.mindstudio.ai/blog/parallel-ai-coding-agents-git-worktrees
- https://redreamality.com/blog/coding-agent-done-claims-verification-survey/
- https://pub.towardsai.net/your-ai-agent-wrote-the-code-and-the-tests-who-checked-the-requirement-002998e55c60

status: ok · reason: web-sourced for 1, 2, 3 (cost), 4 and 5.2; 3.1, 4.2, 4.3 and 5.1 are marked inference or unsourced
