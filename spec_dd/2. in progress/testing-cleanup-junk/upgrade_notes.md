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

# Upgrade notes: testing-cleanup-junk

This change only touches FLS's own test suite, CI and developer tooling. No models, templates,
settings, URLs or dependencies changed.

## Breaking changes

None.

The shipped test helpers under `freedom_ls/tests/` keep their module paths. This change adds three
modules beside them (`site_context.py`, `playwright_helpers.py`, `demo_content_fixtures.py`). The
root-conftest fixture `mock_site_context` and the function `reverse_url` keep their names and
behaviour.

## Manual steps

- **Exclude the new `dev_tooling` marker from your run of the portable FLS tests.** The shipped
  tests of QA seeders and `danger_` commands (in `freedom_ls/dev_tools/tests/` and
  `freedom_ls/qa_helpers/tests/`) now carry `pytest.mark.dev_tooling`. The portable filter
  becomes:

  ```bash
  uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint and not dev_tooling"
  ```

  `/fls-dev:update_fls` already uses this string. Update any CI job or script of your own that
  hard-codes the old one.
- **If your project runs pytest with `--strict-markers` and registers FLS's markers in its own
  pytest config**, add `dev_tooling` to that list. Otherwise collecting those FLS tests fails with
  an unregistered-marker error.

Many browser and markup tests were also merged or deleted, so the portable set is smaller than
before. You don't need to do anything about that.
