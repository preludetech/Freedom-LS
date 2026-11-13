---
name: outstanding-items
description: Put every item outstanding from the user into the spec's todo.md as an unticked checklist line before you report: a decision to make, a choice you deferred to them, a file to keep or delete, a command to run, a review to do, a failure they must handle. Use whenever a reply, final report or summary in a spec worktree leaves the user something to do, inside or outside an SDD command.
allowed-tools: Read, Edit, Bash
---

# Outstanding items go in todo.md

The user works from the spec's `todo.md`, not from the chat. An **outstanding** item that lives
only in a reply is lost in the scroll, so `todo.md` is the ledger: anything the user must do or
decide exists there, and the chat only points at it.

## What counts as outstanding

Anything that needs the user before the work is finished:

- a decision you deferred to them, or a question you asked and left open
- a file, branch or record left for them to keep, commit or delete
- a command or check only they can run
- a failure, skipped test or unmet criterion they must act on
- a review or approval the workflow waits on

A plain observation with nothing for the user to do stays in the report. A follow-up you are
about to do yourself in this session is yours, not theirs.

## Steps

1. Before you send a reply, final report or summary, list every outstanding item in it.
2. Find the spec's `todo.md`: the one beside the spec in `spec_dd/2. in progress/<spec>/` for the
   current branch. With no spec in progress, list the items at the end of the reply under
   "Outstanding for you" and stop here.
3. For each item not already in `todo.md` as an unticked line, add one with the
   `update_todo.md` helper (`${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md`):
   - marker `user`
   - `add_after:` the item the work came from when one exists, else `add:` under the section
     holding the step that raised it
   - text that stands alone: what to do, the file or record by path, and what follows from it
     ("Decide X, then Y")
4. Tick any `todo.md` item you finished in the same work.
5. Commit `todo.md` with the work it belongs to.
6. In the reply, name each item briefly and say it is in `todo.md`.

Done when every outstanding item in the reply has an unticked line in `todo.md`, and every
`todo.md` line you completed is ticked.
