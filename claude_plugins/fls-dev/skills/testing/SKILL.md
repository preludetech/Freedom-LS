---
name: testing
description: FreedomLS test organisation, site-aware fixtures and marker taxonomy. Use alongside ds:testing when writing, moving or marking a test in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Testing (FreedomLS overlay)

Read `Skill(ds:testing)` first for the generic pytest/TDD/AAA methodology. This overlay adds **only** the FreedomLS specifics; it does not repeat the generic body.

For full FLS patterns and the de-branding techniques, see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (the FLS addendum to the `ds` testing resource) and `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.

## Test organisation and hygiene

Read "Test organisation and hygiene" in `ds:testing`'s resource first; what follows is the FLS instance of each rule.

FreedomLS tests live at `freedom_ls/<app_name>/tests/test_<module>.py`.

### Mirroring

Test-only helper and URLconf modules that sit correctly beside their tests: `panel_framework/tests/root_urls.py`, `panel_framework/tests/stub_panels.py`, `health/tests/root_urls.py`, `reports/tests/gather_input_builders.py` and `reports/tests/report_data_builders.py`.

### Cross-cutting tests

A test that exercises no single module lives in a subpackage of `<app>/tests/` (`components/`, `invariants/`, `demo_content/`). `test_organisation/mirroring_exemptions.txt` lists the current exemptions with a reason for each. To add one, append `<app>/tests/<subpackage>/  # <reason>` to that file and delete the covered files' lines from `mirroring_baseline.txt`. The exemption is permanent; it isn't debt to pay off later. Every new test directory needs an empty `__init__.py`, because pytest runs in `prepend` import mode and same-named modules in different directories collide without it.

### Named exceptions

`learner_interface/tests/views/`: page-grouped tests of the one `learner_interface/views.py`, one module per page it renders. The exemption line gives the reason.

`contrib/conformance/`: its root-level `test_*.py` files are both collected tests and importable probes, imported under aliases by `contrib/conformance/tests/test_conformance_meta.py`. It looks like a mirroring violation but is deliberate; the module docstrings say why.

`mail/tests/conftest.py`: its docstring says the helpers are public, not underscore-prefixed, because serialisation, the worker send and the backend are all tested against the same message shape.

### Dependency direction

`docs/app_structure.md`'s dependency table is the source of truth. Regenerate it with the `/ds:app_map` command (`generate_app_map.py`) rather than editing it by hand.

The string-reference case in FLS: `base` depends on `learner_management`, because `TEMPLATES` in `config/settings_base.py` registers `freedom_ls.learner_management.context_processors.can_access_educator_interface`, and `base`'s header template reads the context variable it produces. This edge is declared in `test_organisation/declared_edges.toml`, with that same reason.

Any app's tests may use `accounts`' `UserFactory`.

FLS's baselines and exemptions live in `test_organisation/`: `declared_edges.toml`, `import_baseline.txt`, `mirroring_baseline.txt` and `mirroring_exemptions.txt`. Three pre-commit and CI hooks check them: `app-map-fresh` (`docs/app_structure.md` and the generated contracts are up to date), `lint-imports` (dependency direction), and `test-mirroring` (mirroring).

### Granting permissions in tests

Use `guardian.shortcuts.assign_perm(codename, user, obj)`, not `role_based_permissions`' `assign_object_role`. The role layer is transparent at check time: its README says the role system manages what permissions a user should have, and guardian enforces them.

Where access resolves through role assignments, `assign_perm` grants nothing and the test uses `assign_object_role`. `learner_management.queries.organisations_accessible_to` is the case: it reads role assignments through `roles_granting`, and every `educator_interface` view and the base header-bar menu go through it.

`reports/tests/test_admin.py` uses `assign_perm` next to an `assign_object_role` call. Whether a role maps to the right permissions is `role_based_permissions`' own concern, tested in its own suite.

### `conftest.py` vs. plain module

Pattern to follow: `accounts/tests/conftest.py`, two fixtures plus the private `_seed_default_legal_docs`.

A helper that tests import by hand goes in `helpers.py` beside the tests: `content_engine/tests/helpers.py`, `learner_progress/tests/helpers.py` and `panel_framework/tests/helpers.py` are examples. `panel_framework/tests/stub_models.py` holds that foundational app's stub models. Shared modules for the whole suite live in `freedom_ls/tests/`: `site_context.py` (`site_context`, `drop_ambient_request`), `demo_content_fixtures.py` (module-scoped fixtures that import the shipped `demo_content/` tree) and `app_guards.py`.

### Fixture placement

`freedom_ls/conftest.py` holds the autouse `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides` and `_clear_course_access_backend_cache` fixtures, and the opt-in `mock_site_context` fixture, which many apps' fixtures build on. `mock_site_context` is not autouse; a test that needs it takes it as a parameter (see "`mock_site_context` fixture" below).

### Stub-model technique

The FLS instance is `panel_framework/tests/`. `stub_models.py` holds `StubModel`, `StubChild`, `StubProtectedChild` and `StubGrandchild` (whose docstring says why it exists), `helpers.py` their `_make_stub*` constructors, and `conftest.py` the fixtures that create their tables. A new foundational app's stub models go in a plain `stub_models.py` the same way.

`panel_framework/tests/stub_panels.py` shows the double-import hazard. Django's URL resolver loads it under a different module path from the one pytest gives the conftest, so it fetches `StubModel` with `apps.get_model` at call time. Its docstring explains why.

`site_aware_models` and `role_based_permissions` still borrow downstream models in their tests and need this technique.

### Fixture scope and idempotent reset

The FLS worked example is `_panel_test_tables` in `panel_framework/tests/conftest.py`: session-scoped table creation that unblocks the database only around the schema work on either side of the `yield`. Holding the unblock open across the `yield` would let an unmarked test write rows outside a transaction.

### The thin-wrapper rule

Root-conftest fixtures that are correctly not thin: `course_with_topic` (two factory calls plus `.items.create(...)`) and `staff_client` (builds on `mock_site_context` and `logged_in_client`).

### Factory cross-app direction

No FLS factory breaks the direction rule today, and none uses the dotted-string form yet, so this is new guidance rather than a description of existing code. The caller-side guard in FLS is `app_not_installed(...)`, shown in "Collection safety for optional apps — FLS example" below.

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

FreedomLS ships to downstream projects, so markers control which tests are *portable*. `pyproject.toml` registers them:

- **Unmarked (default) = portable** — contract/unit tests; the downstream-valuable set.
- **`playwright`** — browser-dependent (see `Skill(fls-dev:playwright-tests)`); the browser set a downstream excludes.
- **`fls_internal`** — only valid under FLS's own settings/theme/branding/demo content.
- **`ci_only`** — slow / real-time tests.
- **`dev_tooling`** — tests of developer tooling: QA seeders, `danger_` commands, dev scripts and the content validator.
- **`weasyprint`** — invokes WeasyPrint and needs Pango/cairo/gdk-pixbuf/HarfBuzz.

What runs where:

- `uv run pytest` runs `not ci_only and not weasyprint and not dev_tooling` (the `addopts` `-m`), without coverage. `--cov` opts in. It includes `playwright` and `fls_internal`, since that *is* FLS regression testing. `testpaths` covers `freedom_ls`, `tests` and `claude_plugins/fls-content`.
- CI runs three jobs. The unit job runs `-m "not playwright and not dev_tooling" --cov` with the coverage gate, and includes `weasyprint` because CI has the system libraries. The developer-tooling job runs `-m "dev_tooling and not playwright"`. The Playwright job runs `-m playwright -n auto`, which the root conftest caps at four workers.
- A concrete downstream project runs:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint and not dev_tooling"
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
