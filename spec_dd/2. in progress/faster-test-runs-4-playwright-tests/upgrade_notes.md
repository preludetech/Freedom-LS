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

# Upgrade notes: faster-test-runs-4-playwright-tests

## Breaking changes

This change touches only FLS's own tests and test fixtures. Runtime code, templates, settings and
migrations are unchanged.

The `logged_in_page` fixture, which `freedom_ls/conftest.py` re-exports, no longer drives the login
form. It now gives the browser context a session for `logged_in_user` and does not navigate, so the
page starts blank rather than on the post-login redirect. This affects two kinds of project
Playwright test:

- A test that checked its own login form through `logged_in_page`: call `_login_via_ui(page,
  live_server, email, password)` from `freedom_ls.tests.playwright_fixtures` on the plain `page`
  fixture instead.
- A test that read the page straight after `logged_in_page` without calling `page.goto` first: add
  the `page.goto` to the page it expects.

## Manual steps

None. Project Playwright fixtures that sign users in can call the new
`sign_in(page, live_server, user)` from `freedom_ls.tests.playwright_fixtures` instead of filling in
the login form. It is faster, and like `logged_in_page` it does not navigate.
