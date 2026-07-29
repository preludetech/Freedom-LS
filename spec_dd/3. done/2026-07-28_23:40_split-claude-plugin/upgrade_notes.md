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

# Upgrade notes: split-claude-plugin

This change touches **only Claude Code tooling**. No Django models, migrations, templates, settings,
URLs, Python packages, or npm packages changed — the FLS product runs exactly as before after
pulling. Everything below is about the developer tooling your project loads via `claude.sh`.

If your project does not use the FLS Claude Code plugin at all, there is nothing to do.

## Breaking changes

The single `fls` plugin at `fls-claude-plugin/` is gone. It is replaced by four plugins under
`claude_plugins/`:

| Old | New |
|---|---|
| `fls-claude-plugin/` (manifest `fls`) | `claude_plugins/django-stack/` (`ds`), `claude_plugins/fls-dev/` (`fls-dev`), `claude_plugins/sdd/` (`sdd`) |
| `fls-content-plugin/` | `claude_plugins/fls-content/` |

Consequences for a downstream project:

- **Slash commands are renamespaced.** `/fls:*` no longer exists. Commands are now `/ds:*` (generic
  Django/stack work), `/fls-dev:*` (FLS-product work — `do_qa`, `update_fls`, `update_template_repo`,
  …), and `/sdd:*` (the spec-driven-development workflow — `/sdd:start`, `/sdd:spec_from_idea`,
  `/sdd:implement_plan`, `/sdd:next`, …).
- **Agent names changed.** `fls:sdd-worker`/`fls:sdd-mechanic` → `sdd:sdd-worker`/`sdd:sdd-mechanic`;
  `fls:qa-data-helper` → `fls-dev:qa-data-helper`; `fls:code-reviewer` → `ds:code-reviewer`. Any of
  your own commands, agents, or docs that name these will silently fail to resolve — Claude Code does
  no cross-plugin validation.
- **The launcher changed.** `claude.sh` now sets `CLAUDE_PLUGINS_LOADED=1` (was `FLS_PLUGIN=1`), uses
  `PLUGINS_ROOT` (was `FLS_PATH`), and passes one `--plugin-dir` per plugin. The `SessionStart` hook
  in `.claude/settings.json` checks the new sentinel and **hard-stops the session** if it is unset, so
  a stale `claude.sh` and an updated `settings.json` (or vice versa) will block every session until
  both are migrated.
- **The config dir split in two.** `.claude/fls/` becomes `.claude/fls-dev/` (product config +
  `dev_db_init.sh`, `dev_db_delete.sh`, `db_recreate.sh`, `install_dev.sh`) plus a new `.claude/ds/`
  (`find_available_port.sh`, `db_clear.sh`, `kill_runserver.sh`, `fetch_pr_comments.sh`). Any script,
  Makefile, CI step, or `.claude/settings.json` permission entry that hardcodes
  `.claude/fls/scripts/…` must be repointed. In this repo the root `install_dev.sh` shim now calls
  `./.claude/fls-dev/scripts/install_dev.sh`.
- **Playwright MCP permission glob changed:** `mcp__plugin_fls_playwright__*` →
  `mcp__plugin_ds_playwright__*`. The Playwright MCP server now ships with the `ds` plugin; the
  repo-root `.mcp.json` copy was removed.
- **The `request-code-review` skill was deleted.** If you invoked it, use the `ds:code-reviewer`
  agent instead.
- **Agent memory directories were renamed:** `.claude/agent-memory/code-reviewer/` →
  `ds-code-reviewer/`, and `.claude/agent-memory/fls-qa-data-helper/` → `fls-dev-qa-data-helper/`.
  Nothing migrates these automatically — an un-renamed directory means the agent starts with empty
  memory (the old content is orphaned, not lost).
- **FLS's own Playwright tests moved** from `freedom_ls/<app>/tests/e2e/` to
  `freedom_ls/<app>/tests/playwright/`. The `playwright` pytest marker is unchanged, so
  marker-based exclusion (`-m "not playwright"`) keeps working. Only path-based references break.

## Manual steps

1. **Run the three inits, in this order** — `/ds:init`, then `/fls-dev:init`, then `/sdd:init`.
   Between them they migrate most of the above automatically: the `$FLS_PLUGIN` →
   `$CLAUDE_PLUGINS_LOADED` sentinel, `FLS_PATH` → `PLUGINS_ROOT`, the old monolith `--plugin-dir`
   line, the `.claude/fls/` → `.claude/fls-dev/` directory rename, the
   `Bash(.claude/fls/scripts/*.sh:*)` permission literals, and the per-plugin `--plugin-dir` lines,
   config dirs, wrapper scripts and `.gitignore` entries. `/ds:init` must run first because it owns
   the shared `claude.sh` skeleton and the `SessionStart` hook.

2. **Clean up what the inits deliberately leave alone.** Each init is additive and never removes
   another plugin's entries, so after running them, hand-edit:
   - `.claude/settings.json` — delete `"fls": true` from `enabledPlugins`, delete `Skill(fls:*)`, and
     delete `mcp__plugin_fls_playwright__*` (the inits add the new keys but do not remove the old).
   - `.gitignore` — delete the stale `.claude/fls/config.local.md` line.
   - `.claude/fls-dev/scripts/` — the directory rename carries the four *generic* wrappers
     (`find_available_port.sh`, `db_clear.sh`, `kill_runserver.sh`, `fetch_pr_comments.sh`) across
     with it, while `/ds:init` writes fresh copies under `.claude/ds/scripts/`. Delete the four
     duplicates from `.claude/fls-dev/scripts/`.

3. **Rename your agent-memory directories** if you have them, to preserve accumulated memory:
   `git mv .claude/agent-memory/code-reviewer .claude/agent-memory/ds-code-reviewer` and
   `git mv .claude/agent-memory/fls-qa-data-helper .claude/agent-memory/fls-dev-qa-data-helper`.

4. **Grep your project for the old paths and names** and update any hits — there is no static
   validation, so a missed reference fails silently at invoke time:
   `fls-claude-plugin/`, `fls-content-plugin/`, `.claude/fls/`, `$FLS_PLUGIN`, `FLS_PATH`,
   `Skill(fls:*)`, `fls:sdd-worker`, `fls:sdd-mechanic`, `fls:qa-data-helper`, `fls:code-reviewer`,
   `mcp__plugin_fls_playwright__`, `/fls:`.

5. **Update tool config that names the plugin directories.** In this repo the following changed; make
   the equivalent edits if your `pyproject.toml` / `.pre-commit-config.yaml` carry the same entries:
   - `[tool.pytest.ini_options] testpaths` — `fls-content-plugin` → `claude_plugins/fls-content`
   - `[tool.ruff.lint.per-file-ignores]` — `fls-content-plugin/validate/…` →
     `claude_plugins/fls-content/validate/…`
   - `[tool.mypy] exclude` — `fls-claude-plugin/` → `claude_plugins/(?!fls-content/validate)`
   - pre-commit mypy hook entry — `uv run mypy .` → `uv run mypy . claude_plugins/fls-content/validate`
     (mypy's recursive crawl skips `claude_plugins/fls-content/` because the directory name is not a
     valid Python identifier)

6. **Verify** by quitting Claude and relaunching with `./claude.sh`. If the `SessionStart` hook stops
   the session, the sentinel migration did not land — check `claude.sh` sets
   `CLAUDE_PLUGINS_LOADED=1`. Then confirm `/plugin` lists `ds`, `fls-dev`, and `sdd`.

No `manage.py migrate`, no Tailwind rebuild, no `uv sync`, and no `npm install` are needed — nothing
in this change touches models, Tailwind sources that affect output, or dependencies.
