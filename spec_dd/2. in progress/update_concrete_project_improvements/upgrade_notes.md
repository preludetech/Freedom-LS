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

# Upgrade notes: update_concrete_project_improvements

This change touches only the `fls-dev` Claude Code plugin and FLS's own tooling. No Django code,
model, template, setting or package changed.

## Breaking changes

None.

`/fls-dev:update_fls` (`claude_plugins/fls-dev/commands/concrete/update_fls.md`) still runs inside a
concrete project and behaves the same. Its per-spec procedure now lives in
`claude_plugins/fls-dev/resources/concrete_spec_integration.md`, which it reads through the
submodule.

## Manual steps

None.
