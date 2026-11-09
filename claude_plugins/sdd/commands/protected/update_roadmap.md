---
description: Helper — refresh the spec roadmap after a spec starts or finishes, and retire an effort whose last spec finished
allowed-tools: Read, Edit, Bash, Glob
argument-hint: <roadmap-path> [remove:"<dir>"] …
---

This is a helper command, followed by `sdd:sdd-mechanic` on behalf of
`protected/move_spec_to_in_progress.md` and `/sdd:finish_worktree`. It does **not** decide what
happened; it reacts to what the caller says and to where the spec directories now sit.

If `<roadmap-path>` does not exist there is nothing to do. Return `status: ok · reason: no
roadmap`. A project without a roadmap is fine.

## Arguments

- **`<roadmap-path>`** (required): the roadmap file, usually `spec_dd/1. next/roadmap.md`.
- **`remove:"<dir>"`** (zero or more): the spec finished; delete its bullet.
- **`status:"<dir>|<value>"`** (zero or more, accepted for older callers): needs no edit. The
  script reads a spec's status from its directory's location.

## Step 1: Remove finished specs

For each `remove:"<dir>"`, delete the one line that starts `` - `<dir>` — ** `` (the bullet
grammar is in `${CLAUDE_PLUGIN_ROOT}/resources/roadmap_format.md`). If no line matches, note it
and carry on; never guess at a near match. If more than one matches, stop and return
`status: blocked`.

The script would also drop a bullet whose directory is in `3. done/`; deleting it here keeps the
helper correct when the move to done has not happened yet.

## Step 2: Run the script

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/roadmap.py "<roadmap-path>"
```

It sets every status, unblocks specs whose blockers are done, regenerates "Up next", redraws
`roadmap_diagrams/*.svg` and retires a feature with no specs left. Retiring a feature that names a
parent writes its section to `<parent>/spec-order.md` and prints
`effort retired: <parent path>`. The caller moves that directory to `3. done/`; this helper does
not.

A `PROBLEM:` line (a directory with no bullet, an unknown dependency, a cycle) is not this
helper's to fix. Relay it; the next `/sdd:roadmap` sync fixes it.

## Step 3: Report

A few lines: which bullets were removed, which were not found, the script's output verbatim
(including any `effort retired:` line), and the files changed: the roadmap and
`roadmap_diagrams/`. End with the footer `status: ok|failed|blocked` · `reason: <short>`. Script
problems alone do not make the status `failed`.
