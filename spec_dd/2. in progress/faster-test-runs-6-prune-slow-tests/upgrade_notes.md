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

# Upgrade notes: faster-test-runs-6-prune-slow-tests

## Breaking changes

None. The change touches only FLS's own tests and test tooling: two slow test modules
(`freedom_ls/messaging_policy/tests/test_policy.py` and
`freedom_ls/content_engine/tests/test_images.py`) were trimmed, and the shared test helper
`freedom_ls/messaging_policy/tests/messaging_world.py` changed with them. No model, template,
setting, URL or package changed.

## Manual steps

None, no action needed. A downstream project that imports `messaging_world.py` into its own tests
should rerun those tests after pulling.
