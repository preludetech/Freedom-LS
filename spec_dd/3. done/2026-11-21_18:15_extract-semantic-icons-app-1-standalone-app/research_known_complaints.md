# Research: known complaints about icon packages and reusable Django apps

Scope: complaints that map onto the decisions in `idea.md` and `answers.md`. Evidence strength is
marked per item. Searches were light (two web searches); items marked "general experience" are
widely held practice, not tied to a single cited thread.

## Sources actually consulted

- django-iconify docs/listing (needs `ICONIFY_JSON_ROOT` pointing into `node_modules`): https://socket.dev/pypi/package/django-iconify
- django-tabler-icons (separate download step, `TABLER_ICONS_DIR`): https://github-redirect.dependabot.com/demestav/django_tabler_icons
- djicons (CDN in dev, collected directory in prod, so icons must be collected before deploy): https://pypi.org/project/djicons/
- django-iconx icon packages: https://oliverhaas.github.io/django-iconx/0.2.0/getting-started/icon-packages/
- Simon Willison, pytest-django with a reusable app: https://til.simonwillison.net/django/pytest-django
- pytest-django settings precedence (`--ds` over env over ini): https://pytest-django.readthedocs.io/en/stable/configuring_django.html
- pytest-djangoapp (tooling for testing reusable apps without a host): https://github.com/idlesign/pytest-djangoapp

## Complaints, and what the spec should do

### 1. Icon libraries that need npm/node at runtime or a manual fetch step
Evidence: django-iconify needs the host to build a path into `node_modules`; django-tabler-icons
needs a `download_icons` command run per environment. "Icon not found" then shows up only in
environments where the step was skipped (CI, Docker runtime stage, pip install).
- Do: ship the bundled subset so a pip/git install renders with zero steps (already settled).
- Avoid: any fallback that silently downloads at runtime or on first render.
- Do: keep `icons.E002` wording free of `npm install`; name `SEMANTIC_ICONS_ICONIFY_DIR` (settled).
  Make the message say which set and which directory was checked, so the Docker case (First-Class
  copying `node_modules/@iconify-json`) is diagnosable.

### 2. Large vendored data bloating wheels and repos (general experience)
Full Iconify collections are tens of MB; vendoring them makes every clone, wheel and Docker layer
heavy, and diffs of regenerated data are unreviewable.
- Do: ship a subset covering only the mapped glyphs (settled); measure sizes before quoting them
  in docs (settled). Emit deterministic output (sorted keys, stable indentation, no timestamps) so
  regeneration produces a minimal git diff and the drift test is not flaky.
- Avoid: committing a full set "just in case"; pretty-printing that inflates size without need.
  Consider whether the loader reads a whole set file per request (it caches; keep it).

### 3. Stale vendored data drifting from upstream and from mappings (general experience)
Vendored copies rot: upstream renames/removes icons, or a mapping edit references a glyph not in the
subset, and it surfaces as a blank icon in production.
- Do: the drift test (bundled files equal generator output at recorded versions) plus a test that
  every glyph in all four mapping dicts exists in the bundled data, for all four sets.
- Do: the manifest records version per set and the generator refuses to run if installed
  `@iconify-json` versions differ from the recorded ones unless an explicit "update" flag is given,
  so a maintainer cannot regenerate against whatever npm happens to have installed.
- Avoid: a drift test that needs Node/npm in the default `pytest` run; it should compare against the
  pure subset function and a committed fixture, or be marked as a maintainer test. Note the answers
  say the test imports the pure function; that still needs upstream JSON, so decide whether the test
  skips when `node_modules` is absent (skips hide drift in CI) or CI installs it. Prefer failing in CI,
  skipping locally.

### 4. Missing licence notices (general experience, strongly held)
MIT/ISC require the copyright and permission notice to travel with copies. Vendored-data packages
that omit it are a recurring review/compliance complaint, and wheels frequently drop files that sit
outside the package.
- Do: put licence files inside the app directory next to the data and make sure the build includes
  them (spec 3 owns the pyproject build, but this spec should place them where package-data globs will
  catch them, and add a test asserting a licence file exists for each bundled set).
- Do: copy Lucide's LICENSE verbatim including the Feather notice (settled); keep upstream copyright
  holders' names exact; also record the source package name and version in the manifest.
- Avoid: a single merged "LICENSES" paragraph written from memory.

### 5. Renamed settings breaking silently or warning too noisily (general experience)
Silent break: after a rename the old name is ignored and the host gets defaults (here: heroicons
instead of phosphor) with no error. Noisy break: `warnings.warn` on every read floods logs and tests.
- Do (settled): read old names with a system-check warning, new name wins. Add a warning that is
  emitted by the check, not at each read, so it is silenceable via `SILENCED_SYSTEM_CHECKS`.
- Avoid: checking only "old set and new not set". Also warn when both are set (old is ignored) so the
  host knows it is dead config. Make the old name still work when only it is set, and test all
  three cases (old only, new only, both).
- Avoid: a deprecation check that only runs with `manage.py check`; the check must be registered so
  `runserver` and `migrate` run it too (settled by answers). Document that `check --deploy` is not
  needed.
- Do: treat an old `OVERRIDES` or `BACKEND` the same as `SET`; people forget the less-used ones.
- Do: the upgrade notes for First-Class state the exact old to new mapping and that removal comes after
  one tag; put the removal tag in the warning text.

### 6. Module-level caches that tests must poke privately (general experience)
Tests that do `loader._cache.clear()` couple to internals and break on refactor; hosts that override
settings in their own tests hit stale data with no public way out.
- Do: one public `clear_cache()` on the loader (settled). Also make the cache respond to
  `setting_changed` (Django's `django.test.signals.setting_changed`) for the icon settings so
  `override_settings` just works, and keep the public clear as the explicit escape hatch.
- Avoid: exposing the cache dict; avoid per-process caches keyed without the resolved directory,
  or a test using `ICONIFY_DIR` will read data cached from the bundled path.
- Do: a grep-style test or lint that nothing outside the loader references `_cache`.

### 7. Reusable apps whose tests only run inside a host project
Evidence: the pytest-django docs and Simon Willison's write-up both settle on a test settings module
in the repo plus `DJANGO_SETTINGS_MODULE`/`pythonpath` in pytest config; pytest-djangoapp exists
because the alternative is painful. Typical failures: tests rely on host `conftest.py` fixtures,
`BASE_DIR`, a host template dir, or a host `INSTALLED_APPS` that happens to include a dependency
(here `django-cotton`).
- Do: minimal settings listing only `django.contrib.contenttypes` if needed, `cotton`, and the icons
  app; its own `conftest.py`/`pytest` config with `rootdir`-local discovery.
- Watch: pytest-django precedence is `--ds` over env var over ini, and the root FLS `pytest` config
  will still apply when running from the repo root. The separate second invocation (settled) must pass
  its own `-c`/`--rootdir`/`--ds`, otherwise the FLS settings module wins silently and the "standalone"
  suite passes only because FLS is present. Add a test in the app's own run that asserts
  `settings.SETTINGS_MODULE` is the app's settings and that `freedom_ls.base` is not importable
  via `INSTALLED_APPS`.
- Watch: a root `conftest.py` above `freedom_ls/icons/tests` is still collected by pytest walking up
  from the test dir. The FLS root `freedom_ls/conftest.py` sits at `freedom_ls/`, a parent of the app,
  so it will load for the app's tests and import FLS. Either use `--confcutdir`, `--noconftest` with an
  explicit conftest, or accept the move in spec 3. Flag this as the top risk for the standalone claim.
- Do: a "no FLS import" test (scan app sources for `freedom_ls.` outside its own package, and
  run an import in a subprocess with FLS settings absent).
- Avoid: hidden dependence on the cotton template location: the app's tests must prove `<c-icon>`
  renders using only the app's templates.

### 8. Settings helper copy-paste divergence (general experience)
Copying `AppSettings` is accepted (settled), but copies drift.
- Do: record in the copy's docstring where it was copied from and keep it minimal (only what icons
  use). Do not add FLS-only behaviours. Test it standalone.

### 9. Optional external directory failure modes
From the django-iconify and django-tabler-icons pattern: a wrong path becomes "icon not found"
rather than a config error.
- Do (settled): nonexistent directory is a startup check error; missing icon falls back per icon.
- Add: accept `str` or `Path`; resolve to absolute; the check also errors when the path is a file;
  a directory that exists but has none of the four set folders gets a warning, not silence.
  Per-icon fallback should not mask a typo in `SEMANTIC_ICONS_SET` (unknown set remains an error).

## Summary of avoid/do for the spec

1. Deterministic generator output and version pinning; drift test fails in CI rather than skips.
2. Licence file presence test; files placed inside the app for the later build.
3. Deprecation as a check, covering old-only, new-only, both, and all three names.
4. Public cache clear plus `setting_changed` handling; no `_cache` outside the loader.
5. Standalone suite must not load FLS's `freedom_ls/conftest.py` or settings; prove it by test.
6. Measure sizes; do not quote estimates.

status: ok
