---
description: Review the implementation plan for new cross-app dependencies before any code is written
allowed-tools: Read, Glob, Grep, Edit
---

You are reviewing an **implementation plan** (not code) against the project's authoritative app-dependency diagram at `docs/app_structure.md`. Your job is to catch any new cross-app imports the plan would introduce, so structural changes get approved before implementation time is spent on them.

This mirrors `/plan_security_review`: same callout pattern, same `update_todo` flow, different concern. Where security-review asks "is this safe?", this command asks "does this respect our app boundaries?".

The diagram is the source of truth. If the plan needs an edge that isn't in the diagram, that's either a change worth accepting (with a rationale) or a signal to restructure.

Always adhere to any rules or requirements set out in any CLAUDE.md files when responding.

# Inputs

- `2. plan.md` — the implementation plan under review
- `1. spec.md` — the spec the plan is derived from (for context)
- `docs/app_structure.md` — the current approved dependency graph

# Output

- Edit `2. plan.md` directly where a new cross-app edge can be avoided with a small, obvious restructuring (e.g. moving a helper to a more appropriate app).
- Where accepting or rejecting a new edge is a judgement call, insert a `> **Structure concern:**` callout at the relevant section of the plan and ask the user for input.
- Print a short summary of what changed and what still needs user input.

# Step 1: Confirm prerequisites

Check that `docs/app_structure.md` exists. If it does **not**, stop and tell the user:

> `docs/app_structure.md` is missing. Run `/app_map` first to generate it, then re-run `/plan_structure_review`.

Do not try to review the plan without the diagram — the whole point is to diff against the approved graph.

# Step 2: Parse the approved graph

Read `docs/app_structure.md` and extract:

- The set of apps (nodes in the mermaid block).
- The set of runtime edges (lines of the form `A --> B`).
- The set of test-only edges (lines of the form `A -.-> B`).

Also read `1. spec.md` and `2. plan.md` in full. If the plan or spec is missing, stop and ask the user.

# Step 3: Identify proposed cross-app edges in the plan

Walk the plan looking for evidence of cross-app imports it would introduce. Signals to look for:

- Explicit `from <app>.<module> import …` snippets inside code blocks or step descriptions.
- Step descriptions that create files in app `A` and reference models, forms, views, services, or helpers from app `B`.
- New tests in app `A` that rely on factories, fixtures, or data builders from app `B`.
- New management commands or signal handlers in `A` that orchestrate work in `B`.

For each such signal, record the directed edge `(source_app, target_app)`. Classify each edge as **runtime** or **test-only** based on where the code would live (tests/, `test_*.py`, `conftest.py` → test-only; everything else → runtime).

If the plan is vague about where code will live, flag that ambiguity as a callout rather than guessing.

# Step 4: Classify each proposed edge

For every edge you extracted:

1. **Already in the graph as a runtime edge** → no action.
2. **Already in the graph as a test-only edge, and the plan would make it runtime** → this is a *promotion*, and counts as new. Flag.
3. **Not in the graph at all** → new edge. Flag.
4. **Removes an existing edge** → note in the summary, but do not flag. Fewer edges is generally good.

# Step 5: Edit or flag

For each new edge you identified:

- If the fix is obvious and small (e.g. a helper clearly belongs in a shared low-level app that's already depended on by both ends), edit `2. plan.md` directly to move the code.
- Otherwise, insert a `> **Structure concern:**` callout in `2. plan.md` near the relevant step. Follow this shape:

  > **Structure concern:** The plan introduces a new runtime edge `A --> B` (specifically: `<why>`). This edge is not in `docs/app_structure.md`. Options:
  > 1. **Accept and document** — add a one-line rationale here, then regenerate `docs/app_structure.md` via `/app_map` after implementation and commit the updated diagram.
  > 2. **Restructure** — move the shared code to an existing common app (e.g. `<suggestion>`), or introduce a narrower interface, so the edge is not needed.

  Adapt wording for test-only edges, promotions, and location-ambiguous cases.

Never auto-resolve ambiguity. When in doubt, flag it.

# Step 6: Write the summary

Print:

- The set of new edges you detected (runtime and test-only separately).
- Which new edges you resolved by editing the plan directly.
- Which new edges were flagged as `> **Structure concern:**` callouts for user decision.
- Whether the plan is safe to proceed with (no new edges, or all new edges already edited away), or whether the user must resolve flagged concerns first.

# Step 7: Update the todo list

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as `2. plan.md`.
- `tick:"Run `/plan_structure_review` to check for new cross-app dependencies"`
- For each `> **Structure concern:**` callout you added to `2. plan.md`, pass one `add:"Plan structure review|user|Resolve structure concern: <short label>"`. If you added no callouts, omit `add:`.

# Out of scope

- Do not review or modify code — the code does not exist yet.
- Do not regenerate `docs/app_structure.md`. That's `/app_map`'s job, and it should only happen after an approved structural change lands in code.
- Do not propose refactors that are unrelated to the proposed edges — this is about cross-app boundaries, nothing else.
