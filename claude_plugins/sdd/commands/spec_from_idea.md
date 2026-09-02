---
description: Create a specification based on an idea
allowed-tools: Read, Write, Glob, Grep, Bash, Agent, Skill
# based on https://github.com/iamshaunjp/Claude-Code-Masterclass/blob/claude/snippets/commands/spec-v1.md
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
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 1: gather information (fan-out)

Read the idea carefully. The three research tasks below become **one `sdd:sdd-worker` per task**, each writing `.sdd-work/spec_research_<task>.md` (atomically, with a `status:` footer). Apply resume/retry/blocked per the recipe.

- Analyse the existing codebase
- Research relevant best practices
- Examine reference implementations

# Step 2: User input (depth 0)

Ask questions if you are unsure of anything, or need further information. This is where `AskUserQuestion` is used — workers stay non-interactive.

If there are edge cases that can be handled in multiple ways, ask what to do. If there are contradictions or ambiguity, ask what to do. If the idea includes implementation details and you think there is a better way, make suggestions — challenge anything that looks wrong.

Think carefully about what to ask, then ask the user one question at a time.

# Step 3: Write the specification (synthesis at depth 0)

Read the `.sdd-work/spec_research_*.md` files (paths, not dumped contents) and author `1. spec.md`.

Follow `${CLAUDE_PLUGIN_ROOT}/resources/writing_standard.md`. It carries the rules every SDD
artifact obeys: rewriting means replacing, coverage rather than length, the shared cut-list, where
overflow goes, and the two finishing passes. What follows is what is specific to a spec.

Names come from `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`. The spec is where the
vocabulary is fixed, in the identifiers it proposes as much as in its prose.

## Read the whole directory first

The idea file, every sibling `*.md` beside it (notes files, `research_*.md`), and the research from
step 1. Those are the inputs the spec is written **against**. They are not material to reproduce.
They sit in the same directory and the next command reads them too.

## What the spec is for

Its readers are `/sdd:plan_from_spec` and the human approving it. It answers one question: what has
to be true when this work is done.

It is not a record of how the decision was reached. It is not the step-by-step either. The plan
step does that, and it re-reads the codebase when it does.

## The shape

Use these sections. Omit one when it would be empty; do not invent others.

1. **Purpose.** The problem, in a few sentences.
2. **Terminology.** Only the terms this spec coins or narrows, per
   `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`. Usually there are none.
3. **Scope.** In and out.
4. **Decisions.** Only the ones an implementer could otherwise relitigate, one line of reasoning
   each.
5. **Requirements.** Grouped by the part of the system they change, each naming the files and
   symbols to touch.
6. **Testing.** What has to be proved, not the test code.
7. **Documentation and downstream.** What has to change outside the code.
8. **Open questions.** What the user or an operator still has to settle.
9. **Success criteria.** Checkable, one line each.

## What a spec keeps that an idea doesn't

File paths, symbol names, environment-variable and API contracts, code snippets where prose would
be ambiguous, and named test cases. Cite a line number only where the implementer has to go and
edit that exact spot.

## Never write these in a spec

- **The idea's argument, re-run.** The approach was settled upstream. State the outcome and cite the
  idea by filename. Do not reproduce the reasoning that got there.
- **A decisions table that repeats the body.** A decision explained where it is implemented does not
  also get a table row. A decision in the table is not re-explained in the body.
- **Rejected alternatives at paragraph length.** One sentence naming the alternative and why not, or
  nothing.
- **Reasoning about the spec's own drafting.** No "an earlier draft", no "two notes survive from
  that draft", no "the implementer should not tidy this away".
- **Success criteria that restate sections.** If you cannot say how someone would check it, it is
  not a criterion.
- **Implementation sequencing and work lists.** Ordering constraints belong in the spec only where
  getting them wrong breaks something; everything else is the plan's job.

## Before you finish

Run the completeness pass from the writing standard against the idea, its sibling files and the
answers from step 2, then the earning-its-place pass, then `unslop` and a re-read. Report the line
and word counts.
# Step 4: Clean up

Delete the `.sdd-work/` scratch directory once `1. spec.md` is written (recipe step 7).

# Step 5: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/spec_from_idea` to generate the spec"`

No new items to add.

# Step 6: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `write the spec`. Tell it to stage `1. spec.md` and the `todo.md` beside it.
