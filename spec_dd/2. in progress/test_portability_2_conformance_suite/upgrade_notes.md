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

# Upgrade notes: FLS conformance suite (`freedom_ls.contrib.conformance`)

## Breaking changes

None. This change only adds a new opt-in package (`freedom_ls/contrib/conformance/`) plus a shared test guard and a ruff per-file-ignore entry. It touches no models, settings keys, templates, URLs, or dependencies, so pulling it changes nothing about how an existing downstream project runs. Nothing new is auto-activated: the suite is an importable module, not a pytest plugin, so it stays inert until a downstream explicitly imports it.

## Manual steps

Migrating requires no action — everything below is optional, and describes how to start using the new suite.

To opt your downstream project into the conformance suite, add a test module that imports it, e.g.:

```python
# tests/test_fls_conformance.py  (in your downstream project)
from freedom_ls.contrib.conformance import *  # noqa: F401,F403
```

or, to avoid shadowing same-named tests, the collision-safe form:

```python
from freedom_ls.contrib import conformance

test_fls_namespace_reverses = conformance.test_fls_namespace_reverses
test_reference_url_reverses = conformance.test_reference_url_reverses
test_configured_backend_instantiates = conformance.test_configured_backend_instantiates
test_active_theme_resolves = conformance.test_active_theme_resolves
test_active_icon_set_resolves = conformance.test_active_icon_set_resolves
test_migration_state_consistent = conformance.test_migration_state_consistent
```

Once imported, `pytest` runs the suite against your project's real settings. It verifies FLS URL wiring reverses, the configured `COURSE_ACCESS_BACKEND` loads and instantiates, the active theme and icon set resolve, the sitemap/robots wiring is present, and your migration state is consistent. It needs no database connection or network access.

The suite only checks the FLS pieces you kept:

- Probes for an FLS app you removed from `INSTALLED_APPS` **skip** rather than fail.
- If you keep an FLS app but customise one of its internal routes, prune that individual probe (skip, not fail) with `conformance.drop("student_interface:courses")` — call it before collection (e.g. in your `conftest.py`). Contract-tier routes that other FLS code depends on cannot be pruned and still hard-fail if they don't reverse.
- The `sitemap` and `robots_txt` reference-URL probes are required: replicate FLS's reference sitemap/robots wiring in your project root, or these fail.
