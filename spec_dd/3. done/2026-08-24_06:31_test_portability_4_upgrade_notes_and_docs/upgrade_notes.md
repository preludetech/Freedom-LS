---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - "[tool.pytest.ini_options] addopts"   # hard: marker selection must gain `not weasyprint`
  - "[tool.pytest.ini_options] markers"   # hard: `weasyprint` must be registered under --strict-markers
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: test_portability_4_upgrade_notes_and_docs

No FreedomLS application code changed in this release. There are no model,
template, URL, Django-settings, dependency or Tailwind changes — nothing to
migrate, sync or rebuild.

What changed is the `fls-dev` Claude Code plugin that ships alongside FLS: the
`/update_fls` procedure your project follows to integrate an FLS update, and the
`/update_upgrade_notes` command FLS uses to author these files. Two of those
edits change what *you* run.

`requires_settings_change` is set for this release even though no Django setting
moves. The keys in `changed_settings` are your project's own
`pyproject.toml` `[tool.pytest.ini_options]` entries, not anything under
`config/` — they are flagged so this spec cannot be integrated without the
operator seeing manual step 1 below.

## Breaking changes

**The documented downstream `pytest` selection is now five markers, not four.**
Every copy under `claude_plugins/fls-dev/` now reads:

```
uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"
```

The `weasyprint` marker arrived with the `basic_reports` release (2026-08-21) and
marks the FLS tests that actually call `write_pdf()`. If you kept the old
four-marker string in your CI config, Makefile or README, you are collecting
those tests: they need Pango/cairo/gdk-pixbuf/HarfBuzz to pass, and with
`--strict-markers` an unregistered `weasyprint` marker is a hard **collection**
error rather than a test failure. This corrects plugin docs that were left stale
by that release; the marker itself is not new.

Nothing else here is breaking. The `manage.py check` step added to `/update_fls`
runs checks that already existed — Django runs the full check set inside
`migrate` and `makemigrations` too, so the step changes attribution and warning
visibility, not what passes. The check-ID changes it can surface
(`freedom_ls_course_access.E001`'s repurposing, and the new `.E003` /
`freedom_ls_learner_interface.W001`) shipped with the earlier
`2026-08-23_16:23_fls-integration-system-checks` release and are covered by its
own upgrade notes.

## Manual steps

1. **Update your `pytest` selection** wherever you keep a copy — CI workflow,
   Makefile, task runner, docs — to the five-marker form above. If you have not
   already done so from the `basic_reports` notes, also register the marker in
   your own `[tool.pytest.ini_options] markers` list.

2. **Add the conformance opt-in test file** if you do not have one.
   `/update_fls` now checks for this file and writes it for you if it is
   missing, but you can add it yourself:

   ```python
   # tests/test_fls_conformance.py
   from freedom_ls.contrib.conformance import *  # noqa: F401,F403
   ```

   If you have same-named tests of your own to avoid shadowing, use the
   collision-safe form instead — binding **all six** probes, since any you leave
   out simply never run:

   ```python
   from freedom_ls.contrib import conformance

   test_fls_namespace_reverses = conformance.test_fls_namespace_reverses
   test_reference_url_reverses = conformance.test_reference_url_reverses
   test_configured_backend_instantiates = conformance.test_configured_backend_instantiates
   test_active_theme_resolves = conformance.test_active_theme_resolves
   test_active_icon_set_resolves = conformance.test_active_icon_set_resolves
   test_migration_state_consistent = conformance.test_migration_state_consistent
   ```

   Pruning a probe for a route you have customised (`conformance.drop(...)`)
   is a separate, optional decision — put it in your `conftest.py`, not in the
   file above.

   Why bother, when the probes are probably running already? If your `pytest`
   run recurses into the vendored `submodules/Freedom-LS` tree — the default —
   it collects `freedom_ls/contrib/conformance/test_*.py` directly, so the suite
   runs either way. That is incidental rather than a contract: it depends on a
   collection scope you can change at any time, and if you later point
   `testpaths` at your own `tests/` dir the conformance signal vanishes with no
   error. The opt-in file makes it intentional and stable under either scope.

3. **Nothing else.** No `migrate`, no `uv sync`, no `npm install`, no Tailwind
   rebuild, and nothing to add under `config/`.
