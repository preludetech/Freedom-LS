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

# Upgrade notes: faster-test-runs-10-rerun-only-failures-in-a-batch

## Breaking changes

None. The change is confined to the development tooling under `claude_plugins/` (the test runner
now prints the failed and unfinished test node IDs, and the SDD commands re-run only those after a
fix). No model, template, setting, URL or package changed.

## Manual steps

None. No action needed.
