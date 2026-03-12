---
description: Make a worktree for the current spec
allowed-tools: Bash, Read, Glob, Skill
---

This command prepares a new git worktree so that work on a spec can happen in isolation.

IMPORTANT! DO THE STEPS IN ORDER!

## Step 1: Identify the current spec

Look at the user's input or the current branch to determine which spec directory we're working with.

The spec should be a directory inside `spec_dd/`. For example: `spec_dd/2. in progress/role_based_permission_system_foundations/`.

The worktree name is the spec directory's folder name (e.g., `role_based_permission_system_foundations`).

There is no need to read the spec or any other files. We just care about the name of the feature.

## Step 2: Move the spec to "in progress"

If the spec directory is NOT already inside `spec_dd/2. in progress/`, move it there:

```
mv "spec_dd/0. drafts/my-feature" "spec_dd/2. in progress/my-feature"
# or
mv "spec_dd/1. next/my-feature" "spec_dd/2. in progress/my-feature"
```

DO NOT PROCEED UNTIL THE SPEC FILE IS IN PROGRESS!

## Step 3: Commit all changes

Make a git commit. DO NOT RUN PYTEST NOW.

We don't need to run pytest because we did not change any code at all. We only moved some files that are not under test. So DO NOT run the tests. Running the tests now is a waste of time.

Do not proceed to step 4 unless:
The working tree is clean (no uncommitted changes)

## Step 4: Create the worktree

ALL PREVIOUS STEPS MUST BE COMPLETE BEFORE YOU DO THIS STEP.

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
