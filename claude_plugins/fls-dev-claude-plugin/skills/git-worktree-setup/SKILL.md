---
name: git-worktree-setup
description: FreedomLS-specific extension of the sdd:git-worktree-setup skill. Adds the FLS per-worktree install step and the per-branch database convention. Use alongside sdd:git-worktree-setup when creating or tearing down a worktree in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Git worktree setup (FreedomLS overlay)

Read `Skill(sdd:git-worktree-setup)` first for the generic worktree/bare-repo mechanics. This overlay adds **only** the FreedomLS per-worktree setup step and the per-branch database convention.

## Per-worktree setup step

Where the `sdd` core says "run the project's per-worktree setup step, if any", FreedomLS runs its install script after creating the worktree:

```bash
cd <branch-name>
.claude/fls-dev/scripts/install_dev.sh
```

`install_dev.sh` is an `fls-dev`-owned script.

## Per-branch databases

Each worktree gets its own PostgreSQL database named `db_<sanitized_branch>` (e.g. `db_main`, `db_feature_auth_flow`). This is handled automatically by `settings_dev.py`, which detects the current git branch and derives the database name.

- `.claude/fls-dev/scripts/install_dev.sh` — sets up everything for a new worktree: creates the database, runs migrations, loads demo data.
- `.claude/fls-dev/scripts/dev_db_init.sh` — creates the per-branch dev and test databases (idempotent).
- `.claude/fls-dev/scripts/dev_db_delete.sh` — drops the per-branch dev and test databases (for cleanup).
