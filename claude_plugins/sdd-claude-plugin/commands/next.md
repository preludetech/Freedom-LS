---
description: Figure out the next SDD step and either tick a completed user task or run the next slash command on the main thread.
allowed-tools: Read, Glob, Bash, Write, Edit, Skill, Agent
---

This command inspects the `todo.md` checklist for the current spec and works out what should happen next. When the next item is a slash command, it runs that command **inline on the main thread (depth 0)** — it reads the command file and follows its steps here, rather than wrapping it in a fresh subagent. Running inline at depth 0 keeps the single fan-out level free, so commands that fan out (research/review) can legally spawn their own workers via this command's `Agent` tool. Manual (`(user)`) items are still the user's responsibility.

## Step 1: Locate the todo.md

Figure out which spec we're working with, in this order:

1. If the user's input names a file or directory, use that.
2. Otherwise, look at the current branch name and try to match it to a directory inside `spec_dd/` (usually under `spec_dd/2. in progress/`).
3. If still ambiguous, list candidate directories under `spec_dd/` and ask the user which one.

The target file is `todo.md` inside that directory. If it does not exist, the next step is `/sdd:start`: resolve `claude_plugins/sdd-claude-plugin/commands/start.md` and **run its steps inline** on the main thread (its mechanical work runs via this command's `Agent` tool — see Step 3). Then re-read `todo.md` and continue with Step 2.

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

This is a slash command task. You run it **inline at depth 0** — read the command file and follow its steps yourself on the main thread (do **not** wrap it in a fresh subagent). Because you run at depth 0, any worker/mechanic fan-out the command calls for executes via **your own `Agent` tool**.

1. Extract the fully-namespaced slash command from the item text (e.g. `/sdd:spec_from_idea`, `/sdd:plan_from_spec`, `/ds:threat-model`, `/fls-dev:do_qa`). The generated `todo.md` always writes each command with its owning-plugin prefix.
2. Resolve the command file with a deterministic **keep-prefix → owning-plugin** map. Split the command on its first `:` into the plugin prefix and the command name, then look up the plugin's commands directory:
   ```
   prefix, name = split_once(command, ":")   # "/sdd:do_qa" -> ("sdd", "do_qa")
   dir = { "sdd":     "claude_plugins/sdd-claude-plugin/commands/",
           "fls-dev":  "claude_plugins/fls-dev-claude-plugin/commands/",
           "ds":      "claude_plugins/django-stack-claude-plugin/commands/" }[prefix]
   target = dir + name + ".md"
   if prefix is not a key of the map, or target does not exist:
       stop and tell the user the checklist references command "{command}" that resolves to no
       command file — the prefix must be one of sdd / fls-dev / ds and the file must exist.
   ```
   This is deterministic — no directory probing, no prefix-stripping, no collision risk.
3. Read the resolved file in full and **follow its steps inline at depth 0**. You already know the `todo.md` path and the spec directory from Steps 1–2, and any argument the user passed to `/sdd:next` — use them so the command doesn't re-discover them. The command ticks its own box via the `update_todo` helper when it finishes.
4. When the command's steps are done, relay a short summary of the result to the user (see Step 5).

Do not tick anything yourself — the command ticks its own box.

If the marker is anything other than `(user)` or `(cmd)`, stop and tell the user the checklist line has an unrecognised marker — do not guess. In particular, a combined `(user + cmd)` marker is not supported: ask the user to split the item into two.

## Step 4: Tick a completed user task

Only reach this step if the user confirmed they completed a `(user)` item.

Invoke the helper at `claude_plugins/sdd-claude-plugin/commands/protected/update_todo.md` with:

- `<todo-path>`: the absolute path to the `todo.md` you read in Step 2.
- `tick:"<exact item text minus the `- [ ]` prefix>"`

No new items to add.

After the helper runs, re-read the file and identify the new next unchecked item so you can tell the user what comes up (see Step 5).

## Step 5: Report back

Keep the summary short. One of:

- **All done**: "All items in `todo.md` are checked. If the PR has been merged, you're finished — otherwise pick up at the remaining manual step." (only if every item was already ticked at Step 2).
- **Ticked a user item, next is manual**: "Ticked `<item text>`. Next up: `<next item text>` — do it by hand, then run `/sdd:next` again."
- **Ticked a user item, next is a command**: report that, then proceed straight into the `(cmd)` branch and run the command inline. After it finishes, summarise what it did.
- **Ran a command on the main thread**: "Ran `<command>` on the main thread. Result: `<one-line summary>`. Run `/clear` then `/sdd:next` again to continue."
- **User hasn't done it yet**: "Next up: `<item text>`. This is a manual step — do it, then run `/sdd:next` again."

Do not print the whole checklist.

> **Inline-execution note (load-bearing).** When you run a `(cmd)` file by reading-and-following it, that file is **not** invoked as a slash command, so its own frontmatter (`model:`, `allowed-tools:`) is **inert** — this command's model and tool grants govern. That is why this command holds the broad toolset (`Read, Glob, Bash, Write, Edit, Skill, Agent`): it must author/edit and perform the inlined command's worker/mechanic spawns itself. The `Agent` and other tool grants on the downstream command files take effect only when a user invokes those commands **directly**; reached via `/sdd:next` they run under this command's grants. Worker/mechanic **agent** files are unaffected — they are *spawned*, not inlined, so their `model:`/`tools:` frontmatter is always live (which is why model tiering lives there). See the `claude-code-authoring` skill.
