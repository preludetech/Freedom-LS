---
description: Initialise an SDD workflow — create the todo.md checklist next to the spec or idea, then create an isolated git worktree for the work
allowed-tools: Read, Write, Glob, Bash, Skill
---

This command kicks off Spec-Driven Development for a new spec. It is a thin orchestrator — all the real work happens in two protected helpers, which are invoked in order.

## Step 1: Set up the todo list

In a subagent:

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md`. Pass through whatever the caller said about which spec or idea this is for, so the helper doesn't have to re-discover it.

Wait for the helper to finish. Note the path to the spec directory it landed on — Step 2 needs it.

## Step 2: Create the worktree

In a subagent:

Invoke the helper at `fls-claude-plugin/commands/sdd/protected/start_worktree.md`, passing through the spec directory from Step 1.

Wait for it to finish.

## Step 3: Report back

Print a short, combined summary:

- Path to the new `todo.md`.
- Path to the new worktree.
- A one-line reminder that the user should `cd` into the worktree and run `/sdd:next` to continue.
