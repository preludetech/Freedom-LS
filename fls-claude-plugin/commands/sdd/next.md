---
description: Figure out the next step in the SDD workflow and either tick off a completed user task or spawn a fresh agent to run the next slash command
allowed-tools: Read, Glob, Bash, Agent
---

This command inspects the `todo.md` checklist for the current spec and works out what should happen next. When the next item is a slash command, it spawns a **fresh agent** to execute that command — a fresh agent starts with a clean context, which is what command invocations in this project require. Manual (`(user)`) items are still the user's responsibility.

## Step 1: Locate the todo.md

Figure out which spec we're working with, in this order:

1. If the user's input names a file or directory, use that.
2. Otherwise, look at the current branch name and try to match it to a directory inside `spec_dd/` (usually under `spec_dd/2. in progress/`).
3. If still ambiguous, list candidate directories under `spec_dd/` and ask the user which one.

The target file is `todo.md` inside that directory. If it does not exist, the next step is `/sdd:start` — spawn a fresh agent to run it (same pattern as the `(cmd)` branch in Step 3: resolve `fls-claude-plugin/commands/sdd/start.md`, pass the spec directory through in the prompt, and wait for the agent to return). Once the agent finishes, re-read `todo.md` and continue with Step 2.

## Step 2: Read the todo.md and find the next unchecked item

Read the file in full. Walk the checklist top-to-bottom and find the first line starting with `- [ ]`. Note:

- The full item text (for ticking later).
- The marker in parentheses at the start of the text: `(user)` or `(cmd)`. Every item should have exactly one of these — if a step involves both, the checklist should split it into two items.
- The section heading it sits under (the preceding `## …` line).

If every item is already ticked, skip to Step 5 (the "all done" branch).

## Step 3: Act on the next item based on its marker

### If the marker is `(user)`

This is a manual task. Ask the user, in a single short message, whether they have completed it. Quote the exact item text so there's no ambiguity.

- If the user says **yes**: go to Step 4 (tick it).
- If the user says **no** or is unsure: stop. Do not tick anything. Print the item text and a one-line reminder that it needs to be done by hand, then exit.

### If the marker is `(cmd)`

This is a slash command task. You **must** run it — not by invoking the slash command yourself (you can't clear your own context), but by spawning a **fresh agent** via the `Agent` tool. A fresh agent starts with an empty context, which is equivalent to the user running `/clear` and then the command.

1. Extract the slash command name from the item text (e.g. `/spec_from_idea`, `/plan_from_spec`, `/do_qa`).
2. Resolve the command file. SDD commands live at `fls-claude-plugin/commands/sdd/<name>.md` (strip any leading `/sdd:` or `/` from the extracted name). Confirm the file exists before spawning — if it doesn't, stop and tell the user the checklist references an unknown command.
3. Spawn a fresh agent with `subagent_type: "general-purpose"`. The prompt must be self-contained — the agent has no memory of this conversation. Include:
   - The absolute path to the command file and an instruction to read it in full and follow its steps exactly.
   - The absolute path to the `todo.md` and to the spec directory, so the agent doesn't have to re-discover them.
   - Any argument the user passed to `/sdd:next` that the downstream command would need (pass it through verbatim).
   - A reminder that the command is responsible for ticking its own box via the `update_todo` helper when it finishes.
4. Wait for the agent to return, then relay a short summary of its result to the user (see Step 5).

Do not tick anything yourself — the spawned command ticks its own box.

If the marker is anything other than `(user)` or `(cmd)`, stop and tell the user the checklist line has an unrecognised marker — do not guess. In particular, a combined `(user + cmd)` marker is not supported: ask the user to split the item into two.

## Step 4: Tick a completed user task

Only reach this step if the user confirmed they completed a `(user)` item.

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the absolute path to the `todo.md` you read in Step 2.
- `tick:"<exact item text minus the `- [ ]` prefix>"`

No new items to add.

After the helper runs, re-read the file and identify the new next unchecked item so you can tell the user what comes up (see Step 5).

## Step 5: Report back

Keep the summary short. One of:

- **All done**: "All items in `todo.md` are checked. If the PR has been merged, you're finished — otherwise pick up at the remaining manual step." (only if every item was already ticked at Step 2).
- **Ticked a user item, next is manual**: "Ticked `<item text>`. Next up: `<next item text>` — do it by hand, then run `/sdd:next` again."
- **Ticked a user item, next is a command**: report that, then proceed straight into the `(cmd)` branch and spawn the agent. After it returns, summarise what it did.
- **Ran a command via a fresh agent**: "Ran `<command>` in a fresh agent. Result: `<one-line summary from the agent>`. Run `/sdd:next` again to continue."
- **User hasn't done it yet**: "Next up: `<item text>`. This is a manual step — do it, then run `/sdd:next` again."

Do not print the whole checklist.
