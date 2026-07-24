---
name: git-worktree-setup
description: FreedomLS-specific extension of the sdd:git-worktree-setup skill. Adds the FLS per-worktree install step and the per-branch database convention. Use alongside sdd:git-worktree-setup when creating a worktree in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Git worktree setup (FreedomLS overlay)

Read `Skill(sdd:git-worktree-setup)` first for the generic worktree/bare-repo mechanics. This overlay adds **only** the FreedomLS per-worktree setup step and the per-branch database convention.

## Per-worktree setup step

FreedomLS binds the `sdd` **Setup script** (declared in `.claude/sdd/config.md`) to its own `.claude/fls-dev/scripts/install_dev.sh` — an `fls-dev`-owned script that provisions everything a new worktree needs: it creates the per-branch database, runs migrations, and loads demo data. The `sdd` core runs the configured Setup script from inside the worktree after creating it (see `Skill(sdd:git-worktree-setup)`); run it the same way yourself after a fresh clone.

## Per-branch databases

Each worktree gets its own PostgreSQL database named `db_<sanitized_branch>` (e.g. `db_main`, `db_feature_auth_flow`). `settings_dev.py` derives this name automatically from the current git branch, and `install_dev.sh` creates it.
