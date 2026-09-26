---
name: testing
description: FreedomLS-specific extension of the ds:testing skill. Adds the site-aware mock_site_context fixture rule, the fls_internal/playwright/ci_only/weasyprint marker taxonomy for downstream distribution, and FLS collection-safety. Use alongside ds:testing when writing pytest tests in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Testing (FreedomLS overlay)

Read `Skill(ds:testing)` first for the generic pytest/TDD/AAA methodology. This overlay adds **only** the FreedomLS specifics; it does not repeat the generic body.

For full FLS patterns and worked de-branding examples, see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (the FLS addendum to the `ds` testing resource) and `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.

## Test organisation and hygiene

Read "Test organisation and hygiene" in `ds:testing`'s resource first; what follows is the FLS instance of each rule.

FreedomLS tests live at `freedom_ls/<app_name>/tests/test_<module>.py`.

### Mirroring

No FLS app mirrors a subpackage yet: templatetag and management-command tests sit flat in `tests/` until they are moved.

Test-only helper and URLconf modules that sit correctly beside their tests: `panel_framework/tests/root_urls.py`, `panel_framework/tests/stub_panels.py`, `health/tests/root_urls.py`, `reports/tests/gather_input_builders.py` and `reports/tests/report_data_builders.py`.

### Cross-cutting tests

`form_engine/tests/test_import_independence.py`, and `content_engine`'s `test_demo_content_*.py` and `test_katex_vendor_assets.py`, are not yet grouped in a subpackage.

### Named exceptions

`contrib/conformance/`: its root-level `test_*.py` files are both collected tests and importable probes, imported under aliases by `contrib/conformance/tests/test_conformance_meta.py`. It looks like a mirroring violation but is deliberate; the module docstrings say why.

## `mock_site_context` fixture (mandatory for site-aware models)

Any test that touches a site-aware model **must** take the `mock_site_context` fixture — never manually set `site`. The fixture sets the thread-local site context that `SiteAwareFactory` and the site-aware managers read.

```python
def test_registered_learner_appears_in_cohort_roster(mock_site_context):
    # Arrange
    cohort = CohortFactory()
    learner = UserFactory()
    # Act
    cohort.register(learner)
    # Assert
    assert learner in cohort.roster()
```

## Marker taxonomy (downstream-distribution semantics)

FreedomLS ships to downstream projects, so markers control which tests are *portable*:

- **Unmarked (default) = portable** — contract/unit tests; the downstream-valuable set.
- **`playwright`** — browser-dependent (see `Skill(fls-dev:playwright-tests)`); the browser set a downstream excludes.
- **`fls_internal`** — only valid under FLS's own settings/theme/branding/demo content.
- **`ci_only`** — existing slow / real-time tests (unchanged).
- **`weasyprint`** — invokes WeasyPrint and needs Pango/cairo/gdk-pixbuf/HarfBuzz; excluded by default locally so contributors without those system libraries can still run the suite, but included in CI (where the libraries are installed) since CI's `-m "not playwright"` overrides the local `addopts` exclusion.

FLS's own `uv run pytest` runs everything except `ci_only` and `weasyprint` (it *is* FLS regression testing, with CI supplying the system libraries needed to also run the `weasyprint` set). A concrete downstream project instead runs:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"
```

**Reach for `fls_internal` last.** Every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, de-brand it first (pin the input or assert the contract). Only mark it when it genuinely depends on FLS's own repo/brand/demo state (e.g. it reads `demo_content/`). Prefer a file-level `pytestmark = pytest.mark.fls_internal` only for wholly brand-coupled files; mark individual tests in mixed files.

## Collection safety for optional apps — FLS example

`ds:testing` covers the generic technique. FLS's concrete target is `freedom_ls.course_applications`:

```python
import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```

The conftest form assigns `collect_ignore_glob` with the same call; `course_applications/tests/conftest.py` is the live example.
