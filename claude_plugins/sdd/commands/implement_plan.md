---
name: implement_plan
description: Execute the implementation plan in resilient batches.
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Skill, Agent, ToolSearch, AskUserQuestion
argument-hint: [suffix, e.g. 2b]
---

# Executing Plans

This command runs at **depth 0** (the main thread) and orchestrates batch sub-agents.

## Input

`[suffix]`: optional, `2` followed by letters (e.g. `2b`). The plan file is `<suffix>. plan.md`. The QA file swaps the leading `2` for `3`: `3<letters>. frontend_qa.md`. With no suffix they are `2. plan.md` and `3. frontend_qa.md`.

Below, **the plan file** and **the QA file** mean the resolved names, and **`<id>`** means `<suffix>.N` with a suffix and `N` without.

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

Make one batch per vertical slice in the plan, in the plan's order. A slice runs end to end through every layer its behaviour needs (e.g. "learner can see their deadline on the course page": field + migration + view + template + tests), so never regroup the plan's steps by layer ("all the models", then "all the views"). A small shared-groundwork step the plan places before a slice goes into that slice's batch. If the plan is not ordered as slices, group its steps into the thinnest batches that each deliver working, tested behaviour. Assign each batch a deterministic completion marker: a git commit whose message is prefixed `[batch <id>] <summary>`.

**Resume scan (before spawning):** match the subjects from `git log --format=%s origin/main..HEAD` against this exact, anchored pattern and **skip completed batches**. Only spawn batches whose marker commit is missing. A `design fix` commit counts as its batch's commit. When the last completed batch has design states and no later batch is committed, run its Design check before spawning the next batch.

```
with suffix 2b: ^\[batch 2b\.[0-9]+\]     (only this suffix's batches)
without suffix: ^\[batch [0-9]+\]         (never matches [batch 2b.1])
```

For each remaining batch, spawn **one implementation sub-agent** via the `Agent` tool with `subagent_type: "general-purpose"` (it needs Bash/Edit breadth that `sdd:sdd-worker` lacks), and pass the per-spawn `model: "sonnet"` parameter so non-interactive batch work runs on a mid-tier model rather than the session model. (The user can override to `model: "opus"` per spawn — or set `CLAUDE_CODE_SUBAGENT_MODEL` — if a batch needs heavier reasoning.) Each batch sub-agent does the following:

1. Implement each step in the batch exactly as written in the plan
2. Run any verifications the plan specifies after each step
3. After all steps are done, read `claude_plugins/sdd/commands/protected/run_test_tier.md` and follow it with `<tier>`: `targeted` and `<diff>`: `--working-tree`. A failure follows "When a targeted run or full run fails" in the tier definition the helper names. Done when the helper reports a summary line with no failures.
4. **As its final step, make the `[batch <id>] <summary>` git commit itself** with `uv run git commit` (it has `Bash`; the `uv run` prefix is required so the project's pre-commit hooks fire — see `CLAUDE.md`), then return a structured status (`status: ok|failed|blocked` · `reason:`).

Every brief also carries this rule: comments, docstrings and test names state facts about the code and stand on their own. They never mention the spec, plan, research notes or QA plan, or their numbers: no `§4b`, `spec 6`, `this slice`, `batch 3`, `a later spec`, `Phase 2` or `spec_dd/` paths. Where the reasoning came from the spec, write the reasoning itself. If the project has a skill for writing code comments, the batch follows it.

When the batch's slice has a `**Design states:**` line, the brief also passes the **design paths**, as paths and never contents:

- the plan file and the heading of its Design section;
- the design screenshot for each of the slice's design states.

The brief adds: the design is a visual reference, never a source of scope. Build what the plan's Design section transcribes and nothing else the design shows. Use the project's theme tokens, components and semantic icons; never add a theme, theme token, font or colour, and never add an icon that does not fit the project's icon set.

Committing inside the worker keeps the work and its completion marker **atomic**: a crash between "work done" and "marker written" can't leave an uncommitted batch that the resume scan would wrongly re-run over a dirty tree. (This is the one place a worker commits its own work instead of delegating the commit to `sdd:sdd-mechanic` — the atomic-resume guarantee outweighs tiering that single commit down to Haiku.)

After a batch returns, act on its status:
- `ok` → verify the `[batch <id>]` commit exists, then move to the next batch.
- `failed` → reset any partial uncommitted work so the retry starts clean, then retry that batch (≤2 attempts) with the prior error included in the brief.
- `blocked` → gather the listed `needs` via `AskUserQuestion` (legal at depth 0), then re-spawn the batch with the answers.

**The batch's tier must pass before moving to the next batch.** A fix batch is a batch, so it runs `targeted` the same way.

### Design check

Runs at depth 0 after a batch returns `ok` whose slice has a `**Design states:**` line. Its judgement stays at depth 0. It never asks the user whether to build something the design draws, and fix batches never ask the user anything.

Read `Design check` under `## Design Hooks` in `.claude/sdd/config.md` (`config.local.md` wins), the way `claude_plugins/sdd/commands/protected/pre_step_rebase.md` reads `## Rebase Hooks`. A blank value, or an absent file or section, skips the check: record "design check skipped: no Design check hook" for the Step 3 summary and move on.

Otherwise, start with `fixes = 0` and repeat these steps until one of them ends the check:

1. Read the hook file and follow it here with `<spec-dir>`, the plan path and the slice's design states. It returns one screenshot path per state and width. On `failed`, stop the run with `status: failed` and its reason.
2. For each state, Read the app screenshot and the design screenshot. List each one's elements region by region, then diff both lists against the state's design checklist in the plan. Judge layout, order, hierarchy, relative density, states and copy. Colour, font, icons and exact pixels belong to FLS's theme and stay out of the judgement. A drawn element the checklist does not list is not a miss: its absence is correct.
3. Every design checklist line is met (no **design miss**): delete the hook's screenshots by name, log "design check passed", and end the check.
4. A design miss that has already gone to two fix batches and still stands: end the run with `status: blocked`, naming the miss, the plan line it contradicts and the hook's screenshot paths. The screenshots stay as evidence. The next check of that slice overwrites them, because their names are fixed, and deletes them when it passes.
5. Otherwise spawn one fix batch (`subagent_type: "general-purpose"`, `model: "sonnet"`) with the list of misses and the design paths. It commits `[batch <id>] design fix <n>`, and `fixes` goes up by one. Act on its status as for any batch, then go back to step 1.

### DO NOT run the frontend_qa plan during implementation
If there is a QA file, do **not** run it, and ignore any plan step that says to run it. The QA process runs separately, after the plan is complete.

## Step 3: Final Verification

After all batches are complete:

1. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/run_test_tier.md` and follow it with `<tier>`: `full`, returning the summary line and any failing test names.
2. Check each success criterion from the plan — is it met? List each Design check as passed (with its `fixes` count) or skipped.
3. If any criterion is unmet: fix it with a sub-agent (`subagent_type: "general-purpose"`, per-spawn `model: "sonnet"` — the same tier as the batch sub-agents, since fixes need Bash/Edit breadth). The fix sub-agent runs `targeted`, like any batch. Then repeat from step 1, so a fix is followed by another full run
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
- `tick:` the unticked item that names this command. With a suffix, that is the item that also names the suffix. Without one, it is `"Run `/implement_plan` to execute the implementation plan"`.

No new items to add.
