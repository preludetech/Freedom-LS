---
description: Create a specification based on an idea
allowed-tools: Read, Write, Glob, Agent
---

You are helping to spin up a new feature spec for this application, from a short idea provided in the user input below.

# Output

- Create a spec document in the same directory as the idea file. Name it `1. spec.md`
- Print a short summary of what you did

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` inside the spec directory, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "fls:sdd-worker"` (or `"fls:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 1: gather information (fan-out)

Read the idea carefully. The three research tasks below become **one `fls:sdd-worker` per task**, each writing `.sdd-work/spec_research_<task>.md` (atomically, with a `status:` footer). Apply resume/retry/blocked per the recipe.

- Analyse the existing codebase
- Research relevant best practices
- Examine reference implementations

# Step 2: User input (depth 0)

Ask questions if you are unsure of anything, or need further information. This is where `AskUserQuestion` is used — workers stay non-interactive.

If there are edge cases that can be handled in multiple ways, ask what to do. If there are contradictions or ambiguity, ask what to do. If the idea includes implementation details and you think there is a better way, make suggestions — challenge anything that looks wrong.

Think carefully about what to ask, then ask the user one question at a time.

# Step 3: Create the specification document (synthesis at depth 0)

Read the `.sdd-work/spec_research_*.md` files (paths, not dumped contents) and author `1. spec.md`. Include:

- Why different features/functionality matter
- If decisions were made, why were they made
- Success criteria

# Step 4: Clean up

Delete the `.sdd-work/` scratch directory once `1. spec.md` is written (recipe step 7).

# Step 5: Update the todo list

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/spec_from_idea` to generate the spec"`

No new items to add.
