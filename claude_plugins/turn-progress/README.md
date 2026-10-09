# turn-progress

A Claude Code mod that shows how far through the current task Claude is: which step it is on, out of how many, with a bar.

## What it shows

A band above the prompt while a task has open steps or a turn runs:

```
▶ Step 2 of 5: Fixing the second bug  ██░░░░░░░░ 1/5   ·  ⟳ 42s · req 3 · thinking · 4 tools (1 running)   [Hide]
```

The step line comes first. After it, dimmer, the activity: elapsed time, which model request the turn is on (`req`), the spinner's word, tool counts, agents, backgrounded shells.

`/progress` opens a pane:

```
Fix three bugs
Step 2 of 5: Fixing the second bug
██████░░░░░░░░░░░░░░░░░░░░░░░░ 20%
✓ Fix bug 1
● Fixing the second bug
○ Fix bug 3
○ Run the suite
○ Commit

Turn 42s · req 3 · thinking · 4 tools (1 running)

Agents
● Explore  Survey the app  12s · 4 tools

Shells
● Run the suite  8s
```

`✓` done, `●` in progress, `✗` failed, `○` pending. `/progress clear` drops the steps.

## Where the steps come from

Claude declares them. The mod registers two tools and tells Claude, in a system-prompt section, to use them before starting any task with more than one piece:

- `mcp__turn-progress__set_steps { title?, steps: string[], current? }` — declares the plan, replacing any earlier one.
- `mcp__turn-progress__step { index, status: in_progress | completed | failed, note? }` — advances. Completing a step starts the next pending one, so one call per piece is enough.

The instruction text is `STEPS_PROMPT` in `hooks/register.tsx`. If Claude skips the call on some kind of task, name that kind there.

Two fallbacks, used only while no steps are declared:

- a fan-out of subagents from the main loop: each agent is a step, completed when the agent ends;
- a `TodoWrite` or `TaskCreate`/`TaskUpdate` list, when the session offers those tools.

Declared steps always win. Steps survive across turns until every one is done or failed; the next task's `set_steps` replaces them.

## What it cannot show

A running shell command's output is not reachable from a mod (the engine runs the Bash tool itself), so a shell row shows the command, its elapsed time and whether it ended in error, not its stdout.

## Loading it

`claude.sh` passes `--plugin-dir claude_plugins/turn-progress`, so a session started with `./claude.sh` has it. A session started another way can add the flag by hand.

`.claude-plugin/types/` is written by the engine on each load and is gitignored.

## Checking it

```
claude plugin validate claude_plugins/turn-progress
claude plugin test claude_plugins/turn-progress
```
