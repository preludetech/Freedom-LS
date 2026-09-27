---
name: implement_plan
description: Execute the implementation plan in resilient batches.
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Skill, Agent
---

# Executing Plans

This command runs at **depth 0** (the main thread) and orchestrates batch sub-agents.

## Step 0: Pre-step rebase

Read `claude_plugins/sdd/commands/protected/pre_step_rebase.md` and follow its steps (skip this
when `/sdd:next` says it already ran this turn).

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

### Testing skills

Before spawning anything, read `## Testing Skills` from `.claude/sdd/config.md`, then from
`.claude/sdd/config.local.md`, whose values win. Blank, or the file or section absent, means the
list is empty. When it is not empty, every brief for an implementer, reviewer, boy-scout or fix
agent opens with:

> Before anything else, invoke the `Skill` tool for each of: <ids>, in order.

Make one batch per vertical slice in the plan, in the plan's order. A slice runs end to end through every layer its behaviour needs (e.g. "learner can see their deadline on the course page": field + migration + view + template + tests), so never regroup the plan's steps by layer ("all the models", then "all the views"). A small shared-groundwork step the plan places before a slice goes into that slice's batch. If the plan is not ordered as slices, group its steps into the thinnest batches that each deliver working, tested behaviour. Assign each batch a deterministic completion marker: a git commit whose message is prefixed `[batch N] <summary>`.

**Resume scan (before spawning):** scan `git log` for existing `[batch N]` commits and **skip completed batches**. Only spawn batches whose marker commit is missing.

For each remaining batch, spawn **one implementation sub-agent** via the `Agent` tool with `subagent_type: "sdd:sdd-implementer"`, and pass the per-spawn `model: "sonnet"` parameter so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Its brief carries the skill line (when the list from above is not empty), the batch's plan steps verbatim, and the commit subject `[batch N] <summary>`. The TDD, full-suite and commit rules live in the `sdd:sdd-implementer` agent file, which returns a structured status (`status: ok|failed|blocked` · `reason:`).

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. Agents whose work is a commit make it themselves; `sdd:sdd-mechanic` makes the bookkeeping commits.

After a batch returns, act on its status:
- `ok` → verify the `[batch N]` commit exists, then move to the next batch.
- `failed` → reset any partial uncommitted work so the retry starts clean, then retry that batch (≤2 attempts) with the prior error included in the brief.
- `blocked` → gather the listed `needs` via `AskUserQuestion` (legal at depth 0), then re-spawn the batch with the answers.

**All tests must pass before moving to the next batch.**

### DO NOT run the frontend_qa plan during implementation
If there is a `3. frontend_qa.md` file, do **not** run it, and ignore any plan step that says to run it. The QA process runs separately, after the plan is complete.

## Step 3: Final Verification

After all batches are complete:

1. Run `uv run pytest` via `sdd:sdd-mechanic` to confirm everything passes
2. Check each success criterion from the plan — is it met?
3. If any criterion is unmet: fix it with one `sdd:sdd-implementer` (`subagent_type: "sdd:sdd-implementer"`, per-spawn `model: "sonnet"`), whose brief carries the skill line (when the Testing Skills list is not empty) and the unmet criterion, then repeat from step 1
4. Once everything passes: make the final commit via `sdd:sdd-mechanic`

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

Delegate to `sdd:sdd-mechanic`: invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:"Run `/implement_plan` to execute the implementation plan"`

No new items to add.
