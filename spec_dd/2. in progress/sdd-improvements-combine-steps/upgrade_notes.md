---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sdd-improvements-combine-steps

This change only touches developer tooling. Nothing changed under `freedom_ls/`, `config/`,
`pyproject.toml` or `package.json`: no models, migrations, templates, Django settings or
dependencies. A downstream project that only runs FLS has nothing to do.

What changed is the `sdd` Claude Code plugin (plus one paragraph in the `fls-dev`
`git-worktree-setup` skill). Only projects that use the SDD workflow are affected.

## Breaking changes

None for application code.

For projects that use the `sdd` plugin, some steps now chain into the next one:

- `/sdd:start` now moves the session into the new worktree, runs `/sdd:register_design` when the
  spec directory holds a `design_prompt.md`, and writes the spec with `/sdd:spec_from_idea`.
- `/sdd:implement_plan` runs into the QA command when the plan is done. With `Parallel batches`
  set to 2 or more it can run independent batches at once, in batch worktrees under
  `.claude/worktrees/`.
- `/sdd:document` now runs the documentation items in `todo.md` and then opens the pull request
  itself, ticking the `/sdd:make_pr_quickly` item in `todo.md`.

Each of these commands still works when run by hand.

## Manual steps

Only for projects that use the `sdd` plugin:

1. **Re-run `/sdd:init`.** It adds the new bits and never overwrites existing values:
   - `"worktree": {"baseRef": "head"}` in `.claude/settings.json`, when the `worktree` key is
     absent. Batch worktrees need this to branch from the feature branch.
   - The `allow` entries `Bash(git worktree list*)`,
     `Bash(git worktree remove --force .claude/worktrees/*)` and `Bash(git cherry-pick *)`.
   - A blank `Parallel batches` key under `## Worktree Scripts` in `.claude/sdd/config.md`.
   - A `.claude/worktrees/` line in `.gitignore`.
2. **Optionally set `Parallel batches`** in `.claude/sdd/config.md`. Blank or `1` keeps the old
   one-batch-at-a-time behaviour. If you set it to 2 or more, every batch worktree runs your Setup
   script, so that script must not depend on gitignored files (or you list them in
   `.worktreeinclude`), and your Teardown script must be safe to run twice.
3. **Nothing else.** No `migrate`, no `uv sync`, no `npm install`, no Tailwind rebuild.
