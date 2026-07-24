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
# then run the project's per-worktree setup step, if any (dependency install, DB creation, migrations, seed data)
```

If the project provisions per-worktree resources (e.g. a per-branch dev database), that setup lives in
the project's own tooling, not in this generic skill — run it from inside the new worktree after
creating it.
