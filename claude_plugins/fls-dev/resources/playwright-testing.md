# Playwright testing — FreedomLS addendum

This addendum extends the `ds` `playwright-testing.md` resource (pulled in by `Skill(ds:playwright-tests)`) with the FLS marker framing. Read the `ds` resource first.

## Marker taxonomy / portability

The `playwright` marker sits alongside FLS's `fls_internal`, `ci_only` and `weasyprint` markers (see `Skill(fls-dev:testing)` for the full taxonomy). A concrete downstream project excludes the browser set, the FLS-internal set, the slow set, the WeasyPrint set and the developer-tooling set. The command is in the marker section of `Skill(fls-dev:testing)`.

FLS's own `uv run pytest` runs the `playwright` and `fls_internal` tests against FLS's own settings, as FLS regression testing.

## Cross-references and reverse names

- HTMX interaction guidance: `Skill(ds:htmx)` (htmx is `ds`-owned; there is no `fls-dev` overlay).
- Sign-in: `sign_in` (`freedom_ls/tests/playwright_fixtures.py`) calls `force_login` with `ModelBackend`, because Axes's backend is first in `AUTHENTICATION_BACKENDS`. The cookie name comes from `SESSION_COOKIE_NAME`, which differs per worktree. The form login lives in `freedom_ls/accounts/tests/playwright/test_sign_in_flow.py`. The generic resource's `<login url name>` placeholder is allauth's unnamespaced `account_login`. The learner dashboard is `learner_interface:dashboard`; there is no `:home`. Enrollment/course wording in examples is generic e-learning illustration.
