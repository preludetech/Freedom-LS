---
description: Initialise an SDD workflow — create the todo.md checklist next to the spec or idea, then create an isolated git worktree for the work
allowed-tools: Read, Write, Glob, Bash, Skill, Agent
---

This command kicks off Spec-Driven Development for a new spec. It is a thin orchestrator — all the real work happens in two protected helpers, which the mechanic runs in order. It runs at **depth 0**, so it delegates the mechanical helper work to the `fls:sdd-mechanic` (Haiku) agent and handles any user input itself. See the `claude-code-authoring` skill for the model behind this.

## Step 1: Set up the todo list

Delegate to `fls:sdd-mechanic`: have it run the steps in `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md`. Pass through whatever the caller said about which spec or idea this is for, so the helper doesn't have to re-discover it.

Wait for the mechanic to finish. Note the path to the spec directory it landed on — Step 2 needs it. If the mechanic returns `status: blocked` (e.g. ambiguous spec dir, or an existing `todo.md`), gather the answer from the user via `AskUserQuestion` and re-spawn the mechanic with the answer.

## Step 2: Create the worktree

Delegate to `fls:sdd-mechanic`: have it run the steps in `fls-claude-plugin/commands/sdd/protected/start_worktree.md`, passing through the spec directory from Step 1.

Wait for it to finish. Handle any `blocked` return the same way as Step 1 (ask the user, re-spawn).

## Step 3: Report back

Print a short, combined summary:

- Path to the new `todo.md`.
- Path to the new worktree.
- A one-line reminder that the user should `cd` into the worktree and run `/sdd:next` to continue.
