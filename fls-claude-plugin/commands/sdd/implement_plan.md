---
name: implement_plan
description: Execute the implementation plan in resilient batches.
allowed-tools: Read, Glob, Write, Edit, Bash, Skill, Agent
---

# Executing Plans

This command runs at **depth 0** (the main thread) and orchestrates batch sub-agents.

## Step 1: Read and Review the Plan

1. Read the plan file
2. Before implementing anything, check for:
   - Missing or ambiguous steps
   - Steps that depend on things not covered earlier in the plan
   - Unclear success criteria
   - Missing dependencies or prerequisites
3. If you find issues: raise them with the user before starting
4. If the plan is clear: proceed to Step 2

## Step 2: Batch and Execute (resilient)

Split the plan's tasks into batches of related steps. Each batch should be a coherent unit of work (e.g. "add model + migration", "add views + templates + urls"). Assign each batch a deterministic completion marker: a git commit whose message is prefixed `[batch N] <summary>`.

**Resume scan (before spawning):** scan `git log` for existing `[batch N]` commits and **skip completed batches**. Only spawn batches whose marker commit is missing.

For each remaining batch, spawn **one implementation sub-agent** via the `Agent` tool with `subagent_type: "general-purpose"` (it needs Bash/Edit breadth that `fls:sdd-worker` lacks), and pass the per-spawn `model: "sonnet"` parameter so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Each batch sub-agent does the following:

1. Implement each step in the batch exactly as written in the plan
2. Run any verifications the plan specifies after each step
3. After all steps are done, run `uv run pytest` — all tests must pass
4. Use the `request-code-review` skill to review the batch's changes
5. Fix any issues raised by the review
6. Re-run tests after fixes
7. **As its final step, make the `[batch N] <summary>` git commit itself** with `uv run git commit` (it has `Bash`; the `uv run` prefix is required so the project's pre-commit hooks fire — see `CLAUDE.md`), then return a structured status (`status: ok|failed|blocked` · `reason:`).

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. (This is the one place a worker commits its own work instead of delegating the commit to `fls:sdd-mechanic` — the atomic-resume guarantee outweighs tiering that single commit down to Haiku.)

After a batch returns, act on its status:
- `ok` → verify the `[batch N]` commit exists, then move to the next batch.
- `failed` → reset any partial uncommitted work so the retry starts clean, then retry that batch (≤2 attempts) with the prior error included in the brief.
- `blocked` → gather the listed `needs` via `AskUserQuestion` (legal at depth 0), then re-spawn the batch with the answers.

**All tests must pass before moving to the next batch.**

### DO NOT run the frontend_qa plan during implementation
If there is a `3. frontend_qa.md` file, do **not** run it, and ignore any plan step that says to run it. The QA process runs separately, after the plan is complete.

## Step 3: Final Verification

After all batches are complete:

1. Use the `request-code-review` skill to review all changes end-to-end
2. Run `uv run pytest` via `fls:sdd-mechanic` to confirm everything passes
3. Check each success criterion from the plan — is it met?
4. If any criterion is unmet: fix it with a sub-agent (`subagent_type: "general-purpose"`, per-spawn `model: "sonnet"` — the same tier as the batch sub-agents, since fixes need Bash/Edit breadth), then repeat from step 1
5. Once everything passes and review feedback is addressed: make the final commit via `fls:sdd-mechanic`

## When to Stop and Ask

**Stop immediately when:**
- A step is unclear or ambiguous
- A test fails and the cause isn't obvious
- You hit a missing dependency or prerequisite
- The plan has a gap that blocks progress

**Ask for clarification rather than guessing. Don't force through blockers.**

## Branch Safety

Never start implementation on main/master branch without explicit user consent.

## Step 4: Update the todo list

Delegate to `fls:sdd-mechanic`: invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:"Run `/implement_plan` to execute the implementation plan"`

No new items to add.
