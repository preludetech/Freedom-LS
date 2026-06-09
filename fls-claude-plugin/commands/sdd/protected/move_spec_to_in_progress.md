---
description: Helper — move the spec to "in progress" and commit, before any worktree is created
allowed-tools: Bash, Read, Glob
---

This is a helper command, invoked by `/sdd:start`. It moves the spec directory into
`spec_dd/2. in progress/` and commits that move on the **current** branch — *before* any new
worktree/branch is created. This guarantees the move lands on the current branch (e.g. `main`)
rather than on the feature branch.

Do the steps in order — each step depends on the previous one being complete.

## Step 1: Identify the current spec

Look at the caller's input or the current branch to determine which spec directory we're working with.

The spec is a directory inside `spec_dd/`, usually under `spec_dd/0. drafts/` or `spec_dd/1. next/`
at this point. For example: `spec_dd/1. next/role_based_permission_system_foundations/`.

There is no need to read the spec or any other files — we only care about the directory.

If the spec directory is ambiguous, **stop** and return `status: blocked`.

## Step 2: Move the spec to "in progress"

If the spec directory is NOT already inside `spec_dd/2. in progress/`, move it there:

```
mv "spec_dd/0. drafts/my-feature" "spec_dd/2. in progress/my-feature"
# or
mv "spec_dd/1. next/my-feature" "spec_dd/2. in progress/my-feature"
```

Do not proceed until the spec directory is in `spec_dd/2. in progress/`.

## Step 3: Commit all changes

Make a git commit with `uv run git commit` (per `CLAUDE.md`). This commit captures both the `todo.md`
created in the previous `/sdd:start` step and the directory move.

Do **not** run pytest now: we only moved files that are not under test, so running the tests would be
a waste of time.

Do not finish until the working tree is clean (no uncommitted changes). If the working tree cannot be
made clean, **stop** and return `status: blocked`.

## Step 4: Report back

Print the final spec directory path (now under `spec_dd/2. in progress/`) and a one-line note that the
caller (`/sdd:start`) should pick up from there to create the worktree.
