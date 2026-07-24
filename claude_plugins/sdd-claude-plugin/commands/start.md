---
description: Initialise an SDD workflow — create the todo.md checklist next to the spec or idea, then create an isolated git worktree for the work
allowed-tools: Read, Write, Glob, Bash, Skill, Agent
---

This command kicks off Spec-Driven Development for a new spec. It is a thin orchestrator.

## Step 1: Set up the todo list

Delegate to `sdd:sdd-mechanic`: have it run the steps in `claude_plugins/sdd-claude-plugin/commands/protected/setup_todo_list.md`. Pass through whatever the caller said about which spec or idea this is for, so the helper doesn't have to re-discover it.

Wait for the mechanic to finish. Note the path to the spec directory it landed on — later steps need it. If the mechanic returns `status: blocked` (e.g. ambiguous spec dir, or an existing `todo.md`), gather the answer from the user via `AskUserQuestion` and re-spawn the mechanic with the answer.

## Step 2: Move the spec to "in progress" and commit

Delegate to `sdd:sdd-mechanic`: have it run the steps in `claude_plugins/sdd-claude-plugin/commands/protected/move_spec_to_in_progress.md`, passing through the spec directory from Step 1.

This moves the spec into `spec_dd/2. in progress/` and commits the move (along with the `todo.md` from Step 1) on the **current** branch — before any worktree exists. Wait for it to finish and confirm the working tree is clean and the move is committed before continuing. Handle any `blocked` return the same way as Step 1 (ask the user, re-spawn).

## Step 3: Create the worktree

Delegate to `sdd:sdd-mechanic`: have it run the steps in `claude_plugins/sdd-claude-plugin/commands/protected/start_worktree.md`, passing through the spec directory (now under `spec_dd/2. in progress/`).

Only run this **after** Step 2's commit has landed on the current branch — the new worktree must branch off a clean, up-to-date branch that already contains the move. Wait for it to finish. Handle any `blocked` return the same way as Step 1 (ask the user, re-spawn).

## Step 4: Report back

Print a short, combined summary:

- Path to the new `todo.md`.
- Path to the new worktree.
- A one-line reminder that the user should `cd` into the worktree and run `/sdd:next` to continue.
