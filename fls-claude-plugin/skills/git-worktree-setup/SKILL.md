---
name: git-worktree-setup
description: Reference this skill whenever you need to understand the worktree setup for this project.

---

# Git Worktree Structure

The project uses a **bare repository** layout:

- The bare repo is the parent directory of all worktree directories
- Each worktree is a sibling directory (e.g., `main/`, `some-feature/`)
- Each worktree has a `.git` **file** (not directory) pointing to its git dir

To create a new worktree:
```bash
cd .. # navigate to the bare repo (parent of current worktree)
git worktree add <branch-name>
cd <branch-name>
.claude/fls/scripts/install_dev.sh
```

## Per-Branch Databases

Each worktree gets its own PostgreSQL database named `db_<sanitized_branch>` (e.g., `db_main`, `db_feature_auth_flow`). This is handled automatically by `settings_dev.py` which detects the current git branch and derives the database name.

- `.claude/fls/scripts/install_dev.sh` — sets up everything for a new worktree: creates the database, runs migrations, loads demo data
- `.claude/fls/scripts/dev_db_init.sh` — creates the per-branch dev and test databases (idempotent)
- `.claude/fls/scripts/dev_db_delete.sh` — drops the per-branch dev and test databases (for cleanup)
