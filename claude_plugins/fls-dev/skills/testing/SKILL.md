---
name: testing
description: FreedomLS-specific extension of the ds:testing skill. Adds the FLS instances of the test organisation and hygiene rules (mirroring, dependency direction, and the conftest/fixture/factory layering), the site-aware mock_site_context fixture rule, the fls_internal/playwright/ci_only/weasyprint marker taxonomy for downstream distribution, and FLS collection-safety. Use alongside ds:testing when writing pytest tests in the FreedomLS repo.
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

`mail/tests/conftest.py`: its docstring says the helpers are public, not underscore-prefixed, because serialisation, the worker send and the backend are all tested against the same message shape.

### Dependency direction

`docs/app_structure.md`'s dependency table is the source of truth. Regenerate it with the `/ds:app_map` command (`generate_app_map.py`) rather than editing it by hand.

The string-reference case in FLS: `base` depends on `learner_management`, because `TEMPLATES` in `config/settings_base.py` registers `freedom_ls.learner_management.context_processors.can_access_educator_interface`, and `base`'s header template reads the context variable it produces. The dependency table cannot see this edge.

Any app's tests may use `accounts`' `UserFactory`.

### Granting permissions in tests

Use `guardian.shortcuts.assign_perm(codename, user, obj)`, not `role_based_permissions`' `assign_object_role`. The role layer is transparent at check time: its README says the role system manages what permissions a user should have, and guardian enforces them.

`reports`, `educator_interface`, `learner_management`, `base` and `organisations` check only `has_perm` and `get_objects_for_user`, so an `assign_object_role` call in their tests is a stand-in for a guardian grant. `reports/tests/test_admin.py` already uses `assign_perm` next to one.

Whether a role maps to the right permissions is `role_based_permissions`' own concern, tested in its own suite.

### `conftest.py` vs. plain module

Pattern to follow: `accounts/tests/conftest.py`, two fixtures plus the private `_seed_default_legal_docs`.

Pattern to avoid: `learner_interface/tests/conftest.py`, plain functions for manual import plus a `reverse_url` re-export from the root conftest.

### Fixture placement

`freedom_ls/conftest.py` holds the autouse `_disable_force_site_name`, `_disable_preview_overrides` and `_clear_course_access_backend_cache` fixtures, and the opt-in `mock_site_context` fixture, which many apps' fixtures build on. `mock_site_context` is not autouse; a test that needs it takes it as a parameter (see "`mock_site_context` fixture" below).

### Stub-model technique

The reference implementation is `panel_framework/tests/conftest.py`: `StubModel`, `StubChild`, `StubProtectedChild` and `StubGrandchild` (whose docstring says why it exists), with `_make_stub`, `_make_stub_child` and `_make_stub_protected_child`.

`site_aware_models` and `role_based_permissions` still borrow downstream models in their tests and need this technique.

### Fixture scope and idempotent reset

The FLS worked example is `panel_framework/tests/conftest.py`, quoted near-verbatim below and trimmed to the two fixture signatures, the unblock/schema-editor lines and `_panel_test_permissions`'s docstring:

```python
@pytest.fixture(autouse=True, scope="session")
def _panel_test_tables(django_db_setup, django_db_blocker):
    """Create stub tables once per test session."""
    with django_db_blocker.unblock():
        ...
        with connection.schema_editor() as editor:
            editor.create_model(StubModel)
            ...
        yield
        with connection.schema_editor() as editor:
            ...


@pytest.fixture(autouse=True)
def _panel_test_permissions(db):
    """Ensure stub-model ContentType and Permissions exist before every test.

    Function-scoped because tests using ``@pytest.mark.django_db(transaction=True)``
    elsewhere in the suite flush the DB between tests, wiping any session-scoped
    setup. The ContentType in-memory cache must also be cleared so that
    ``get_for_model(StubModel)`` does not return a stale PK from a prior
    rolled-back transaction. Idempotent via ``get_or_create``.
    """
    ...
```

### The thin-wrapper rule

Root-conftest fixtures that are correctly not thin: `course_with_topic` (two factory calls plus `.items.create(...)`) and `staff_client` (builds on `mock_site_context` and `logged_in_client`).

### Factory cross-app direction

No FLS factory breaks the direction rule today, and none uses the dotted-string form yet, so this is new guidance rather than a description of existing code. The caller-side guard in FLS is `app_not_installed(...)`, already shown in "Collection safety for optional apps — FLS example" below.

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
