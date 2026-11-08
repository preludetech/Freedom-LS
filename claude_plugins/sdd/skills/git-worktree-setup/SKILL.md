---
name: git-worktree-setup
description: Reference this skill whenever you need to understand the worktree setup for this project.

---

# Git Worktree Structure

The project uses a **bare repository** layout:

- The bare repo is the parent directory of all worktree directories
- Each worktree is a sibling directory (e.g., `main/`, `some-feature/`)
- Each worktree has a `.git` **file** (not directory) pointing to its git dir

To create a new worktree, from inside the current worktree:
```bash
parent="$(dirname "$(git rev-parse --show-toplevel)")"   # the bare repo
git worktree add -b <branch-name> "$parent/<branch-name>" HEAD
cd "$parent/<branch-name>"
# then run the configured Setup script, if any (dependency install, DB creation, migrations, seed data)
```

The absolute path keeps the new worktree a sibling, never nested inside the current one, and
`HEAD` makes the current branch its base. From the bare repo itself, `git worktree add <name>`
branches off the bare repo's `HEAD` instead.

Per-worktree resources (e.g. a per-branch dev database) are set up by the project's own tooling, not
this generic skill. The setup and teardown scripts are configured under the **Worktree Scripts**
section of `.claude/sdd/config.md` (`Setup script` / `Teardown script`). Run the configured Setup
script from inside the new worktree after creating it; leave the values blank if the project has no
such step.
