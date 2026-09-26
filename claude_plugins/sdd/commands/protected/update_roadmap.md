---
description: Helper — change a row's status in the spec roadmap, remove a row, and retire an effort whose last spec finished
allowed-tools: Read, Edit, Write, Glob
argument-hint: <roadmap-path> [status:"<dir>|next|in progress"] [remove:"<dir>"] …
---

This is a helper command, followed by `sdd:sdd-mechanic` on behalf of
`protected/move_spec_to_in_progress.md` and `/sdd:finish_worktree`. It does **not** decide what
happened. It reacts to what the caller says, editing single rows of the spec roadmap
(`spec_dd/1. next/roadmap.md`), keeping its "Ready to start" and "Needs work on main first" lists
true, and archiving an effort whose rows have all gone.

If `<roadmap-path>` does not exist there is nothing to do. Return `status: ok · reason: no
roadmap`. A project without a roadmap is fine.

## Arguments

- **`<roadmap-path>`** (required): the roadmap file, usually `spec_dd/1. next/roadmap.md`.
- **`status:"<dir>|<value>"`** (zero or more): set the row for `<dir>` to `<value>`, which is
  exactly `next` or `in progress`.
- **`remove:"<dir>"`** (zero or more): delete the row for `<dir>`.

At least one `status:` or `remove:` is required. If the caller passes these in prose, parse the
intent. If anything is ambiguous, stop and return `status: blocked`.

## Step 1: Validate

The file exists and is readable. Every `status:` value is one of the two literals. Otherwise stop
and say which argument is wrong.

## Step 2: Read

Read the roadmap in full and `${CLAUDE_PLUGIN_ROOT}/resources/roadmap_format.md` for the row
grammar.

## Step 3: Locate each row

A row is the single table line whose Directory cell is exactly `` `<dir>` ``. If no line matches,
note it in the report and continue with the other arguments; never guess at a near match. If more
than one line matches, stop and return `status: blocked`.

## Step 4: Apply

- `status:` rewrites the Status cell of that line and nothing else on it.
- `remove:` deletes that line.

## Step 4.5: Keep the start lists true

The "Ready to start" and "Needs work on main first" sections must never name a spec that has
started. Their bullet format is in the row grammar. If the roadmap has no "Needs work on main
first" section, skip the edits that would touch it.

- **`status:"<dir>|in progress"`**: delete the bullet for `<dir>` from both lists, if there is one.
- **`status:"<dir>|next"`**: change neither list. The next `/sdd:roadmap` puts it back.
- **`remove:"<dir>"`**: delete the bullet for `<dir>` from both lists, if there is one. Then
  find every remaining row whose Status is `next` and whose Depends on cell names `<dir>`. For
  each one, check every name in its Depends on cell against `spec_dd/3. done/*_<name>` with Glob.
  If all of them match:
  - if its Notes cell starts with `Before starting:`, add
    `` - `<its dir>`: <the precursor text, prefix dropped> `` to "Needs work on main first";
  - otherwise add `` - `<its dir>` `` to "Ready to start".

  Insert each bullet in alphabetical order, and skip it if it is already there. If a list held
  only `None.`, replace that line. If a list is left empty, write `None.`

Touch nothing else: not the graphs and not any `####` subsection. The next `/sdd:roadmap`
regenerates those.

## Step 5: Retire an emptied effort

After the removals, look at every `###` effort section. If its table has no rows left:

1. Take the text from its `###` heading up to, but not including, the next `###` or `##`
   heading.
2. Read the parent directory name from its `Parent:` line.
3. Write that text to `spec_dd/1. next/<parent>/spec-order.md`, preceded by one line:
   `Archived from the spec roadmap on <today>, when the last of its specs finished.`
4. Delete that text from the roadmap.
5. Report `effort retired: spec_dd/1. next/<parent>`. The caller moves that directory to
   `3. done/`; this helper does not.

## Step 6: Report

A few lines: which rows changed, which were not found, which start-list bullets were added or
removed, any `effort retired:` line, and a reminder that the graphs refresh on the next
`/sdd:roadmap`. End with the footer
`status: ok|failed|blocked` · `reason: <short>`.
