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

# Upgrade notes: full-test-run-still-too-often

This change touches only the development tooling under `claude_plugins/django-stack/` and
`claude_plugins/sdd/`. No FLS app, model, template, setting or package changes.

## Breaking changes

None.

## Manual steps

No action needed.

A project that uses the `ds` test selector (`claude_plugins/django-stack/scripts/select_tests.py`)
gets two optional changes:

- `[tool.test_tiers]` in `pyproject.toml` accepts a new optional key, `dependency_files`: a list
  of globs whose change forces the `full` tier whichever side changed them. The built-in list is
  `pyproject.toml`, `uv.lock`, `.python-version`, `package.json` and `package-lock.json`. Leave
  the key out unless the project has another file of that kind.
- `pyproject.toml` and `uv.lock` moved from the selector's built-in escalation list to that
  dependency-file list. They still force `full`, so no project config changes. An `escalation`
  glob in `[tool.test_tiers]` now behaves differently for a path main brought in during a rebase:
  it selects the tests of the apps the branch changed or imports and of the path's own app, or
  nothing when that app neither is one of those nor imports one, not the whole suite. A file
  that must force `full` even when only main changed it belongs in `dependency_files`.
