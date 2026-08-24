# Playwright testing — FreedomLS addendum

This addendum extends the generic `ds` `playwright-testing.md` resource (pulled in by `Skill(ds:playwright-tests)`). Most of the resource is generic; this file restores the FLS-specific marker framing. Read the `ds` resource first.

## Marker taxonomy / portability

The `playwright` marker sits alongside FLS's `fls_internal`, `ci_only` and `weasyprint` markers (see `Skill(fls-dev:testing)` for the full taxonomy). A concrete downstream project excludes the browser set, the FLS-internal set, the slow set and the WeasyPrint set with:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"
```

FLS's own `uv run pytest` exercises the `playwright` and `fls_internal` tests against FLS's own settings, since that is FLS regression testing.

## Cross-references and reverse names

- HTMX interaction guidance: `Skill(ds:htmx)` (htmx is `ds`-owned; there is no `fls-dev` overlay).
- Login-fixture reverse names: the generic resource's `accounts:login` and `home` are placeholders — substitute the real ones. FLS's shared fixture (`freedom_ls/tests/playwright_fixtures.py`) reverses allauth's unnamespaced `account_login` and then asserts the redirect *away* from it, because `LOGIN_REDIRECT_URL` is `/`. The learner dashboard is `learner_interface:dashboard`; there is no `:home`. Enrollment/course wording in examples is generic e-learning illustration.
