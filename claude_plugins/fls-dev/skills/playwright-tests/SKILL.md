---
name: playwright-tests
description: "FreedomLS browser flow tests: the shared fixtures, why every browser test is transaction=True, and where layout checks go. Use when writing or extending a Playwright test in the FreedomLS repo."
allowed-tools: Read, Grep, Glob
---

# Playwright tests (FreedomLS overlay)

Read `Skill(ds:playwright-tests)` first for the flow rule and the generic mechanics. This overlay covers what is specific to FLS. Resource detail: `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md`.

## Fixtures

- `logged_in_page` and `logged_in_user`: an email-verified learner, logged in through the allauth form (`freedom_ls/tests/playwright_fixtures.py`).
- `educator_logged_in_page`: the educator equivalent (`freedom_ls/educator_interface/tests/playwright/conftest.py`).
- `live_server_site` and `mock_site_context`: bind the live server's host to the test `Site` so site-aware queries resolve (`freedom_ls/conftest.py`).
- `QA_VIEWPORTS` and `assert_no_horizontal_overflow` (`freedom_ls/tests/playwright_helpers.py`): the layout check. A flow loops it over every viewport in its last step.

## Why transaction=True and a login per test

The browser uses its own database connection, so every browser test is `@pytest.mark.django_db(transaction=True)`. That flushes the database after each test, which deletes the session row a reused login cookie points at. Login therefore happens per test through the UI. The `playwright_fixtures.py` module docstring has the full reasoning.

## Flow trade-off

A flow stops at its first failing step, so one failure hides the steps after it. The retained trace (`test-results/<test>/trace.zip`) shows which step failed. Extend the existing flow for a page with a step and an assertion instead of adding a file.

## What belongs in a Client test

Anything a rendered response proves: status codes, redirects, permissions, form validation, `HX-Request` handling, `HX-Trigger` headers, 422 responses, markup attributes. A browser test covers behaviour only a browser runs: JS, Alpine state, htmx swaps in the page, `<dialog>`, history, layout.

## Markers and CI

`Skill(fls-dev:testing)` covers the `playwright` marker, the rest of the marker taxonomy and the CI jobs.
