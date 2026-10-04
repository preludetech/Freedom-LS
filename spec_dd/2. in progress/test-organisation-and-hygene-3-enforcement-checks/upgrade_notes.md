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

# Upgrade notes: test-organisation-and-hygene-3-enforcement-checks

## Breaking changes

None. The `freedom_ls` package is unchanged: no models, templates, settings, URLs or runtime
dependencies changed.

## Manual steps

None. Nothing needs doing after pulling.

This change adds three pre-commit hooks and CI steps that check FLS's own test organisation:
`app-map-fresh`, `lint-imports` and `test-mirroring`. They live in this repository's
`.pre-commit-config.yaml` and `.github/workflows/tests.yml` and do not run in a downstream project.
`import-linter` was added to FLS's `dev` dependencies only, so a downstream install does not
pull it in.

A downstream project that uses the `django-stack` plugin's
`claude_plugins/django-stack/scripts/generate_app_map.py` (the `/ds:app_map` command) keeps the
old header, legend and edge rules unless it adds a `[tool.test_organisation]` table to its own
`pyproject.toml`. The new `--check` option writes nothing and exits 1 when a file the script
would write is out of date.
Opting in to the enforcement checks is optional. `claude_plugins/django-stack/resources/testing.md`
and `docs/app_conventions.md` describe how.
