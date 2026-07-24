# Playwright testing — FreedomLS addendum

This addendum extends the generic `ds` `playwright-testing.md` resource (pulled in by `Skill(ds:playwright-tests)`). Most of the resource is generic; this file restores the FLS-specific marker framing. Read the `ds` resource first.

## Marker taxonomy / portability

The `playwright` marker sits alongside FLS's `fls_internal` and `ci_only` markers (see `Skill(fls-dev:testing)` for the full taxonomy). A concrete downstream project excludes the browser set and the FLS-internal set with:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only"
```

FLS's own `uv run pytest` exercises the `playwright` and `fls_internal` tests against FLS's own settings, since that is FLS regression testing.

## Cross-references and reverse names

- HTMX interaction guidance: `Skill(ds:htmx)` (htmx is `ds`-owned; there is no `fls-dev` overlay).
- Login-fixture reverse names in FLS examples use `reverse('student_interface:home')` (the generic resource uses `dashboard:home`). `accounts:login` is generic and left as-is. Enrollment/course wording in examples is generic e-learning illustration.
