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

# Upgrade notes: faster-test-runs-5-full-suite-on-github-actions

## Breaking changes

None. This change touches FLS's own test tooling and CI workflow only: no model, template,
setting, URL or runtime dependency in the `freedom_ls` package changed. `pytest-split` is a new
FLS dev dependency, used only by FLS's own GitHub Actions workflow.

## Manual steps

None. No action needed.

A downstream project that uses the `django-stack` plugin's test tiers can, if it wants, add an
optional `[tool.test_tiers.remote]` table to its `pyproject.toml` (`command`, `start_timeout_s`,
`run_timeout_s`) so the full tier runs a remote command and falls back to the local command when
the remote one is unavailable. `DS_TEST_REMOTE=off` skips the remote command. Without the table,
the full tier runs locally as before. The contract a remote command must meet is in
`claude_plugins/django-stack/resources/test_tiers.md`.
