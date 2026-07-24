---
name: playwright-tests
description: FreedomLS-specific extension of the ds:playwright-tests skill. Explains why the playwright marker exists for FLS downstream exclusion. Use alongside ds:playwright-tests when writing E2E/browser tests in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Playwright tests (FreedomLS overlay)

Read `Skill(ds:playwright-tests)` first for the generic Playwright/pytest-django mechanics. This overlay adds **only** the FreedomLS marker rationale.

For the FLS resource detail, see `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md`.

## Why the `playwright` marker exists

`@pytest.mark.playwright` (applied to every browser test, all under per-app `tests/e2e/` dirs) is the **browser set a downstream project excludes**. Keep every browser test under this marker and don't rename it.

The marker sits alongside the rest of FLS's taxonomy (`fls_internal` / `ci_only`) documented in `Skill(fls-dev:testing)`. A concrete downstream project selects the portable set with:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only"
```
