---
name: testing
description: FreedomLS-specific extension of the ds:testing skill. Adds the site-aware mock_site_context fixture rule, the fls_internal/playwright/ci_only marker taxonomy for downstream distribution, and FLS collection-safety. Use alongside ds:testing when writing pytest tests in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Testing (FreedomLS overlay)

Read `Skill(ds:testing)` first for the generic pytest/TDD/AAA methodology. This overlay adds **only** the FreedomLS specifics; it does not repeat the generic body.

For full FLS patterns and worked de-branding examples, see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (the FLS addendum to the `ds` testing resource) and `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.

## Test file path convention

FreedomLS tests live at `freedom_ls/<app_name>/tests/test_<module>.py`.

## `mock_site_context` fixture (mandatory for site-aware models)

Any test that touches a site-aware model **must** take the `mock_site_context` fixture — never manually set `site`. The fixture sets the thread-local site context that `SiteAwareFactory` and the site-aware managers read.

```python
def test_registered_student_appears_in_cohort_roster(mock_site_context):
    # Arrange
    cohort = CohortFactory()
    student = StudentFactory()
    # Act
    cohort.register(student)
    # Assert
    assert student in cohort.roster()
```

## Marker taxonomy (downstream-distribution semantics)

FreedomLS ships to downstream projects, so markers control which tests are *portable*:

- **Unmarked (default) = portable** — contract/unit tests; the downstream-valuable set.
- **`playwright`** — browser-dependent (see `Skill(fls-dev:playwright-tests)`); the browser set a downstream excludes.
- **`fls_internal`** — only valid under FLS's own settings/theme/branding/demo content.
- **`ci_only`** — existing slow / real-time tests (unchanged).

FLS's own `uv run pytest` runs everything except `ci_only` (it *is* FLS regression testing). A concrete downstream project instead runs:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only"
```

**Reach for `fls_internal` last.** Every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, de-brand it first (pin the input or assert the contract). Only mark it when it genuinely depends on FLS's own repo/brand/demo state (e.g. it reads `demo_content/`). Prefer a file-level `pytestmark = pytest.mark.fls_internal` only for wholly brand-coupled files; mark individual tests in mixed files.

## Collection safety for optional apps — FLS example

`ds:testing` covers the generic technique. FLS's concrete target is `freedom_ls.course_applications`:

```python
import pytest
from django.conf import settings

if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```
