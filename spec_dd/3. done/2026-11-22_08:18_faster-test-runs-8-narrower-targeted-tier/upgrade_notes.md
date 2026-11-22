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

# Upgrade notes: faster-test-runs-8-narrower-targeted-tier

## Breaking changes

None. This change touches only the `django-stack` plugin's test selection
(`claude_plugins/django-stack/scripts/select_tests.py`) and FLS's own `[tool.test_tiers]` table.
No model, template, setting or package changes.

## Manual steps

None. No action needed.

Optional: a project that uses the `django-stack` plugin's test tiers can opt in to narrow selection
by adding `narrow = true` to `[tool.test_tiers]` in its own `pyproject.toml`. It is off when the key
is absent. With it on, a targeted run selects the changed module's app tests plus the test files
that import it, rather than every app that imports the app. `select_tests.py --wide` ignores the
setting for one run. See `claude_plugins/django-stack/resources/test_tiers.md` for what narrow
selection leaves to the full run.
