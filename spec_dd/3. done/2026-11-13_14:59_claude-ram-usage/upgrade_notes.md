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

# Upgrade notes: claude-ram-usage

## Breaking changes

None. The change is confined to the Claude Code plugins under `claude_plugins/`, this repository's
own `[tool.test_tiers.memory]` table in `pyproject.toml`, and its `.claude/` configuration. No
`freedom_ls/` code, model, template, setting or dependency changed.

## Manual steps

None. No action needed after pulling.
