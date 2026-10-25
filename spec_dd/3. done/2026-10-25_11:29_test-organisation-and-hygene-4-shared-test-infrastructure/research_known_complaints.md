# Research: known complaints

What do developers commonly complain about with shared test infrastructure of this kind? Web
findings come from search-result snippets only (4 searches, no page opened).

## Already recorded in this repo

Paths under `spec_dd/1. next/test-organisation-and-hygene/`.

- **Playwright wildcard re-export** (`research_test_organisation.md`, Part B, lines 124-131).
  `from freedom_ls.tests.playwright_fixtures import *  # noqa: F403` in the root conftest makes the
  Playwright-only fixtures (`logged_in_page`, `reset_local_storage`) global to every non-browser
  test, and bypasses the wildcard-import lint rule. Recommendation 7 flags it without mandating an
  answer.
- **Placement pitfalls** (`research_test_organisation.md`, lines 97-109). A fixture defined too
  shallow "pollutes the global fixture namespace and invites accidental shadowing"; too deep gets
  duplicated across siblings. Module-scope model or factory imports fail at collection and abort the
  session. Session-scoped fixtures holding mutable state break under `pytest-randomly` or `xdist`.
- **Conftest helpers** (`research_test_organisation.md`, lines 171-186). Plain helper functions in a
  conftest need a manual import, which defeats the conftest. A `reverse_url` re-export that
  "shadows" the root conftest is fragile. Rule: a conftest holds only `@pytest.fixture` fixtures
  plus underscore-prefixed private helpers; anything for manual import goes in a plain module.
- **Circular edges** (`research_test_layout_audit.md`, line 65, table 210-225): `course_access` ↔
  `course_applications`, `learner_management` ↔ `learner_progress`.
- **Missing collection guards** (`research_test_layout_audit.md`, line 256): `course_interest` and
  `course_recommendations` fail at collection when not installed.
- **Other.** A conftest that functionally shadows the root one (audit line 158); a conftest that grew
  a plain `gated_course_with_form()` function (audit line 160); factory_boy circular dependencies
  resolved with string `SubFactory` references (`research_test_organisation.md` line 43);
  `panel_framework/tests/conftest.py` (lines 151-157) is function-scoped on purpose because
  `django_db(transaction=True)` tests truncate tables and would wipe a session-scoped fixture.

## Found on the web

### Star imports and fixtures (F401/F403)

- Fixtures pulled in by a star import caused "fixture not found" errors; the workaround was to stop
  star-importing. https://forums.fast.ai/t/fixture-not-found-errors-when-fastai-star-imports-and-pytest/86085
- An Astropy issue proposes moving fixtures into `conftest.py` partly because imported fixtures
  trip F401; a maintainer preferred local fixtures for readability.
  https://lightrun.com/answers/astropy-astropy-move-pytest-fixtures-to-conftestpy
- An imported fixture with `# noqa: F401` still triggers F811 "redefinition" when used as a test
  argument. https://www.python.org/pipermail/code-quality/2017-May/000901.html
- Nothing specific found on mypy or IDE complaints.

### `pytest_plugins` in nested conftests

- pytest 4.0 made it an error: "Defining `pytest_plugins` in a non-top-level conftest is no longer
  supported" (issue #4548), because the plugins activate globally. Fix: declare in the rootdir
  conftest. https://testgitea.trustie.net/floraachy/pytest2/commit/a93f41233a8f4edadb33a055396247ef1ede210a ,
  https://doc.pytest.org/en/4.6.x/writing_plugins.html
- So nested `pytest_plugins` cannot scope Playwright fixtures; only a nested conftest that imports
  them explicitly can.

### `collect_ignore_glob`

- Only the official docs surfaced; they show a conditional `collect_ignore_glob` in a conftest, and
  `--ignore-glob`/`--deselect` as CLI alternatives.
  https://docs.pytest.org/en/9.0.x/example/pythoncollection.html
- Unconfirmed: whether globs resolve relative to the conftest, and behaviour on no match.
- Mitigation: check with `pytest --collect-only -q` that the guard drops only the intended tests
  when the app is absent and still collects them when present.

### Playwright with pytest-django

- Playwright's sync API creates an asyncio loop that conflicts with Django's
  `SynchronousOnlyOperation` check during DB setup/teardown; pytest-asyncio beside pytest-playwright
  can make plain sync tests raise it. The write-up's `DJANGO_ALLOW_ASYNC_UNSAFE` workaround only
  silences the check.
  https://glama.ai/mcp/servers/@phainestai/mimir/blob/57b4bd723178bc90e03a81bc075cee148dbf5262/docs/architecture/PLAYWRIGHT_E2E_SOLUTION.md
- Starting Playwright in `setUpClass` left a live event loop during DB teardown; fix was per-test
  start/stop. https://forum.djangoproject.com/t/modernizing-integration-testing-with-playwright-gsoc-2026/44657
- In-flight AJAX after a test can block the DB flush (`live_server` scope).
  https://github.com/pytest-dev/pytest-django/issues/454
- Proposed pytest-django PR #1223 (merge unconfirmed) restricts async tests using `db` to one
  thread. https://gh.nn.ci/pytest-dev/pytest-django/pull/1223.patch
- Nothing found on pytest-playwright fixtures slowing non-browser runs. Inference: pytest-playwright
  browser fixtures are session-scoped and lazy, so the cost is namespace, not browser launches.

### Not found

Giant "magic" root conftests (only hint: `pytest --fixtures` shows definition sites), scattered
factory_boy factories, moving test helpers breaking downstream projects.

## Implications

- Prefer a nested conftest under the Playwright-only directories that imports fixtures by name:
  avoids the global namespace and the F403 `noqa`.
- Do not use nested `pytest_plugins`.
- Moving `SiteFactory` breaks downstream imports from `accounts.factories`; record it for
  downstream projects.
- Verify the new `collect_ignore_glob` guards with `--collect-only` in both installed and
  not-installed cases.

status: ok
