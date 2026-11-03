# Research: reference implementations

Question: how do reference implementations solve chained commands, front-loaded questions, parallel subagents and short-lived worktrees for parallel coding?

Each section gives mechanism, strengths, what breaks, and a verdict for a Markdown-driven Claude Code plugin (the SDD plugin) with a no-nesting rule for subagents. Items I could not verify from primary sources are marked UNVERIFIED.

Local baseline (read from the repo):
- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md` says: no nesting or fan-out from a subagent (the `Agent` tool is not exposed at depth 1), subagents can't type slash commands (prefer skills or "read-and-follow this helper file"), and `AskUserQuestion` is orchestrator-only.
- `claude_plugins/sdd/commands/README.md` says every artifact command commits and pushes via `sdd:sdd-mechanic`, and fan-out uses `sdd:sdd-worker`.

## Key finding: the no-nesting rule is stricter than current docs

The official subagent docs (https://code.claude.com/docs/en/sub-agents) say a subagent can spawn subagents "up to three layers below the main conversation". `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` changes the limit: `1` turns nesting off, and at the limit the `Agent` tool is removed from subagents. The plugin's no-nesting rule is therefore a choice that holds on a depth-1 setup. It is not a platform guarantee, and the authoring skill's wording ("not exposed at depth 1") may be out of date. It should be re-verified before the spec relies on it. Designing to the stricter rule stays safe on either behaviour.

## 1. Claude Code itself

Sources:
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/worktrees
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/agent-teams
- https://code.claude.com/docs/en/common-workflows

### 1a. Subagents, background and worktree isolation
- **Mechanism.** The main session spawns subagents with the `Agent` tool.
  - A subagent spawned from the main conversation starts in the background by default.
  - Results arrive as a completion notification in a later turn. `CLAUDE_CODE_FORK_SUBAGENT=0` makes Claude wait instead.
  - Background subagents get a reduced built-in tool set (`Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write` and a few others) plus all MCP tools.
  - The default concurrency cap is 20 (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`).
  - Frontmatter `isolation: worktree`, or "use worktrees for your agents", gives each subagent a temporary worktree. It is removed automatically if the subagent made no changes. A worktree with changes stays on disk until a periodic sweep (`cleanupPeriodDays`) can remove it safely.
- **Good at.** Context protection, since only a summary returns. Cheap parallel research. Conflict-free parallel edits when the slices touch disjoint files.
- **What breaks.**
  - A worktree subagent branches from the repository default branch on the remote (`worktree.baseRef: "fresh"`), not the parent session's `HEAD`. A plan slice that depends on unpushed or in-progress commits on the feature branch needs `worktree.baseRef: "head"`. That setting is global, so it would have to go in the project settings or the plugin docs.
  - A fresh worktree has no installed dependencies and no gitignored files. `.worktreeinclude` copies matching gitignored files, for example `.env`. It does not run `uv sync`, migrations or a database setup. Per-worktree setup is the caller's job.
  - A subagent in its own worktree takes its `CLAUDE.md` and rules from the main conversation, not from the worktree.
  - Commits made in a subagent worktree land on a separate branch. Merging is up to the orchestrator, and Claude Code gives no merge help.
  - Claude Code blocks writes and git commands that resolve to the main checkout, so the orchestrator must read results via the branch, not by the subagent writing into the main tree.
- **Verdict.** Fits. It is the only native route to parallel coding without hand-rolled `git worktree add`, but the base-branch default and the missing environment setup need explicit handling (use `baseRef: "head"` or create the worktrees by hand).

### 1b. `claude --worktree`, `EnterWorktree` and `ExitWorktree`
- **Mechanism.**
  - `claude --worktree <name>` creates `.claude/worktrees/<name>/` on a new branch `worktree-<name>` and starts the session there.
  - Mid-session, the `EnterWorktree` tool creates a worktree or switches to an existing one under `.claude/worktrees/`. Entering a path outside that directory prompts for approval. `ExitWorktree` leaves it.
  - A clean worktree is removed on exit. A worktree with work prompts the user (interactive) or is left in place with its lock (`-p`).
  - Resume returns the session to its worktree.
- **Good at.** Isolating a whole SDD run, which is the project's existing `/sdd:start` worktree model.
- **What breaks.**
  - `EnterWorktree` and `ExitWorktree` are session-level tools. They move the working directory of the whole session and do not give an orchestrator several worktrees at once.
  - A worktree created by hand with `git worktree add` under the project directory is also supported. Claude Code reads untracked skills, agents and commands from the main checkout when the worktree has no `.claude/skills`.
  - Permission approvals for Bash are saved to the main checkout and shared, which is helpful for parallel slices.
  - `permissions.blockWritesOutsideWorkingDirectories` removes the worktree tools.
- **Verdict.** `--worktree` is already the model `/sdd:start` uses. `EnterWorktree` is not the parallelism primitive.

### 1c. Agent teams (experimental)
- **Mechanism.** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` enables a team lead plus teammates. Each teammate is a full session with its own context. They share a task list with pending, in progress and completed states and dependency blocking. File locking prevents double-claiming. A mailbox JSON file per agent carries messages. `TeammateIdle`, `TaskCreated` and `TaskCompleted` hooks gate quality.
- **Good at.** Review and research with debate. Cross-layer work with disjoint file ownership.
- **What breaks.**
  - Experimental. No nested teams.
  - No session resumption with in-process teammates.
  - Task status lags.
  - Spawning requires an interactive session and does not work with `-p`.
  - Higher token cost.
  - Two teammates editing the same file overwrite each other, so file ownership must be partitioned by hand.
- **Verdict.** Does not fit. It is experimental and off by default, and the plugin can't enable it for users.

### 1d. Command chaining and the `Skill` tool
- **Mechanism.** Commands are merged into skills: `.claude/commands/x.md` and `.claude/skills/x/SKILL.md` both create `/x`. Plugin skills are namespaced `/plugin:skill`. Claude invokes skills through the `Skill` tool, subject to `Skill(name)` permission rules.
  - `disable-model-invocation: true` blocks a model-initiated call and also blocks preloading into subagents. The tool call is refused and Claude is told not to reproduce the steps another way.
  - `user-invocable: false` still lets Claude call it.
  - A skill can set `context: fork` (with `agent:`) to run in a forked subagent. It runs in the background by default, `background: false` waits, and non-interactive mode always waits.
  - `disallowed-tools: AskUserQuestion` is the documented way to keep a background fork from stopping to ask.
- **Docs gap.** The docs don't say outright that one command can call another through the `Skill` tool, and they don't say how a nested `Skill` call treats `AskUserQuestion`. A command chain done by "main session reads the next command's file and follows it" is the dependable form. This matches the authoring skill's "read-and-follow this helper file" rule and the existing `update_todo.md` protected-helper pattern.
- **Good at.** A `Skill` call that runs in the main session keeps that session's tools, including `AskUserQuestion`, and its context.
- **What breaks.** The context of a chained run accumulates in one session (a spec run followed by `register_design` plus `spec_from_idea` is long). A chained command that has `disable-model-invocation: true` can't be called by the model. Whether other plugin commands are callable depends on that flag, so this must be checked for each command in the chain.
- **Verdict.** Fits as a "main session reads the next command file and follows it" chain. Don't rely on the `Skill` tool for commands that need `AskUserQuestion` until it is tested.

### 1e. `AskUserQuestion` in subagents
- **Mechanism.** Removed from every subagent, "even when listed in the `tools` field" (https://code.claude.com/docs/en/sub-agents). In `claude -p`, `AskUserQuestion` is denied even under `dontAsk`, and `--permission-prompts none` removes it (https://code.claude.com/docs/en/headless).
- **Consequence.** Questions can only be asked by the depth-0 orchestrator, which is what the idea's "get the input up front" needs: ask first, then pass the answers into the subagents and chained steps as arguments or file content.
- **Verdict.** Fits. It is exactly the repository's current rule.

### 1f. Headless and autonomous mode
- **Mechanism.** `claude -p` runs a prompt non-interactively. `/skill-name` in the prompt expands user-invoked skills and custom commands. `--allowedTools`, `--permission-mode`, `--output-format json` and `--json-schema` give scripted control, and `--bare` skips discovery of plugins, so it needs `--plugin-dir`. `-p` runs wait for background subagents. Scheduled tasks "can't ask clarifying questions", so prompts must state success and what to do with results.
- **Good at.** Re-running the independent QA step from CI or a script.
- **What breaks.** It can't answer questions. `-p` worktrees are not cleaned up (they remain locked). Teammates are not spawned.
- **Verdict.** Fits as an escape hatch (QA re-run), but not for the interactive spec commands.

### 1g. Workflow tool / "ultracode"
I found no documentation for a Workflow tool or "ultracode" orchestration. The headless docs mention background "subagents and workflows" and a "dynamic workflow" in passing, but nothing that explains them. UNVERIFIED, so don't build on it.

## 2. GitHub spec-kit

Sources:
- https://github.com/github/spec-kit
- https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/tasks.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/clarify.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/implement.md

- **Chaining.** The sequence is constitution, specify, plan, tasks, implement, converge. The README says to run them "one at a time, reviewing each result before continuing", with no auto-chaining. The only chain is the `handoffs` frontmatter on each command: for example `tasks` offers "Analyze For Consistency" and "Implement Project" with `send: true`, which pre-fills the next prompt for the user.
- **Parallel `[P]`.**
  - The `/speckit.tasks` generator emits `- [ ] T005 [P] Implement ... in src/middleware/auth.py`. The marker is allowed "ONLY if task is parallelizable (different files, no dependencies on incomplete tasks)".
  - `implement.md` says "parallel tasks [P] can run together", tasks on the same files must run sequentially, and when `[P]` tasks fail the agent should "continue with successful tasks, report failed ones".
  - It is an instruction to one agent, not an orchestrator. spec-kit adds no worktrees and no subagent fan-out, and it relies on the agent to decide.
- **Up-front questions.** `/speckit.clarify` asks at most 5 questions per session, strictly one at a time. Multiple-choice questions mark a "Recommended" option with the reasoning, and short answers are 5 words or fewer with a "Suggested" answer. Answers go into a `## Clarifications / ### Session YYYY-MM-DD` section, and each is folded into the relevant spec section. `implement` also gates on unchecked checklists and asks "proceed anyway? (yes/no)".
- **Good at.** Cheap, readable partitioning (the `[P]` plus file-path convention), and a recorded Q&A trail in the artifact itself.
- **What breaks.** No enforcement of file disjointness, no isolation, one question at a time (slow), and the user must run each phase.
- **Verdict.** Steal the ideas, not the machinery:
  - `[P]` plus file paths per task, with the plan's slices being the unit.
  - A recommended answer with each question.
  - A dated Q&A log in the spec directory.
  - A single question batch up front is faster than spec-kit's one-at-a-time loop, so batch the questions.

## 3. Open-source orchestration plugins and worktree runners

- **superpowers (obra).** Source: https://github.com/obra/superpowers.
  - Skills: `using-git-worktrees`, `subagent-driven-development`, `dispatching-parallel-agents`, `requesting-code-review` and `finishing-a-development-branch`.
  - Flow: after design approval it creates a worktree on a new branch, runs project setup and verifies a clean test baseline. It then dispatches a fresh subagent per task, with two-stage review after each task (spec compliance, then code quality). Critical review issues block progress. `finishing-a-development-branch` offers merge, PR, keep or discard and cleans up the worktree. The README claims autonomous runs "for a couple hours at a time".
  - Strength: one worktree per run, fresh subagents per task keep the main context small, and setup plus baseline checks happen once.
  - Weakness: tasks run sequentially in one worktree, so it protects context rather than gaining speed. The page doesn't explain how `dispatching-parallel-agents` coordinates with worktrees.
  - Verdict: fits. It mirrors the SDD plugin's existing per-run worktree plus a mechanic or worker per task.
- **SwarmGit and generic "one worktree per agent" tools.** Source: https://pypi.org/project/swarmgit/ (summarised in a search snippet, so details are UNVERIFIED). One worktree and branch per agent, then completed branches merged into main sequentially, with conflict resolution in a coordination step. Other guides repeat the point that isolation moves conflicts to merge time and a long-lived branch diverges more (https://betterstack.com/community/guides/ai/git-worktrees-claude/, https://www.morphllm.com/claude-code-worktrees).
  - Verdict: fits, with short-lived branches merged back right away and one orchestrator doing the merge.
- **BMAD-METHOD, claude-flow, gastown, ccswarm, ralph-wiggum loop.** I did not fetch primary sources for these, so mechanisms are UNVERIFIED. Do not cite them in the spec without a follow-up fetch. From general knowledge only: BMAD uses persona agents and hand-off documents (story files), and the ralph loop re-runs one prompt until a completion check passes. Both are heavier than the SDD plugin needs.

## 4. Aider, Codex, Cursor, Devin

The only source here is vendor-neutral comparison blogs from a web search (https://techsy.io/blog/background-coding-agents-compared, https://ssojet.com/blog/background-coding-agents, https://aitoolsatlas.ai/tools/cursor-background-agents). Treat all of this as UNVERIFIED.

- **Cursor background agents (Cloud Agents).** A detached, isolated cloud VM per agent that reports back asynchronously and delivers via pull request, up to about 8 in parallel. Isolation is a remote machine, not a worktree. Good at: unattended parallel tasks. Breaks: the agent starts from the remote repo, so local uncommitted state is invisible. Verdict: the idea (one sandbox per task, PR as the merge point) applies, but it isn't available inside a Claude Code plugin.
- **Codex cloud.** Runs in OpenAI-managed infrastructure; tasks in the background, several attempts can be compared. Details of container and branch handling were not in the results. Same verdict.
- **Devin.** Parallel sessions in cloud sandboxes (details not retrieved). Same verdict.
- **Aider.** Terminal pair programmer with no managed background mode; it commits per edit (from general knowledge, not retrieved). Nothing to take for parallelism.
- **Pattern across these.** The sandbox owns the whole task and the integration point is a branch or PR. For a plugin, that maps to "one worktree and one branch per slice, merged by the orchestrator".

## 5. Implement, then an independently re-runnable QA step

- **spec-kit.** `/speckit-implement` and `/speckit-converge` are repeated "until convergence reports `Converged`" (https://github.com/github/spec-kit). The checker is a separate command and re-runnable, but the user chains them by hand. `analyze` is the offered handoff after `tasks`.
- **superpowers.** Review is built into the loop (per task and a final check, `requesting-code-review`), and tests are verified at the start (baseline) and in `finishing-a-development-branch`. QA is not a separate re-runnable command (https://github.com/obra/superpowers).
- **Claude Code.** Two ways to keep QA separate and re-runnable:
  - A user-invokable command or skill, run after implement in the main session. For `-p`, a `claude -p "/plugin:qa"` call re-runs it.
  - A subagent running the project's QA command (`sdd-worker` or `sdd-mechanic`) and writing `qa_report.md`, which is the file-based hand-off the plugin already uses.
- **Good at.** One QA entry point, called at the end of `implement_plan` and also by the user alone. The two callers see the same command.
- **What breaks.** A chained QA that needs `AskUserQuestion` (for example a decision on a skipped test) can't ask from a subagent, so findings should go to `qa_report.md` and come back for the orchestrator to ask about. Chained QA also runs late, after the long implement context. In `-p` mode it can't ask at all.
- **Verdict.** Fits: `implement_plan` ends by reading and following the QA command file. The standalone QA command remains for re-runs. This is also the README's current rule that the QA command is "the project's own".

## Summary of verdicts

| Pattern | Source | Fits the Markdown plugin plus no-nesting rule? |
|---|---|---|
| Subagent `isolation: worktree` for parallel slices | Claude Code | Yes, but needs `worktree.baseRef: "head"` or hand-made worktrees, plus explicit dependency setup per worktree |
| `--worktree` for the whole run | Claude Code | Yes (already used by `/sdd:start`) |
| `EnterWorktree` for parallelism | Claude Code | No (session-wide switch, not parallel) |
| Agent teams | Claude Code | No (experimental, interactive only) |
| Read-and-follow command chain | Claude Code, plugin | Yes (use it for start to register_design to spec_from_idea) |
| `Skill` tool chain | Claude Code | Uncertain (undocumented for commands, check `disable-model-invocation`) |
| Ask all questions at depth 0, pass answers down | Claude Code (`AskUserQuestion` removed in subagents) | Yes (required) |
| `[P]` task markers plus file paths | spec-kit | Yes (a convention in the plan, no machinery) |
| Recommended answer per question, dated Q&A log | spec-kit | Yes |
| Worktree plus per-task subagents plus two-stage review | superpowers | Yes |
| One branch per agent, sequential merge by orchestrator | swarm-style tools (UNVERIFIED) | Yes (short-lived branches) |
| Cloud sandbox per task | Cursor, Codex, Devin (UNVERIFIED) | No (not available to a plugin) |
| Separate re-runnable verifier command | spec-kit, Claude Code | Yes |

## Open questions for the spec
1. Test whether `/plugin:command` can be called through the `Skill` tool from another command, and what `AskUserQuestion` does there. The docs don't say.
2. Decide how a slice worktree gets its base commit: `worktree.baseRef: "head"` (global setting) or hand-made `git worktree add` from the feature branch.
3. Decide how slice worktrees get their environment (for this project, install and database setup) before the slices start. Neither `.worktreeinclude` nor `EnterWorktree` does this.
4. Re-check the depth-1 nesting claim in the authoring skill against `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`.
5. Fetch primary sources for BMAD, claude-flow, gastown and Devin if the spec wants to cite them.

status: ok · reason: Claude Code, spec-kit and superpowers verified from primary sources; BMAD, claude-flow, gastown, Aider, Codex, Cursor and Devin marked UNVERIFIED (search snippets only)
