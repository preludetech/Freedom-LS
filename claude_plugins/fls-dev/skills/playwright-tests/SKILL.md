---
name: playwright-tests
description: "FreedomLS browser flow tests: the shared fixtures, why every browser test is transaction=True, and where layout checks go. Use when writing or extending a Playwright test in the FreedomLS repo."
allowed-tools: Read, Grep, Glob
---

# Playwright tests (FreedomLS overlay)

Read `Skill(ds:playwright-tests)` first for the flow rule and the generic mechanics. This overlay covers only what is specific to FLS. Detail: `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md`.

## Fixtures

- `logged_in_page` and `logged_in_user`: an email-verified learner. `logged_in_page` gets its session from `sign_in` (`freedom_ls/tests/playwright_fixtures.py`), with no form. The page starts on `about:blank`, so the test calls `page.goto(...)` first.
- `educator_logged_in_page` and `cohort_admin_logged_in_page`: the educator and cohort-admin equivalents, also through `sign_in` (`freedom_ls/educator_interface/tests/playwright/conftest.py`).
- `_login_via_ui`: drives the allauth form, for the sign-in test only.
- `live_server_site` and `mock_site_context`: bind the live server's host to the test `Site` so site-aware queries resolve (`freedom_ls/conftest.py`).
- `QA_VIEWPORTS` and `assert_no_horizontal_overflow` (`freedom_ls/tests/playwright_helpers.py`): the layout check. A flow resizes one page through `QA_VIEWPORTS`, once per viewport.
- `QA_VIEWPORTS` and `assert_no_horizontal_overflow` also exist in `freedom_ls/panel_framework/tests/playwright/helpers.py`, the framework's own copy: its tests import that one, never `freedom_ls.tests`. Edit both together; `test_framework_copies_match_base.py` fails on drift. The standalone run (`Skill(fls-dev:testing)`) leaves `tests/playwright` out.

## Why transaction=True and a session per test

The browser uses its own database connection, so every browser test is `@pytest.mark.django_db(transaction=True)`. That flushes the database after each test and deletes the session row a reused cookie points at, so `sign_in` makes the session in the test, after its user exists. The `playwright_fixtures.py` module docstring has the full reasoning.

## Flow trade-off

A flow stops at its first failing step, so one failure hides the steps after it. The retained trace (`test-results/<test>/trace.zip`) shows which step failed. Extend the existing flow for a page with a step and an assertion instead of adding a file.

## What belongs in a Client test

Anything a rendered response proves: status codes, redirects, permissions, form validation, `HX-Request` handling, `HX-Trigger` headers, 422 responses, markup attributes. A browser test covers behaviour only a browser runs: JS, Alpine state, htmx swaps in the page, `<dialog>`, history, layout.

## Markers and CI

`Skill(fls-dev:testing)` covers the `playwright` marker, the rest of the marker taxonomy and the CI jobs.
