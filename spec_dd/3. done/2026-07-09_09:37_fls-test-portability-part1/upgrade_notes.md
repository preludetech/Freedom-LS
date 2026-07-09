---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - "pyproject.toml [tool.pytest.ini_options] markers: register the new fls_internal marker"
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: fls-test-portability-part1

## Breaking changes

None to runtime code, models, templates, settings keys, or URLs. Nothing your
application code needs to change to keep working.

One test-config caveat: FLS tests are now marked with the new
`@pytest.mark.fls_internal` marker, and FLS runs pytest with `--strict-markers`.
If your downstream project collects the vendored `freedom_ls/` test subtree (the
default when `uv run pytest` finds no project-local `tests/` and falls back to
recursive collection) and your own `pyproject.toml` does **not** register
`fls_internal`, `--strict-markers` will raise a collection error on those tests.
Register the marker (see Manual steps) to avoid this.

## Manual steps

1. **Register the `fls_internal` marker** in your project's own
   `pyproject.toml`. FLS's `pyproject.toml` is not inherited by your project —
   your own file is the config source — so copy this entry into your
   `[tool.pytest.ini_options]` `markers = [...]` list:

   ```toml
   "fls_internal: marks tests that only pass under FLS's own settings, theme, branding or demo content (not portable to a concrete downstream)",
   ```

2. **Adopt the recommended pytest selection** when running your suite so FLS's
   own brand/demo and browser tests are deselected, leaving only the portable
   contract set:

   ```
   -m "not playwright and not fls_internal and not ci_only"
   ```

   Add this to your `addopts`, or pass it on the command line. (Note: a
   command-line `-m` *replaces* the `-m` in `addopts` rather than merging, so if
   you set it on the command line include the whole expression.)

No migrations, no Tailwind rebuild, no package or npm installs are required for
this upgrade.
