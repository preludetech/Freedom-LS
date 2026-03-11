---
name: git-worktree-setup
description: Reference this skill whenever you need to understand the worktree setup for this project.

---

# Git Worktree Structure

The project uses a **bare repository** layout at `/home/sheena/workspace/lms/freedom-ls-worktrees/`:

- The bare repo stores git objects at `.git/` with worktree refs in `worktrees/`
- Each worktree is a sibling directory (e.g., `main/`, `some-feature/`)
- Each worktree has a `.git` **file** (not directory) pointing to its git dir:
  `gitdir: /home/sheena/workspace/lms/freedom-ls-worktrees/worktrees/main`

To create a new worktree:
```bash
cd .. # this assumes you are in one of the branch directories to begin with
git worktree add <branch-name>
```
