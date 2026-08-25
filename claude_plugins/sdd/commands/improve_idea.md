---
description: Improve the idea by doing research and making suggestions
allowed-tools: Read, Glob, WebFetch, WebSearch, Write, Agent, Skill
---

Read the given idea file carefully. Your job is to help refine the idea by doing research and making suggestions.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents.

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt. Subagents don't have access to `AskUserQuestion`
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` inside the spec directory, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"` (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

## Step 1: Figure out what we need to research

Read through the idea and decide what to research. If the plan isn't clear, ask the user (recipe step 1).

You might want to research: reference implementations, best practices for the challenge, common UX patterns, common UX challenges and complaints for this kind of work.

Output: a concrete list of research topics, each assigned a **durable** filename `research_<topic>.md` in the same directory as the idea file. (These are the artifacts `setup_todo_list.md` already detects — keep the naming scheme.)

## Step 2: Do the research (fan-out)

Apply the Fan-out recipe: one `sdd:sdd-worker` **per topic**, each writing its own `research_<topic>.md` (atomically, with a `status:` footer and reference URLs for web-sourced findings). Resume = skip topics whose file already ends `status: ok`; retry failed topics (≤2); `blocked` → ask the user, re-spawn.

## Step 3: Refine the idea (synthesis at depth 0)

Read the `research_*.md` **files** and rewrite the idea.

Ask questions if you need to. Don't make big decisions on your own.

### Refining means replacing

Rewrite the idea whole. It is not the original with findings bolted on top. Research that changed a
decision changes the text. Research that confirmed a decision leaves no trace at all.

The result is still an idea: what we are doing, why, and what has been settled. It is not a
specification, and it is not a record of how you arrived at it.

### Never write these

This list exists because each item has actually shown up in a refined idea and made it worse.

- **Research narration.** No "research status" preamble, no "what the research changed", no
  claim/verdict tables, no "the audit corrected this", no strikethrough over superseded text. State
  the conclusion as a fact. The `research_*.md` files are durable and sit next to the idea; if one
  is worth pointing at, cite it by filename with a one-line gloss.
- **Implementation checklists.** No "likely scope of the spec", no helper-function names, env-var
  schemes, migration steps, or file-by-file work lists. `/sdd:spec_from_idea` does that, and it
  re-reads the codebase when it does.
- **A decision stated more than once.** Pick where it belongs and delete the echoes.
- **`path/file.py:123` on claims nobody would dispute.** Backtick the symbol or path instead. Cite a
  line number only where the reader has to go and look in order to act.
- **Throat-clearing about what the idea is not**, unless it is a real scope boundary.
- **Sections that exist to hold leftovers.** If something doesn't fit the idea, it goes in a sibling
  file or it goes away.

### Where the overflow goes

Detail worth keeping that doesn't belong in the idea goes into a **sibling file in the same
directory**, never into an extra section. `research_*.md` is the home for findings. Anything else
gets its own clearly named file. `/sdd:spec_from_idea` reads the directory, so nothing is stranded.

### Test-fit every paragraph

If cutting it wouldn't change a decision the spec has to make, cut it.

### Finish with two passes

1. Invoke the `unslop` skill over the idea file.
2. Re-read it top to bottom as if someone else wrote it, and delete whatever now reads as padding.

Report the before and after line and word counts in your summary, so the direction of travel is
visible.

No scratch cleanup here. The `research_*.md` files are durable artifacts, not `.sdd-work/` scratch.

## Step 4: Update the todo list

Invoke the helper at `claude_plugins/sdd/commands/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as the idea file
- `tick:"Optionally run `/improve_idea` to research and refine the idea"`

No new items to add.
