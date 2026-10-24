# Research: reference implementations

How do reference implementations organise shared test infrastructure?

## Verified via fetch (GitHub, 2026-10)

- **Saleor, root `/conftest.py`.** A `pytest_plugins = [...]` list of dotted fixture modules:
  `saleor.tests.fixtures`, `saleor.account.tests.fixtures`, `saleor.checkout.tests.fixtures`,
  `saleor.payment.tests.fixtures`, `saleor.webhook.tests.circuit_breaker.fixtures`. Each app owns
  its own `<app>/tests/fixtures.py` and the root only lists them. It also calls
  `prepare_test_db_connections()` at import. https://github.com/saleor/saleor/blob/main/conftest.py
- **Saleor, `saleor/tests/fixtures.py`** (about 1800 lines): shared fixtures defined directly, no
  wildcard re-export. Includes autouse fixtures such as `private_media_root` and
  `clear_telemetry_data`. https://github.com/saleor/saleor/blob/main/saleor/tests/fixtures.py
- **Saleor, `saleor/tests/e2e/conftest.py`.** E2E-only fixtures (`e2e_staff_api_client`,
  `e2e_logged_api_client`, `e2e_not_logged_api_client`, `e2e_app_api_client`) live in a conftest
  scoped to the e2e directory, not the root, prefixed `e2e_`.
  https://github.com/saleor/saleor/blob/main/saleor/tests/e2e/conftest.py
- **django-oscar, `tests/conftest.py`.** Hooks only (`pytest_addoption` for `--sqlite` and
  `--deprecation`, `pytest_configure`, `pytest_unconfigure`). No fixtures, no `pytest_plugins`, no
  factory imports. https://github.com/django-oscar/django-oscar/blob/master/tests/conftest.py
- **django-oscar, `src/oscar/test/factories/__init__.py`.** Factories are a shipped package split
  by domain (`address`, `basket`, `catalogue`, `customer`, `offer`, `order`, `partner`, `payment`,
  `voucher`, `wishlists`, `contrib`). The `__init__` star-imports each submodule so callers use one
  import path, and adds `create_*` helpers.
  https://github.com/django-oscar/django-oscar/blob/master/src/oscar/test/factories/__init__.py
- **Wagtail, `wagtail/test/utils/__init__.py`.** Star-imports `decorators`, `page_tests` and
  `wagtail_tests` with `# NOQA: F403`. Test helpers ship inside the package at `wagtail/test/`.
  https://github.com/wagtail/wagtail/blob/main/wagtail/test/utils/__init__.py
- **pytest-playwright docs** (https://playwright.dev/python/docs/test-runners) only label example
  snippets as `conftest.py`; they give no layout guidance for custom fixtures.

## Not verified (recollection, not fetched)

The Wagtail root `conftest.py` URL returned 404; Sentry, Zulip and pretix were not fetched.

- Sentry puts fixtures in `sentry.testutils.pytest.*` modules and loads them through a
  `pytest_plugins` list in the root `conftest.py`.
- Wagtail has no root pytest-fixture layer; it uses Django `TestCase` and `wagtail.test.*` helper
  apps.
- pytest-django recommends fixtures in `conftest.py` and discourages star re-exports.

## Takeaways

1. Saleor and Sentry use `pytest_plugins = [...]` at the root: fixture modules listed explicitly,
   one per domain, not star-imported into the root conftest.
2. Browser/E2E fixtures go in a conftest scoped to the e2e directory (`saleor/tests/e2e/conftest.py`).
   `pytest_plugins` in a non-root conftest is an error in modern pytest, so scoping means a plain
   import in a directory-scoped conftest.
3. Factories for shared models live in a shared, domain-split package (Oscar's
   `oscar/test/factories/`), consistent with `SiteFactory` in `site_aware_models/factories.py`.
4. Narrow-use fixtures sit with their narrow consumers (Saleor's per-app `tests/fixtures.py`).
5. No fetched repo showed a `collect_ignore_glob` guard for optional apps; Saleor and Oscar test
   everything installed. FLS's `app_not_installed` guard has no fetched precedent.

status: ok
