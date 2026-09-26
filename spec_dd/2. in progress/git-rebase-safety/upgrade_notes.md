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

# Upgrade notes: git-rebase-safety

This change touches only the Claude Code plugins under `claude_plugins/` (`ds`, `sdd`, `fls-dev`).
Nothing under `freedom_ls/` changed. There are no models, templates, Django settings, Python or npm
packages, or Tailwind sources to update. A downstream project that does not use these plugins has
nothing to do.

## Breaking changes

`/ds:rebase_main` behaves differently:

- If the worktree has uncommitted changes, it commits them as `<branch>: wip before rebase onto main`
  instead of stopping.
- Before rewriting the branch, it moves a backup branch, `rebase-backup/<branch>`, to the current tip.
- If the branch has an upstream, it force-pushes (`--force-with-lease --force-if-includes`) without
  asking, once tests and pre-commit pass.
- Its lost-change step runs `.claude/ds/scripts/rebase_lost_change_check.sh`. That wrapper only
  exists after `/ds:init` has been re-run. Without it, `/ds:rebase_main` fails at that step.

## Manual steps

1. Re-run `/ds:init`, `/sdd:init` and `/fls-dev:init`. They add what is missing and never overwrite
   existing files or values:
   - `/ds:init` installs `.claude/ds/scripts/rebase_lost_change_check.sh` and adds a
     `## Rebase Scripts` section with a blank `Rebuild script` key to `.claude/ds/config.md`.
   - `/sdd:init` adds a `## Rebase Hooks` section with blank `Rebase command` and `Front-end check`
     keys to `.claude/sdd/config.md`.
   - `/fls-dev:init` installs `.claude/fls-dev/scripts/rebuild_after_rebase.sh`, which runs
     `uv sync`, `npm i` and `npm run tailwind_build`.
2. Optional: turn on the rebase that runs before each feature-branch SDD step by filling in the new
   keys. While the values are blank, the pre-step rebase is skipped and SDD commands work as they
   did before. `<PLUGINS_ROOT>` is the value in your `claude.sh`:
   - `.claude/ds/config.md`: `- Rebuild script: .claude/fls-dev/scripts/rebuild_after_rebase.sh`
   - `.claude/sdd/config.md`:
     `- Rebase command: <PLUGINS_ROOT>/claude_plugins/django-stack/commands/rebase_main.md`
   - `.claude/sdd/config.md`:
     `- Front-end check: <PLUGINS_ROOT>/claude_plugins/fls-dev/commands/protected/frontend_check.md`
3. Optional: to stop permission prompts for the upstream-change scan, add
   `"Bash(<PLUGINS_ROOT>/claude_plugins/sdd/scripts/upstream_change_scan.sh:*)"` to
   `permissions.allow` in `.claude/settings.json`. Leave out the `<PLUGINS_ROOT>/` prefix when
   `PLUGINS_ROOT` is `.`. No init command adds this entry.
