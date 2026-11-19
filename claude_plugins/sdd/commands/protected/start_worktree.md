---
description: Helper — make a worktree for the current spec
allowed-tools: Bash, Read, Glob, Skill
---

This helper, invoked by `/sdd:start`, makes a new git worktree for a spec. The spec must already have
been moved to `spec_dd/2. in progress/` and that move committed on the current branch, by the prior
`/sdd:start` step (`move_spec_to_in_progress.md`), not this one.

Do the steps in order; each depends on the previous one being complete.

## Step 1: Identify the current spec and check preconditions

Look at the user's input or the current branch to find the spec directory.

The spec should be a directory inside `spec_dd/2. in progress/`. For example: `spec_dd/2. in progress/role_based_permission_system_foundations/`.

The worktree name is the spec directory's folder name (e.g., `role_based_permission_system_foundations`).

Do not read the spec or any other files; only the feature name matters.

**Preconditions** — if either fails, do not create a worktree; **stop** and return `status: blocked`:

- The spec directory is already inside `spec_dd/2. in progress/`.
- The working tree is clean (no uncommitted changes).

## Step 2: Create the worktree

The new worktree is a sibling of the current one: the bare repo is the parent of all worktree
directories. Run this from inside the current worktree, with an absolute path and the current
branch as the base:

```bash
parent="$(dirname "$(git rev-parse --show-toplevel)")"
git worktree add -b <spec-folder-name> "$parent/<spec-folder-name>" HEAD
```

Never `cd ..` first.

## Step 3: Prepare the new worktree for development

Read **Setup script** under `## Worktree Scripts` in `.claude/sdd/config.md` (`config.local.md` wins):

- If **Setup script** is a non-blank path, run that script from inside the new worktree.
- If it is blank, or the config file / section is absent, skip this step — this project has no per-worktree setup step.

```bash
cd "$parent/<spec-folder-name>"   # then run the configured Setup script, if any
```

## Step 4: Report back

Print the worktree path and a one-line note that the caller (`/sdd:start`) should pick up from there.
