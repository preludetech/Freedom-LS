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

# Upgrade notes: make-qa-more-efficient

This change is **entirely developer tooling**. Nothing under `freedom_ls/`, `config/`,
`pyproject.toml`, or `package.json` was touched — no models, no migrations, no templates,
no Django settings, no Python or npm dependencies. A downstream project that only *runs*
FLS needs to do nothing.

The changes are to the Claude Code plugins FLS ships (`claude_plugins/fls-dev`,
`claude_plugins/sdd`, `claude_plugins/django-stack`) and the project-level files those
plugins deploy (`.claude/settings.json`, `.claude/fls-dev/scripts/`, `.gitignore`).
Only projects that use the FLS SDD/QA workflow are affected.

## Breaking changes

None for application code.

For projects using the FLS Claude Code plugins:

- **The Playwright MCP server moved to the plugin definition.**
  `claude_plugins/django-stack/.mcp.json` is now the authoritative Playwright server
  (tools namespaced `mcp__plugin_ds_playwright__*`). Its args now include
  `--output-dir ${CLAUDE_PROJECT_DIR}/qa-screenshots --headless --isolated
  --image-responses omit --caps testing`. If your project defines its own root
  `./.mcp.json` Playwright server (namespace `mcp__playwright__*`), `/do_qa` will no
  longer bind to it — empty that definition, or both servers will start.
- **`--image-responses omit` means screenshots no longer come back inline.** Any local
  command, agent, or habit that reads a screenshot straight from the tool response must
  read it from the `qa-screenshots/` output directory instead.
- **The `Bash(rm -rf .sdd-work/)` allow entry was removed** and replaced by the
  `delete_sdd_work_files.sh` script (formerly named `qa_scratch_teardown`). If you
  hand-copied that allow entry or referenced the old script name, update it.

## Manual steps

Only for projects that use the FLS Claude Code plugins:

1. **Re-run `/fls-dev:init`.** It deploys the new wrapper scripts under
   `.claude/fls-dev/scripts/` (`qa_collect_screenshots.sh`, `qa_cleanup.sh`,
   `compress_screenshots.sh`, `delete_sdd_work_files.sh`) and merges the plugin-owned
   `allow` entries into `.claude/settings.json`. It skips files that already exist and
   never overwrites them.
2. **Check `.claude/settings.json` permissions.** `/init` merges plugin-owned entries,
   but confirm these are present — every missing one is a permission prompt (and a
   cascade-cancel risk) mid-QA-run:
   - `Bash(.claude/fls-dev/scripts/*.sh:*)`
   - `Bash(uv run python manage.py runserver:*)`
   - `Bash(uv run git revert:*)`

   Note the trust boundary this implies: the `Bash(.claude/<plugin>/scripts/*.sh:*)`
   wildcard grants prompt-free execution with arbitrary arguments to **any** `.sh` placed
   in those directories. Treat adding a script there as security-sensitive — equivalent
   to adding an allow-list entry.
3. **Add `qa-screenshots/` to your `.gitignore`.** Playwright MCP writes screenshots
   there during a QA run; `/do_qa` moves them into the spec directory afterwards.
4. **Nothing else.** No `migrate`, no Tailwind rebuild, no `uv sync`, no `npm install`.
