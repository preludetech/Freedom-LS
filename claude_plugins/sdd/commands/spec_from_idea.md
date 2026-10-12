---
description: Create a specification based on an idea
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill, AskUserQuestion, WebFetch, WebSearch
# based on https://github.com/iamshaunjp/Claude-Code-Masterclass/blob/claude/snippets/commands/spec-v1.md
---

You are helping to spin up a new feature spec for this application, from a short idea provided in the user input below.

# Output

- Create a spec document in the same directory as the idea file. Name it `1. spec.md`
- Run the review wave over it and edit in every clear fix
- Print a summary with one line per applied fix (what, dimension, evidence) and the spec's line and word counts before and after the review

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Start the work; don't ask permission for it.** Never ask whether to research, scan or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt everything the worker needs from what the user has already said and what is on disk. Questions only the user can answer are asked at depth 0 *while* the workers run: as early as possible, batched up to four per `AskUserQuestion`. Never ask what a worker or the code will answer, and never hold a worker back for an answer it doesn't need. Ask once, early, with a default; late questions and review judgement calls follow "When a question comes late" in the `claude-code-authoring` skill's `fanout_recipe.md`.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's output if they can; ask via `AskUserQuestion` only if they can't. Then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Once the phase artifact is finalised, delete this command's own scratch files **by name** — never the `.sdd-work/` directory itself, which is shared with every other SDD command and may hold a concurrent run's files. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Step 0: Pre-step rebase

Read `${CLAUDE_PLUGIN_ROOT}/commands/protected/pre_step_rebase.md` and follow its steps.

# Step 1: Research fan-out

Read the idea carefully, then spawn the research straight away, in the background: one `sdd:sdd-worker` per topic, each writing `research_<topic>.md` beside the idea file (atomically, with a `status:` footer and reference URLs for web-sourced findings). Apply resume/retry/blocked per the recipe. A topic whose file exists and ends `status: ok` is skipped. So is a topic whose file exists with no `status:` footer: it was written by a person or an older command, so it is that topic's research and is never overwritten.

Each brief names the topic's question in one sentence and says the idea file is never rewritten.

| topic | question |
| --- | --- |
| `codebase` | What in the existing codebase does this work touch, reuse or conflict with? |
| `best_practices` | What are the established best practices for this challenge? |
| `reference_implementations` | How do reference implementations solve it? |
| `prior_art` | What has already been tried for this, here or elsewhere, and what happened? |
| `ux_patterns` | What are the common UX patterns for this kind of work? |
| `known_complaints` | What do users commonly complain about with this kind of work? |

# Step 2: The question batch, while the workers run (depth 0)

Don't wait for the research to finish before asking, and don't ask what it will answer. This is where `AskUserQuestion` is used — workers stay non-interactive.

1. **Front-load.** As soon as the workers are spawned, ask the questions the idea itself leaves open and no research task bears on: contradictions, ambiguity, edge cases that can go more than one way, and implementation details in the idea where you see a better way (challenge anything that looks wrong). Batch them, up to four per `AskUserQuestion`.
2. **As each research file lands,** read it, drop the questions it answers, and ask the new ones it raises. The window for asking is the time the workers run; if the first `AskUserQuestion` is already answered, ask a follow-up in a further one.

Only ask a question that passes the recipe's test (`claude-code-authoring` skill, `resources/fanout_recipe.md`): the answer changes the spec, nothing on disk or in the research answers it, and there is no obvious default. Once the spec is written in Step 3, a new question takes its default and is recorded as "When a question comes late" describes, until the end-of-run batch in Step 7.

# Step 3: Write `1. spec.md` (synthesis at depth 0)

Read the `research_*.md` files (paths, not dumped contents) and author `1. spec.md`.

Follow `${CLAUDE_PLUGIN_ROOT}/resources/writing_standard.md`. It carries the rules every SDD
artifact obeys: rewriting means replacing, coverage rather than length, the shared cut-list, where
overflow goes, and the two finishing passes. What follows is what is specific to a spec.

Names come from `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`. The spec is where the
vocabulary is fixed, in the identifiers it proposes as much as in its prose.

## Read the whole directory first

The idea file, every sibling `*.md` beside it (notes files, `research_*.md`), and the research from
Step 1. Those are the inputs the spec is written **against**. They are not material to reproduce.
They sit in the same directory and the next command reads them too.

A `design.md`, beside the idea or named under its "Resources", registers a Claude Design design
(see `/sdd:register_design`). Read the design itself the way that file says, and treat it the way
it says. The spec names the `design.md` path under its resources, so the plan and the
implementation read it too.

The design is a visual reference, never a source of scope. The spec's scope comes from the idea
alone. Where the design draws a control, screen, field or state the idea does not ask for, leave it
out of the spec and do not ask the user about it. Never put a theme, theme token, font or icon the
design uses into the spec: the spec uses the project's own theme.

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

The cut-list is in `${CLAUDE_PLUGIN_ROOT}/resources/spec_review_dimensions.md`, under "Never write these in a spec".

## Before you finish

Run the completeness pass from the writing standard against the idea, its sibling files and the
answers from Step 2, then the earning-its-place pass, then `unslop` and a re-read. Report the line
and word counts.
# Step 4: Commit `write the spec`

Delegate to `sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow its steps with `<summary>`: `write the spec`. Tell it to stage `1. spec.md` and each `research_*.md` beside the idea that exists.

# Step 5: Review wave

Spawn the wave the way `${CLAUDE_PLUGIN_ROOT}/commands/spec_review.md` Step 1 does.

# Step 6: Apply the clear fixes

As `${CLAUDE_PLUGIN_ROOT}/commands/spec_review.md` Step 2.

# Step 7: End-of-run question batch

As `${CLAUDE_PLUGIN_ROOT}/commands/spec_review.md` Step 3.

# Step 8: Clean up

As `${CLAUDE_PLUGIN_ROOT}/commands/spec_review.md` Step 4. The `research_*.md` files are durable and stay.

# Step 9: Update the todo list

Invoke the helper at `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the spec file
- `tick:"Run `/sdd:spec_from_idea`"`

No new items to add.

# Step 10: Commit `review the spec`

Delegate to `sdd:sdd-mechanic`: read `${CLAUDE_PLUGIN_ROOT}/resources/commit_and_push.md` and follow its steps with `<summary>`: `review the spec`. Tell it to stage `1. spec.md` and the `todo.md` beside it.
