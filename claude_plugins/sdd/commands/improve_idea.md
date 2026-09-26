---
description: Improve the idea by doing research and making suggestions
allowed-tools: Read, Glob, Grep, WebFetch, WebSearch, Write, Agent, Skill
---

Read the given idea file carefully. Your job is to help refine the idea by doing research and making suggestions.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents.

1. **Start the work; don't ask permission for it.** Never ask whether to research, scan or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt everything the worker needs from what the user has already said and what is on disk. Questions only the user can answer are asked at depth 0 *while* the workers run: as early as possible, batched up to four per `AskUserQuestion`. Never ask what a worker or the code will answer, and never hold a worker back for an answer it doesn't need.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's output if they can; ask via `AskUserQuestion` only if they can't. Then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Once the phase artifact is finalised, delete this command's own scratch files **by name** — never the `.sdd-work/` directory itself, which is shared with every other SDD command and may hold a concurrent run's files. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

## Step 1: Figure out what we need to research

Read through the idea and decide what to research. Don't ask the user whether or what to research: pick the topics yourself. Where the idea is unclear, research the options rather than asking which one is meant.

You might want to research: reference implementations, best practices for the challenge, common UX patterns, common UX challenges and complaints for this kind of work.

Output: a concrete list of research topics, each assigned a **durable** filename `research_<topic>.md` in the same directory as the idea file. (These are the artifacts `setup_todo_list.md` already detects — keep the naming scheme.)

## Step 2: Do the research (fan-out)

Apply the Fan-out recipe: one `sdd:sdd-worker` **per topic**, each writing its own `research_<topic>.md` (atomically, with a `status:` footer and reference URLs for web-sourced findings). Resume = skip topics whose file already ends `status: ok`; retry failed topics (≤2); `blocked` → supply the needs if the idea, code or another topic can, else ask the user; re-spawn.

While the workers run, ask the questions only the user can answer and no topic bears on, batched up to four per `AskUserQuestion`. As each file lands, drop the questions it answers, ask the ones it raises, and spawn a new topic for anything research can answer.

## Step 3: Refine the idea (synthesis at depth 0)

Read the `research_*.md` **files** and rewrite the idea.

Don't make big decisions on your own: a decision research couldn't settle and the user hasn't answered should already have been asked in Step 2. Anything new that surfaces here gets asked now, in one batch.

Name things the way the project already names them — follow
`${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`. A synonym coined in an idea propagates into
the spec, then the plan, then the code.

Follow `${CLAUDE_PLUGIN_ROOT}/resources/writing_standard.md`. It carries the rules every SDD
artifact obeys: rewriting means replacing, coverage rather than length, the shared cut-list, where
overflow goes, and the two finishing passes. What follows is what is specific to an idea.

### An idea is not a specification

The result is still an idea: what we are doing, why, and what has been settled. It is not a
specification, and it is not a record of how you arrived at it.

### Never write these in an idea

- **Implementation checklists.** No "likely scope of the spec", no helper-function names, env-var
  schemes, migration steps, or file-by-file work lists. `/sdd:spec_from_idea` does that, and it
  re-reads the codebase when it does.
- **`path/file.py:123` on claims nobody would dispute.** Backtick the symbol or path instead. Cite a
  line number only where the reader has to go and look in order to act.

### Where the overflow goes

`research_*.md` is the home for findings. They are durable and sit next to the idea, so if one is
worth pointing at, cite it by filename with a one-line gloss rather than summarising it. Anything
else worth keeping that does not belong in the idea gets its own clearly named sibling file.
`/sdd:spec_from_idea` reads the directory, so nothing is stranded.

No scratch cleanup here. The `research_*.md` files are durable artifacts, not `.sdd-work/` scratch.

## Step 4: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the idea file
- `tick:"Optionally run `/improve_idea` to research and refine the idea"`

No new items to add.

## Step 5: Commit and push

Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and follow its
steps with `<summary>`: `research and refine the idea`. Tell it to stage the idea file and every
`research_*.md` this run wrote.
