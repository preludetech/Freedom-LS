# Research: best practices for a standalone, reusable Django app

Scope: the seven practices the spec needs. Decisions in `answers.md` are taken and not reopened. Each section says what the practice is, then what it means for this spec. Sources marked (fetched) were read for this research. Sources marked (background) are general knowledge and were not re-fetched.

## 1. Deprecating and renaming settings for one release

- Django's own policy is that a deprecated feature keeps working, warns for at least one release, and is then removed. The warning names the release that removes it. (fetched) https://docs.djangoproject.com/en/5.2/internals/release-process/#internal-release-deprecation-policy
- Python hides `DeprecationWarning` unless the code that triggers it is in `__main__`. `FutureWarning` is shown by default. So a plain `DeprecationWarning` from a settings read inside a library is invisible to a host operator. (fetched) https://docs.python.org/3/library/warnings.html
- Settings are static configuration. A system check is the better channel for them, because `manage.py check`, `runserver` and `migrate` show it, and the host can silence it with `SILENCED_SYSTEM_CHECKS`. The user has chosen this already: `icons.W0xx` per old name that is set. (fetched) https://docs.djangoproject.com/en/5.2/topics/checks/
- Check ids follow `<app_label>.<E|W><nnn>`. The ids are the silencing key, so treat them as public API once shipped. Keep the existing ids and add new warning ids with fresh numbers, never reusing one.

Actionable:
- Keep one table `{old_name: new_name}` in `config.py`. The settings reader looks up the new name first, then the old name. The new name wins when both are set.
- The check reads `settings` directly (via `hasattr`/`getattr` on the old name) and emits one `Warning` per old name set. The message names the replacement and the removal tag. Add a `hint` with the exact new line.
- Do not also emit a runtime `warnings.warn` on every read. The check is the single announcement, which settles the "once vs each read" open question (once, at check time). If a runtime warning is wanted for non-check paths, use `FutureWarning` or a custom `DeprecationWarning` subclass, called once per process.
- Test it: set only the old name (value is used, check warns), set both (new wins, check still warns), set neither (no warning). Use `pytest`'s `settings` fixture and `django.core.checks.run_checks`.
- When the old and new name are both present, say so in the warning text, so the host knows the old one is dead weight.

## 2. App-prefixed flat settings

- The convention in reusable apps is a flat, upper-case, app-prefixed name per setting (`CORS_ALLOWED_ORIGINS`, `DEBUG_TOOLBAR_CONFIG` is a nested exception, `ACCOUNT_*` in allauth, `CELERY_*`). Flat names are greppable, overridable per environment, and work with `override_settings`/`settings` fixture without deep-merging dicts. (background) https://docs.djangoproject.com/en/5.2/topics/settings/ (fetched pattern in Django's own `SESSION_*`, `CSRF_*` families)
- Defaults live in the app, not in the host's settings. Read through a small helper with a default per name, evaluated at use time, not import time, so tests can change settings.
- Validate at startup via checks, not by raising at import. Matches the decision that a missing `SEMANTIC_ICONS_ICONIFY_DIR` is a check error.

Actionable:
- The app's own `AppSettings` copy takes prefix `SEMANTIC_ICONS_` and a defaults dict (`SET="heroicons"`, `OVERRIDES={}`, `BACKEND=None`, `ICONIFY_DIR=None`).
- Do not read `BASE_DIR`. Treat `ICONIFY_DIR` as `str | Path | None`.
- Never cache settings values at import time. Only cache the parsed icon data, behind the public cache clear (section 6).

## 3. Shipping vendored third-party data with licence notices

- Include non-Python files through `package_data` (or `include_package_data` plus `MANIFEST.in`). Without it a built wheel silently omits the JSON. Read them with `importlib.resources.files()`, not `__file__` paths, so zipped installs work. Keep package files read-only. (fetched) https://setuptools.pypa.io/en/latest/userguide/datafiles.html
- Spec 3 owns the build, but spec 1 must lay the data out so it can be included: data inside the package directory, a single `data/` subtree, no files outside the package. Note it in the spec so spec 3 adds the `package_data` glob (`icons/data/**/*`) and checks the wheel contents.
- Licence practice: MIT and ISC require the copyright and permission notice to travel with copies of "substantial portions". A subset is still a portion, so ship each set's licence text beside its data. Copy upstream `LICENSE` files verbatim (the Lucide file carries the Feather MIT notice). Add a short top-level `NOTICE`/`THIRD_PARTY_LICENSES` index in the data directory listing set, upstream package, version, licence, and source URL. (background) https://opensource.org/license/mit and https://opensource.org/license/isc
- Python packaging metadata can carry licence files too (PEP 639 `license-files`), but this is spec 3's job. Mention only that the files must be under paths the build can glob. (background) https://peps.python.org/pep-0639/

Suggested layout (a proposal, answers the open "on-disk layout" item):

```
freedom_ls/icons/data/
  manifest.json            # versions, generated-by, file list
  NOTICE.md                # index of sets, licences, upstream URLs
  heroicons/icons.json     # Iconify JSON subset
  heroicons/LICENSE
  lucide/icons.json  lucide/LICENSE
  tabler/icons.json  tabler/LICENSE
  ph/icons.json      ph/LICENSE      # keep the upstream package dir name `ph`, so the PACKAGE_MAP key and the ICONIFY_DIR layout match
```

Using the upstream directory names means the bundled directory and a host's `node_modules/@iconify-json` directory share one layout. The loader then has one code path with two roots.

## 4. Recording upstream versions in a manifest

- Practice: a small machine-readable file generated together with the data, never hand-edited. It is the input to the drift test and the evidence for licence notices.
- Include: schema version, generator name/path, for each set the upstream npm package name, exact version, licence SPDX id, and optionally icon count and a sha256 of the output file. Include the sorted list of icon names kept per set, so a reviewer sees a diff when the mapping changes.
- Exclude timestamps: they make regeneration non-reproducible and break the drift test. Sort keys, use stable indentation (`json.dumps(..., sort_keys=True, indent=2)` plus a trailing newline), and write Iconify JSON compactly but deterministically.
- Pin: the generator reads the version from the installed `node_modules/@iconify-json/<pkg>/package.json`. The `package.json` `devDependencies` should use exact versions or the lock file pins them, so "regenerate" is repeatable.

Example manifest shape:

```json
{
  "schema": 1,
  "sets": {
    "heroicons": {"package": "@iconify-json/heroicons", "version": "1.2.3", "license": "MIT", "icons": 118, "sha256": "..."}
  }
}
```

(Sizes and counts must be measured by the generator, per the idea.)

## 5. A drift test proving vendored data matches the generator

Common pattern (generated files such as protobuf stubs, OpenAPI clients, lockfiles in CI): regenerate in memory and compare to what is committed.

- Because the generator is Python and its subset function is pure (`subset(iconify_data: dict, names: set[str]) -> dict`), the drift test can run without Node. It needs the full upstream data to regenerate, which only exists with `node_modules`. Two layers fix that:
  1. Always-on test (no Node): load each committed `icons.json`, assert the set of icon names equals the set the four mappings reference (including aliases the mappings need), assert every committed file is valid Iconify JSON, assert `manifest.json` lists the same sets and versions as the files, assert the licence file exists for each set, and assert the manifest's sha256 matches the committed file. This catches mapping edits that were not followed by regeneration.
  2. Full regeneration test: `pytest.mark.skipif` no `node_modules/@iconify-json`, or a marker selected in CI after `npm ci`. It regenerates from the pinned upstream version and compares byte-for-byte. A skipped test must be visible in the report, so the CI tier that has Node must run it for real. Do not let it skip silently in the tier that is meant to prove it.
- Compare parsed JSON for the semantic check and bytes for the formatting check, so a failure message can say "re-run `uv run python scripts/...`" and show a short diff of added or removed icon names.
- The test must derive the required icon names from the live mapping dicts, never from a second copied list.
- Put the pure function in the script module, importable by the test (decided). Give the script a `main()` and keep it import-safe with no side effects at import.

## 6. A public cache-clear API instead of private reach-ins

- Principle: anything tests and other apps need becomes a documented function. A leading underscore means "may change without notice". Django's own pattern is `cache_clear()` on `functools.lru_cache`d functions (for example `django.apps.apps.clear_cache()`, `get_user_model` helpers). (background) https://docs.python.org/3/library/functools.html#functools.cache
- Implementation options: back the loader with `functools.lru_cache` and expose `def clear_cache() -> None: _load.cache_clear()`, or keep the dict and expose the same function. Either way the public function is the only supported way to reset.
- Connect it to settings changes: listen to `django.test.signals.setting_changed` for `SEMANTIC_ICONS_*` (and the deprecated old names) and clear the cache automatically. Then host tests using `override_settings` do not need to call anything, and the FLS tests and `conftest.py` need at most one fixture. Django does exactly this for its own cached settings readers. (background) https://docs.djangoproject.com/en/5.2/ref/signals/#setting-changed
- Provide a pytest fixture in the app's conftest that calls `clear_cache()` before and after tests that change settings, so test isolation stays automatic.
- Test the cache API itself: load, change the directory setting, call `clear_cache()`, assert the new data is read.
- Also grep-test or review that nothing outside the icons package references `loader._cache` after the change.

## 7. Running a reusable app's tests under its own minimal settings

- The app ships a tiny settings module for tests only: `SECRET_KEY`, `INSTALLED_APPS` (`django.contrib.contenttypes` if needed, `django_cotton`, the app), `TEMPLATES` with cotton's loaders, `USE_TZ`, `DEFAULT_AUTO_FIELD`, and a sqlite in-memory or no database. If the app has no models, pytest-django needs no database at all, so tests should not request `db`. (background) https://pytest-django.readthedocs.io/en/latest/database.html
- pytest-django precedence is `--ds` over `DJANGO_SETTINGS_MODULE` env var over ini file. To make the app's file win, put `addopts = --ds=...` in its ini. (fetched) https://pytest-django.readthedocs.io/en/latest/configuring_django.html
- The user's decision is a separate pytest run. Two clean ways to wire that:
  1. A dedicated config file inside the app (`freedom_ls/icons/pytest.ini`, or `pyproject`-independent ini) and run `uv run pytest -c freedom_ls/icons/pytest.ini freedom_ls/icons/tests`. With `-c`, pytest takes the ini file's directory as `rootdir` and uses that file's options only, so the main config does not leak in.
  2. Keep one config and use `--ignore=freedom_ls/icons/tests` in the main `addopts` plus a second invocation with `--ds=freedom_ls.icons.tests.settings -p no:cacheprovider`. Simpler, but the main config's other options (markers, plugins, coverage, `DJANGO_SETTINGS_MODULE`) leak into the app run, so it proves less.
  Prefer option 1 for "proves standalone". The ini carries `DJANGO_SETTINGS_MODULE`, `pythonpath`, `testpaths`, and `addopts = --ds=...` so an exported env var cannot override it.
- Main suite exclusion: `--ignore=freedom_ls/icons/tests` (or `norecursedirs`/`testpaths`) in the main config. Without it a plain `uv run pytest` would import the app's tests under FLS settings and either pass vacuously or fail on conftest conflicts.
- Isolation: the app's tests directory must have its own `conftest.py` and must not import from `freedom_ls.conftest` or other FLS apps. A static test (or the existing import-check) asserts no `freedom_ls.*` import outside `freedom_ls.icons` in the app package. Note that with `freedom_ls/__init__.py` present the import name `freedom_ls.icons` still triggers `freedom_ls/__init__.py`. Keep that file empty of imports for the standalone claim to hold, and mention that the hard proof is spec 3, when the package moves out.
- Wire it into the tiers: a Makefile/script target or a pre-commit/CI entry runs both invocations, and both must be listed in `ds:testing`/`fls-dev:testing` docs. A failing second run must fail the tier.
- Common reference layouts for the same pattern (background, not fetched): django-cotton, django-filter, django-allauth and django-debug-toolbar keep a `tests/settings.py` and `runtests`-style entry or a `tox`/`nox` matrix; djangoproject's "testing reusable applications" section describes the same idea. https://docs.djangoproject.com/en/5.2/topics/testing/advanced/#testing-reusable-applications

## Pitfalls to name in the spec

- `icons.E002` text change: keep the id, change the message and hint. Update any test that matches the old message.
- Fallback "icon by icon" doubles the lookup cost for sets in the host directory. Cache the merged result per set after the first load, not per icon read.
- Iconify JSON `aliases` and `info`/`width`/`height` defaults: a subset must keep `aliases` that point at kept icons (and their parents), the set-level `width`/`height`, and drop the rest. Otherwise a kept alias renders wrong.
- `.gitattributes`: mark generated JSON as `linguist-generated` and `-diff` if large, so reviews stay readable.
- Data directory layout and the manifest are the contract that spec 3's build and spec 4's docs rely on. Fix them here.

## Sources

- https://docs.djangoproject.com/en/5.2/topics/checks/ (fetched)
- https://docs.djangoproject.com/en/5.2/internals/release-process/#internal-release-deprecation-policy (fetched)
- https://docs.python.org/3/library/warnings.html (fetched)
- https://setuptools.pypa.io/en/latest/userguide/datafiles.html (fetched)
- https://pytest-django.readthedocs.io/en/latest/configuring_django.html (fetched)
- https://docs.djangoproject.com/en/5.2/topics/testing/overview/ (fetched: caches are not cleared between tests)
- https://docs.djangoproject.com/en/5.2/topics/testing/advanced/#testing-reusable-applications (background)
- https://docs.djangoproject.com/en/5.2/ref/signals/#setting-changed (background)
- https://peps.python.org/pep-0639/ (background)
- https://opensource.org/license/mit and https://opensource.org/license/isc (background)

status: ok
