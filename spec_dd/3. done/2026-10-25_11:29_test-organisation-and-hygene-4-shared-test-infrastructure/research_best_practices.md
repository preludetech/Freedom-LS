# Research: best practices

Established practice for shared test infrastructure with pytest, pytest-django, pytest-playwright
and factory_boy in a reusable Django app. Fetched sources: the pytest `writing_plugins` and
`fixtures` pages and the factory_boy reference. Points marked "background" were not confirmed on a
fetched page.

## 1. Root conftest scope, wildcard re-exports, `pytest_plugins`

- **Root conftest** holds only what every test needs: autouse hygiene fixtures
  (`_disable_force_site_name`, `_isolate_media_root`), the opt-in `mock_site_context`, hooks.
  `fls-dev:testing` "Fixture placement" says the same.
- **Nested conftest** fixtures are visible only below that directory; a subdirectory fixture
  overrides a same-named parent and can call it.
  https://docs.pytest.org/en/stable/how-to/fixtures.html
- **`pytest_plugins`** in a conftest that is not the rootdir conftest is deprecated/erroring
  because "once a plugin is imported, it will affect the entire directory tree".
  https://docs.pytest.org/en/stable/how-to/writing_plugins.html
  For projects without entry points, the docs say to use `pytest_plugins` in the top-level conftest.
- **Costs of `import *` of fixtures:** the fixtures docs discourage importing fixtures into a module
  ("might change/stop working in future versions"); linters flag it (F403/F401); it hides the
  definition site; every public name comes in, and a nearer same-named fixture overrides it
  silently. Imported fixtures count as defined in the importing conftest, so the scope of
  `import *` is that conftest's tree.
- **Preferred, in order:** (1) a global, intentional set → `pytest_plugins = ["freedom_ls.tests.playwright_fixtures"]`
  in the rootdir conftest; (2) a narrow set → explicit named imports in a conftest under only the
  directories that need it (with `# noqa: F401`); (3) avoid `import *`.
- **Discoverability:** `pytest --fixtures -v` shows each fixture's defining file.
- **Playwright caveat:** pytest-playwright registers `page`, `browser` etc. via its entry point;
  only FLS wrappers (logged-in page, live-server setup) need exposing.
- **Reusable-app caveat (background):** a downstream project running its own tests doesn't
  necessarily load `freedom_ls/conftest.py`; fixtures meant for downstream reuse would be better
  shipped as an entry-point plugin. That would be new scope.

## 2. Narrowly used fixtures (`course_with_scored_quiz`, `sit_quiz`)

- Root conftest only if several unrelated apps use them.
- For a few apps: a plain shared module in `freedom_ls/tests/` (like `site_context.py`,
  `demo_content_fixtures.py`) explicitly imported by each consumer's `tests/conftest.py`.
- For one app: that app's conftest; never duplicate across apps.
- They are not thin wrappers (several factory calls plus a quiz sitting), so they stay fixtures.
- Keep function scope; session-scoped DB fixtures need `django_db_blocker` care
  (`_panel_test_tables`).

## 3. Factories for a shared model (Site)

- Factory lives with the app that owns or anchors the model. `Site` is `django.contrib.sites`, and
  `site_aware_models` is the app every site-aware app depends on, so it is the neutral home.
- A factory depends only on its own app and apps below it; upward `SubFactory` edges cause cycles.
  Dotted-path `SubFactory` strings break cycles but are a last resort.
  https://factoryboy.readthedocs.io/en/stable/reference.html
- (Background) `SiteFactory` should `django_get_or_create` on `domain` to avoid clashing with the
  migration-created `example.com` site.

## 4. Skipping tests for optional apps

- `collect_ignore_glob` in a conftest when a whole directory depends on the optional app; it stops
  collection and so avoids import errors. FLS's `app_not_installed` pattern.
- Pitfalls: ignored files never appear as skipped, so a misconfigured guard can hide tests (keep a
  CI run with every app installed); globs are relative to the conftest's directory; the conftest
  must not import the optional app at module level; a conftest inside the ignored tree never loads.
- `pytest.importorskip` / `pytest.skip(..., allow_module_level=True)` report a visible skip and suit
  a single module.
- Markers don't prevent import errors at collection.
- Use the conftest guard app-wide, the module-level skip for one-offs.

## 5. Moving `SiteFactory`

- A clean move fits: stale imports fail loudly at collection, and a re-export shim in
  `accounts/factories.py` would keep the very cross-app edge being removed.
- Downstream projects may import `freedom_ls.accounts.factories.SiteFactory`; without a shim, note
  the new path in release/upgrade notes.
- Do the move in one commit, search repo-wide for every importer, and run the suite plus the
  import and mirroring checks.

## Against the FLS testing skill

Agrees with its fixture placement, shared helpers in `freedom_ls/tests/`, and `app_not_installed`
guards. The skill says nothing about wildcard re-exports; external practice favours a root
`pytest_plugins` entry or an explicit scoped import. That is a new rule, not a contradiction.

status: ok
