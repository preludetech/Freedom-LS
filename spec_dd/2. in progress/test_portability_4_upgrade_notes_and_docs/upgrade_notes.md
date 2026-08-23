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

# Upgrade notes: test_portability_4_upgrade_notes_and_docs

No FreedomLS application code changed in this release. There are no model,
template, URL, settings, dependency or Tailwind changes — nothing to migrate,
sync or rebuild.

What changed is the `fls-dev` Claude Code plugin that ships alongside FLS: the
`/update_fls` procedure your project follows to integrate an FLS update, and the
`/update_upgrade_notes` command FLS uses to author these files. Two of those
edits change what *you* run.

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
`test_portability_3_system_checks` release and are covered by its own upgrade
notes.

## Manual steps

1. **Update your `pytest` selection** wherever you keep a copy — CI workflow,
   Makefile, task runner, docs — to the five-marker form above. If you have not
   already done so from the `basic_reports` notes, also register the marker in
   your own `[tool.pytest.ini_options] markers` list.

2. **Add the conformance opt-in test file** if you do not have one. The FLS
   conformance suite is an importable module, so without a `tests/` file
   importing it your `pytest` run collects zero probes — silently, not as an
   error, so a green run tells you nothing about your wiring. `/update_fls` now
   checks for this file and writes it for you if it is missing, but you can add
   it yourself:

   ```python
   from freedom_ls.contrib.conformance import *          # simple
   # or, collision-safe (recommended):
   from freedom_ls.contrib import conformance
   test_fls_namespace_reverses = conformance.test_fls_namespace_reverses

   # Prune an internal-tier route you have customised while keeping its app:
   conformance.drop("learner_interface:courses")
   ```

3. **Nothing else.** No `migrate`, no `uv sync`, no `npm install`, no Tailwind
   rebuild, no settings to add.
