---
description: Review the implementation plan for new cross-app dependencies before any code is written
allowed-tools: Read, Glob, Grep, Edit, Agent
---

You are reviewing an **implementation plan** (not code) against the project's authoritative app-dependency diagram at `docs/app_structure.md`. Your job is to catch any new cross-app imports the plan would introduce, so structural changes get approved before implementation time is spent on them.

This mirrors `/plan_security_review`: same callout pattern, same `update_todo` flow, different concern. Where security-review asks "is this safe?", this command asks "does this respect our app boundaries?".

The diagram is the source of truth. If the plan needs an edge that isn't in the diagram, that's either a change worth accepting (with a rationale) or a signal to restructure.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` inside the spec directory, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "fls:sdd-worker"` (or `"fls:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Inputs

- `2. plan.md` — the implementation plan under review
- `1. spec.md` — the spec the plan is derived from (for context)
- `docs/app_structure.md` — the current approved dependency graph

# Output

- Edit `2. plan.md` directly where a new cross-app edge can be avoided with a small, obvious restructuring (e.g. moving a helper to a more appropriate app).
- Where accepting or rejecting a new edge is a judgement call, insert a `> **Structure concern:**` callout at the relevant section of the plan and ask the user for input.
- Print a short summary of what changed and what still needs user input.

# Step 1: Confirm prerequisites (depth 0)

Check that `docs/app_structure.md` exists. If it does **not**, stop and tell the user:

> `docs/app_structure.md` is missing. Run `/app_map` first to generate it, then re-run `/plan_structure_review`.

Do not try to review the plan without the diagram — the whole point is to diff against the approved graph. Also confirm `1. spec.md` and `2. plan.md` exist; if either is missing, stop and ask the user.

# Step 2: Delegate the parse + scan (fan-out)

Spawn **one `fls:sdd-worker`** to parse the approved graph and identify the cross-app edges the plan would introduce, writing its findings to `.sdd-work/plan_structure_findings.md` (atomically, with a `status:` footer). Apply resume/retry/blocked per the recipe. The worker's brief:

## Scan specification (the worker's brief)

**Parse the approved graph.** Read `docs/app_structure.md` and extract:
- The set of apps (nodes in the mermaid block).
- The set of runtime edges (lines of the form `A --> B`).
- The set of test-only edges (lines of the form `A -.-> B`).

Also read `1. spec.md` and `2. plan.md` in full.

**Identify proposed cross-app edges in the plan.** Signals to look for:
- Explicit `from <app>.<module> import …` snippets inside code blocks or step descriptions.
- Step descriptions that create files in app `A` and reference models, forms, views, services, or helpers from app `B`.
- New tests in app `A` that rely on factories, fixtures, or data builders from app `B`.
- New management commands or signal handlers in `A` that orchestrate work in `B`.

For each such signal, record the directed edge `(source_app, target_app)`. Classify each edge as **runtime** or **test-only** based on where the code would live (tests/, `test_*.py`, `conftest.py` → test-only; everything else → runtime). If the plan is vague about where code will live, record that ambiguity rather than guessing.

**Classify each proposed edge:**
1. **Already in the graph as a runtime edge** → no action.
2. **Already in the graph as a test-only edge, and the plan would make it runtime** → this is a *promotion*, and counts as new. Flag.
3. **Not in the graph at all** → new edge. Flag.
4. **Removes an existing edge** → note in the summary, but do not flag. Fewer edges is generally good.

The worker writes, per flagged edge: the edge, runtime/test-only, why the plan implies it, the plan section, and whether the fix is obvious (small restructuring) or a judgement call.

# Step 3: Edit or flag (depth 0)

Read `.sdd-work/plan_structure_findings.md` (the file, not dumped contents). For each new edge:

- If the fix is obvious and small (e.g. a helper clearly belongs in a shared low-level app that's already depended on by both ends), edit `2. plan.md` directly to move the code.
- Otherwise, insert a `> **Structure concern:**` callout in `2. plan.md` near the relevant step. Follow this shape:

  > **Structure concern:** The plan introduces a new runtime edge `A --> B` (specifically: `<why>`). This edge is not in `docs/app_structure.md`. Options:
  > 1. **Accept and document** — add a one-line rationale here, then regenerate `docs/app_structure.md` via `/app_map` after implementation and commit the updated diagram.
  > 2. **Restructure** — move the shared code to an existing common app (e.g. `<suggestion>`), or introduce a narrower interface, so the edge is not needed.

  Adapt wording for test-only edges, promotions, and location-ambiguous cases.

Never auto-resolve ambiguity. When in doubt, flag it.

# Step 4: Write the summary

Print:

- The set of new edges you detected (runtime and test-only separately).
- Which new edges you resolved by editing the plan directly.
- Which new edges were flagged as `> **Structure concern:**` callouts for user decision.
- Whether the plan is safe to proceed with (no new edges, or all new edges already edited away), or whether the user must resolve flagged concerns first.

# Step 5: Clean up

Delete the `.sdd-work/` scratch directory once the review is complete (recipe step 7).

# Step 6: Update the todo list

Delegate to `fls:sdd-mechanic`: invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as `2. plan.md`.
- `tick:"Run `/plan_structure_review` to check for new cross-app dependencies"`
- For each `> **Structure concern:**` callout you added to `2. plan.md`, pass one `add:"Plan structure review|user|Resolve structure concern: <short label>"`. If you added no callouts, omit `add:`.

# Out of scope

- Do not review or modify code — the code does not exist yet.
- Do not regenerate `docs/app_structure.md`. That's `/app_map`'s job, and it should only happen after an approved structural change lands in code.
- Do not propose refactors that are unrelated to the proposed edges — this is about cross-app boundaries, nothing else.
