---
description: Make a worktree for the current spec
allowed-tools: Bash, Read, Glob, Skill
---

# Create a git worktree for the current spec

This command prepares a new git worktree so that work on a spec can happen in isolation.

## Step 1: Identify the current spec

Look at the user's input or the current branch to determine which spec directory we're working with.

The spec should be a directory inside `spec_dd/`. For example: `spec_dd/2. in progress/role_based_permission_system_foundations/`.

The worktree name is the spec directory's folder name (e.g., `role_based_permission_system_foundations`).

## Step 2: Move the spec to "in progress" if needed

If the spec directory is NOT already inside `spec_dd/2. in progress/`, move it there:

```
mv "spec_dd/0. drafts/my-feature" "spec_dd/2. in progress/my-feature"
# or
mv "spec_dd/1. next/my-feature" "spec_dd/2. in progress/my-feature"
```

## Step 3: Commit all changes

Use the /commit skill to commit all current changes.

Do not proceed to step 4 unless:
- The working tree is clean (no uncommitted changes)
- All tests pass (`uv run pytest`)

## Step 4: Create the worktree

Create the worktree from the **bare repo parent directory** (not from inside an existing worktree).

The bare repo is the parent of all worktree directories. For example, if you are currently in:
```
/home/user/project-worktrees/main/
```
then the bare repo is:
```
/home/user/project-worktrees/
```

Run:
```bash
cd <bare-repo-directory>
git worktree add <spec-folder-name>
```

For example, if the spec folder is called `implement-feature`:
```bash
cd /home/user/project-worktrees/
git worktree add implement-feature
```

IMPORTANT: Never create a worktree inside an existing worktree. Always `cd` to the bare repo parent first.
