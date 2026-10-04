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

# Upgrade notes: fls-content-plugin-extendable

## Breaking changes

None. This change touches only the `fls-content` Claude Code plugin and the docs. No models,
templates, settings, packages or Tailwind sources changed.

## Manual steps

None required. Existing content repos keep working unchanged: with no declarations, the plugin
behaves as before.

Optional, for concrete projects that add custom content widgets: content authors can now declare
them so the `fls-content` plugin treats them as valid widgets. Add one file per widget in the content
repo at `.claude/fls-content/widgets/c-<name>.md`. The file format and validity rules are in
`claude_plugins/fls-content/skills/widget-reference/resources/custom-widgets.md`, and
`docs/how tos/custom-content-widgets.md` ("Telling your authors") gives a worked example. A
declaration whose name matches a built-in widget is ignored. Authors need the updated
`fls-content` plugin for declarations to take effect.
