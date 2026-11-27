---
name: git-worktree-setup
description: The FLS per-worktree install step, the per-branch database convention and the paired panel framework package worktree. Use alongside sdd:git-worktree-setup when creating a worktree in the FreedomLS repo, and when editing django-panel-framework alongside FLS.
allowed-tools: Read, Grep, Glob
---

# Git worktree setup (FreedomLS overlay)

Read `Skill(sdd:git-worktree-setup)` first for the worktree/bare-repo mechanics. This overlay adds **only** the per-worktree setup step and the per-branch database convention.

## Per-worktree setup step

FLS binds the `sdd` **Setup script** (declared in `.claude/sdd/config.md`) to `.claude/fls-dev/scripts/install_dev.sh`, an `fls-dev`-owned script that creates the per-branch database, runs migrations, and loads demo data. `sdd` runs the Setup script from inside the new worktree (see `Skill(sdd:git-worktree-setup)`); run it the same way yourself after a fresh clone.

## Per-branch databases

Each worktree gets its own database `db_<sanitized_branch>` (e.g. `db_main`, `db_feature_auth_flow`), plus `test_db_<branch>` and `test_db_<branch>_gwN` test databases. `settings_dev.py` derives the name from the current git branch, and `install_dev.sh` creates it. Both databases are owned by the `fls_dev` role, not `pguser`.

`dev_db_init.sh` — run by setup and by every rebase — writes a worktree stamp on `db_<branch>`: a `COMMENT ON DATABASE` recording which repository and worktree created it. `uv run python -m dev_db.stale_dbs` reads these stamps to list this repository's per-branch databases whose worktree is gone.

A batch worktree under `.claude/worktrees/` gets `db_<sanitized_branch>` and `test_db_<sanitized_branch>` for its batch branch from `install_dev.sh`, like any worktree, and `dev_db_delete.sh` drops them. `uv run python -m dev_db.stale_dbs` lists any a crashed worker left behind.

## Panel framework package worktree

`rebuild_after_rebase.sh` sources `link_panel_framework.sh`, which links the package worktree paired with the FLS worktree.

- An FLS worktree on `<branch>` links `$PANEL_FRAMEWORK_REPO/<branch>` when that worktree exists. `PANEL_FRAMEWORK_REPO` defaults to the `django-panel-framework.git` bare repo. `PANEL_FRAMEWORK_DIR` overrides the whole path. With neither, the locked tag stays in use. FLS `main` pairs with the package's `main`.
- Create the package worktree by hand: `git -C "$PANEL_FRAMEWORK_REPO" worktree add "<branch>" -b "<branch>"`. The next `rebuild_after_rebase.sh` links it.
- Set `UV_NO_SYNC=1` in your shell, and in the per-machine `.claude/settings.local.json` `env` block for agents. A plain `uv run`, the pre-commit hook's included, otherwise uninstalls the editable copy and restores the locked one.
- A new package dependency arrives only through `uv sync`. Run `rebuild_after_rebase.sh` afterwards to re-link.
- A framework change FLS needs goes one way: edit and test in the paired package worktree, tag it, then bump the pin and run `uv lock` in the same FLS change, and run the FLS suite.
- For a one-off run against a package directory, use `uv run --with-editable "<dir>" <cmd>`.
