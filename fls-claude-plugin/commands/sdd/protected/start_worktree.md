---
description: Helper — make a worktree for the current spec
allowed-tools: Bash, Read, Glob, Skill
---

This is a helper command, invoked by `/sdd:start`. It prepares a new git worktree so that work on a spec can happen in isolation.

By the time this helper runs, the spec must already have been moved to `spec_dd/2. in progress/` and
that move committed on the current branch — that is the job of the prior `/sdd:start` step
(`move_spec_to_in_progress.md`), not this one.

Do the steps in order — each step depends on the previous one being complete.

## Step 1: Identify the current spec and check preconditions

Look at the user's input or the current branch to determine which spec directory we're working with.

The spec should be a directory inside `spec_dd/2. in progress/`. For example: `spec_dd/2. in progress/role_based_permission_system_foundations/`.

The worktree name is the spec directory's folder name (e.g., `role_based_permission_system_foundations`).

There is no need to read the spec or any other files. We just care about the name of the feature.

**Preconditions** — if either fails, do not create a worktree; **stop** and return `status: blocked`:

- The spec directory is already inside `spec_dd/2. in progress/`.
- The working tree is clean (no uncommitted changes).

## Step 2: Create the worktree

Create the worktree from the **bare repo parent directory** (not from inside an existing worktree). Never create a worktree inside an existing worktree.

The bare repo is the parent of all worktree directories. To find it, navigate one directory up from your current worktree:

```bash
cd ..  # from current worktree to bare repo
git worktree add <spec-folder-name>
```

## Step 3: Call install_dev.sh to make sure the new worktree is ready for development

```bash
cd <spec-folder-path> && .claude/fls/scripts/install_dev.sh
```

## Step 4: Report back

Print the worktree path and a one-line note that the caller (`/sdd:start`) should pick up from there.
