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

# Upgrade notes: new-register-design-process

This change touches only the `sdd` Claude Code plugin (`claude_plugins/sdd/`). No application code,
model, template, setting or dependency changed, so a downstream project's running app needs no
action.

## Breaking changes

`/sdd:register_design` now takes the link of a Design Artifact in Claude (or a handoff prompt that
holds one) and reads the canvas through the `Artifact` tool. It no longer uses `DesignSync` or
`/design-login`, and a `claude.ai/design/p/` project link is refused. Downstream teams that register
designs need edit access to the Design Artifact they register.

Existing `design.md` files written by the older command stay valid: later SDD steps still read them.

## Manual steps

None. A spec with an old-format handoff prompt that has not been registered yet needs its
`design_prompt.md` to hold the Design Artifact link before `/sdd:register_design` runs on it. See
"Registering a design" in `claude_plugins/sdd/commands/README.md`.
