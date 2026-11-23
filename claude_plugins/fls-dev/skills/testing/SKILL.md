---
name: testing
description: FLS test layout (mirroring, exemptions, conftest placement), the mandatory mock_site_context fixture and the marker taxonomy (which tests run where). Use alongside ds:testing when writing, moving or marking a test in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Testing (FreedomLS overlay)

Read `Skill(ds:testing)` first for the pytest/TDD/AAA methodology. This overlay adds **only** the FreedomLS specifics.

Full FLS patterns and the de-branding techniques: `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (the FLS addendum to the `ds` testing resource) and `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.

A test that passes on one run and fails on another: `${CLAUDE_PLUGIN_ROOT}/resources/flaky_tests.md`.

## Test organisation and hygiene

Read "Test organisation and hygiene" in `ds:testing`'s resource first; what follows is the FLS instance of each rule.

FreedomLS tests live at `freedom_ls/<app_name>/tests/test_<module>.py`.

### Mirroring

Test-only helper and URLconf modules that sit correctly beside their tests: `panel_framework/tests/root_urls.py`, `panel_framework/tests/stub_panels.py`, `health/tests/root_urls.py`, `reports/tests/gather_input_builders.py` and `reports/tests/report_data_builders.py`.

### Cross-cutting tests

A test that exercises no single module lives in a subpackage of `<app>/tests/` (`components/`, `invariants/`, `demo_content/`). `test_organisation/mirroring_exemptions.txt` lists the current exemptions with a reason for each. To add one, append `<app>/tests/<subpackage>/  # <reason>` to that file and delete the covered files' lines from `mirroring_baseline.txt`. The exemption is permanent, not debt. Every new test directory needs an empty `__init__.py`.

### Named exceptions

`learner_interface/tests/views/`: page-grouped tests of the one `learner_interface/views.py`, one module per page it renders. The exemption line gives the reason.

`contrib/conformance/`: its root-level `test_*.py` files are both collected tests and importable probes, imported under aliases by `contrib/conformance/tests/test_conformance_meta.py`. It looks like a mirroring violation but is deliberate (the module docstrings say why).

`mail/tests/conftest.py`: its docstring says the helpers are public, not underscore-prefixed, because serialisation, the worker send and the backend are all tested against the same message shape.

### Dependency direction

`docs/app_structure.md`'s dependency table is the source of truth. Regenerate it with the `/ds:app_map` command (`generate_app_map.py`) rather than editing it by hand.

The string-reference case in FLS: `base` depends on `learner_management`, because `TEMPLATES` in `config/settings_base.py` registers `freedom_ls.learner_management.context_processors.can_access_educator_interface`, and `base`'s header template reads the context variable it produces. This edge is declared in `test_organisation/declared_edges.toml`, with that same reason.

Any app's tests may use `accounts`' `UserFactory`.

FLS's baselines and exemptions live in `test_organisation/`: `declared_edges.toml`, `import_baseline.txt`, `mirroring_baseline.txt` and `mirroring_exemptions.txt`. Three pre-commit and CI hooks check them: `app-map-fresh` (`docs/app_structure.md` and the generated contracts are up to date), `lint-imports` (dependency direction), and `test-mirroring` (mirroring).

### Granting permissions in tests

Use `guardian.shortcuts.assign_perm(codename, user, obj)`, not `role_based_permissions`' `assign_object_role`.

Where access resolves through role assignments, `assign_perm` grants nothing and the test uses `assign_object_role`. `learner_management.queries.organisations_accessible_to` is the case: it reads role assignments through `roles_granting`, and every `educator_interface` view and the base header-bar menu go through it.

`reports/tests/test_admin.py` uses `assign_perm` next to an `assign_object_role` call. Whether a role maps to the right permissions is `role_based_permissions`' own concern, tested in its own suite.

### `conftest.py` vs. plain module

Pattern to follow: `accounts/tests/conftest.py`, two fixtures plus the private `_seed_default_legal_docs`.

A helper that tests import by hand goes in `helpers.py` beside the tests: `content_engine/tests/helpers.py`, `learner_progress/tests/helpers.py` and `panel_framework/tests/helpers.py` are examples. `panel_framework/tests/stub_models.py` holds that foundational app's stub models. Shared modules for the whole suite live in `freedom_ls/tests/`: `site_context.py` (`site_context`, `drop_ambient_request`), `demo_content_fixtures.py` (module-scoped fixtures that import the shipped `demo_content/` tree) and `app_guards.py`. `factories.py` holds `SiteFactory`, the factory for the `Site` row itself: `Site` belongs to no FLS app, so any app's tests can import it without adding a dependency.

### Fixture placement

`freedom_ls/conftest.py` holds the autouse `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides` and `_clear_course_access_backend_cache` fixtures, the session-scoped autouse `fast_password_hasher` fixture (tests hash passwords with MD5, and the configured hashers stay after it so their hashes still verify), and the opt-in `mock_site_context` fixture, which many apps' fixtures build on. `mock_site_context` is not autouse; a test that needs it takes it as a parameter (see "`mock_site_context` fixture" below).

A test that checks real hashing, such as an Argon2 hash or a hash prefix, opts in to the configured hashers with the non-autouse `production_password_hashers` fixture. It takes the fixture as a parameter, or a class or module applies `@pytest.mark.usefixtures("production_password_hashers")`. A concrete project turns MD5 off by defining its own `fast_password_hasher` after importing `freedom_ls.conftest`.

`freedom_ls/conftest.py` imports the four Playwright fixtures (`playwright`, `reset_local_storage`, `logged_in_user`, `logged_in_page`) from `freedom_ls/tests/playwright_fixtures.py` by name, so they reach every app's `tests/playwright/` directory and any project that star-imports the module. A fixture shared across apps lives in a plain module in the lowest app that depends on everything it builds, and each consumer's `tests/conftest.py` imports it by name: `course_with_scored_quiz` and `sit_quiz` live in `learner_progress/tests/quiz_fixtures.py` and are imported by `learner_progress/tests/conftest.py` and `learner_interface/tests/conftest.py`.

### Stub-model technique

The FLS instance is `panel_framework/tests/`. `stub_models.py` holds `StubModel`, `StubChild`, `StubProtectedChild` and `StubGrandchild` (whose docstring says why it exists), `helpers.py` their `_make_stub*` constructors, and `conftest.py` the fixtures that create their tables. A new foundational app's stub models go in a plain `stub_models.py` the same way. The migration-drift probe, `contrib/conformance/test_migrations.py`, skips models defined under a `tests` package, so stubs stay out of it when their app has real migrations.

`panel_framework/tests/stub_panels.py` shows the double-import hazard. Django's URL resolver loads it under a different module path from the one pytest gives the conftest, so it fetches `StubModel` with `apps.get_model` at call time. Its docstring explains why.

`site_aware_models` and `role_based_permissions` still borrow downstream models in their tests and need this technique.

### Fixture scope and idempotent reset

The FLS worked example is `_panel_test_tables` in `panel_framework/tests/conftest.py`: session-scoped table creation that unblocks the database only around the schema work on either side of the `yield`. Never hold the unblock open across the `yield`.

### The thin-wrapper rule

Root-conftest fixtures that are correctly not thin: `course_with_topic` (two factory calls plus `.items.create(...)`) and `staff_client` (builds on `mock_site_context` and `logged_in_client`).

### Factory cross-app direction

The caller-side guard in FLS is `app_not_installed(...)`, shown in "Collection safety for optional apps — FLS example" below.

## `mock_site_context` fixture (mandatory for site-aware models)

Any test that touches a site-aware model **must** take the `mock_site_context` fixture, and never sets `site` manually. The fixture sets the thread-local site context that `SiteAwareFactory` and the site-aware managers read.

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
- **`needs_fls_host`** — a `panel_framework` test that needs FLS's real templates, icon set or URLconf. The standalone run deselects it.

What runs where:

- `uv run pytest` runs `not ci_only and not weasyprint and not dev_tooling` (the `addopts` `-m`), without coverage. `--cov` opts in. It includes `playwright` and `fls_internal`: that is FLS regression testing. `testpaths` covers `freedom_ls`, `tests` and `claude_plugins/fls-content`.
- The test tiers (`select_tests.sh`) pass `-m 'not ci_only and not weasyprint'`, from `[tool.test_tiers] markers`, so `dev_tooling` tests run when a tier selects them. `addopts` also sets `--dist loadfile`: under `-n auto` a module's tests stay on one worker.
- CI (`.github/workflows/tests.yml`) runs on push to main and on `workflow_dispatch`, not on pull requests. Its test jobs:
  - `unit-1` to `unit-6` run `-m "not playwright" --cov` (`UNIT_MARKERS`), so they include `ci_only`, `weasyprint` and `dev_tooling` tests; CI has the system libraries.
  - `playwright-1` and `playwright-2` run `-m playwright` (`BROWSER_MARKERS`), both with `-n auto` (the root conftest caps it at four workers).
  - Each group takes its share of the tests with `pytest-split`, from `.test_durations`, and a random seed set from the run ID.
  - `standalone-panel_framework` and `standalone-icons` run the two standalone commands below, each with its own `standalone_pytest.ini`.
  - `coverage` combines the unit groups' coverage data and fails under 92%.
  - `test-verdict` fails unless every test job and `coverage` succeeded, and checks that the groups' reports together hold each collected test exactly once.
- The panel framework's unit tests also run with no FLS around them, in CI's `standalone-panel_framework` job. This is a documented command, not a `[tool.test_tiers]` tier:

```bash
uv run pytest -c freedom_ls/panel_framework/tests/standalone_pytest.ini freedom_ls/panel_framework/tests
```

  `standalone_pytest.ini` sets `--ds=freedom_ls.panel_framework.tests.standalone_settings` (in-memory SQLite, `standalone_app/` for the user model, no stand-in templates: the framework ships every template it renders), adds `-m "not needs_fls_host"`, skips only `playwright` (`norecursedirs`), so the `components` and `invariants` tiers run too, and blocks network access. `standalone_fixtures.py` supplies the `site` and `mock_site_context` fixtures; FLS's conftest does not load.
- The icons app's tests run the same way, in CI's `standalone-icons` job:

```bash
uv run pytest -c freedom_ls/icons/tests/standalone_pytest.ini freedom_ls/icons/tests
```

  `standalone_pytest.ini` sets `--ds=freedom_ls.icons.tests.standalone_settings` (no database, only `django_cotton` and `freedom_ls.icons` installed) and blocks network access; FLS's conftest does not load. The settings leave `SEMANTIC_ICONS_ICONIFY_DIR` unset, so the tests render from the bundled icon data alone. `freedom_ls/icons/tests/conftest.py` clears the loader cache around every test and provides two fixtures: `bundled_data_only` sets `SEMANTIC_ICONS_ICONIFY_DIR` to `None`, and `iconify_dir` points it at an empty `tmp_path`. Use `iconify_dir` to test the on-disk overlay and `bundled_data_only` to pin the bundled lookup under FLS settings; never point the setting at a real directory in a test.
- A concrete downstream project runs:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint and not dev_tooling" -n auto --dist loadfile
```

Add `needs_fls_host` to a `panel_framework` test that fails under the standalone run because the framework's default templates, icons or URLconf lack something it asserts on (a rendered FLS template, a real icon, an FLS URL name). Mark the individual test, as `test_reference.py` and `test_tables.py` do. The marker is not `fls_internal`: the FLS run keeps the test, and a downstream that installs the framework runs it too.

**Reach for `fls_internal` last.** Every portable test is integration signal for a downstream. Before marking a test `fls_internal`, de-brand it first (pin the input or assert the contract). Only mark it when it genuinely depends on FLS's own repo/brand/demo state (e.g. it reads `demo_content/`). Prefer a file-level `pytestmark = pytest.mark.fls_internal` only for wholly brand-coupled files; mark individual tests in mixed files.

## The test-cost ranking

```bash
uv run python scripts/rank_test_costs.py
```

Run it after pruning tests, or when the suite feels slower. It runs the whole suite once under a cost recorder with `-n 4`, then writes `test_organisation/test_cost_ranking.md`. The run leaves out the Playwright, `ci_only` and `weasyprint` tests, `educator_interface/tests/invariants/test_permission_matrix.py` and `tests/test_rank_test_costs.py`. It does include the `dev_tooling` tests, which a plain `uv run pytest` leaves out. The last run took about 318 seconds of wall time, 5.3 minutes. The command takes no arguments.

`test_organisation/test_cost_ranking.md` holds a header (date, commit, test count, CPU and wall seconds, the database setup and teardown time kept out of the test costs, run conditions) and the cost, in seconds and share of the total, of each area, of the top 50 files and of the top 200 test functions. It is generated: do not edit it by hand. Compare costs only between runs made under similar machine load, since the header records the load.

Nothing fails on slowness: no test or hook has a time limit. A run with failing tests exits non-zero and leaves the ranking as it was.

## Remote full run

The `full` tier runs on GitHub Actions. `[tool.test_tiers.remote]` in `pyproject.toml` sets the command, `uv run python claude_plugins/fls-dev/scripts/remote_full_run.py`. It pushes the branch if needed, dispatches the `Tests` workflow, waits for it and prints the runner's `run:` lines, ending in `run: RESULT PASS`, `FAIL` or `UNAVAILABLE <reason>`. Run it as any full tier, through the test runner in the background (`Skill(sdd:protected:run_tests)`).

- `RESULT UNAVAILABLE`: GitHub gave no verdict. Quote the reason and run the `fallback:` line, the local full command.
- `- Remote full run: off` under `## Test Tiers` in `.claude/ds/config.md` turns the remote run off for everyone, for a GitHub outage or a move off GitHub; in `.claude/ds/config.local.md` it turns it off for one machine. The full tier then runs locally and never calls `gh`. `DS_TEST_REMOTE=on|off` overrides both for one run.

Reading a remote failure:

- Each `run: failed <node id>` line is a failed test. Re-run those locally, as for a local failure.
- A `remote: standalone-<app> failures re-run with: <command>` line marks failures from a standalone job. Re-run those IDs with that command, which uses the app's `standalone_pytest.ini`. The tier's own command runs them with FLS around them, where a standalone-only failure passes.
- `.sdd-work/remote_full_run_<branch>.txt` (the `run: log` line, `/` in the branch name written as `-`) holds each failed node ID and its failure text. Read it before re-running.
- A `RESULT FAIL` with no `run: failed` line is not a test failure. `run: coverage <n>% below <m>%` means the coverage gate failed. Otherwise open the `run: url` page and read the failing job.

Refreshing `.test_durations`, which splits the groups evenly: run both pools in the background through the test runner, then commit the file. The second run merges into the first's output.

```bash
.claude/ds/scripts/run_tests.sh uv run pytest -n auto --no-cov -m 'not playwright' --store-durations --durations-path .test_durations
.claude/ds/scripts/run_tests.sh uv run pytest -n auto --no-cov -m 'playwright' --store-durations --durations-path .test_durations
```

Refresh it when a group runs much longer than the others.

## Memory settings

The test runner sizes its xdist worker count to free memory. `claude_plugins/django-stack/resources/test_tiers.md` defines what each setting means; this section records FLS's values and how they were measured.

Measured 2026-11-12, each rounded up to the next 256 MB:

- `per_worker_mb = 768` and `max_workers = 4` in `[tool.test_tiers.memory]` in `pyproject.toml`. `max_workers` matches the cap the root `conftest.py` puts on `-n auto`. 768 is the largest proportional set size (Pss) of one worker plus its Chromium, 669 MB.
- `Batch memory (MB): 3584` in `.claude/sdd/config.md`, with `Memory capacity` pointing at `run_tests.sh --capacity`. 3584 is the largest Pss of the whole process tree under the runner during the full tier, 3402 MB.
- `Worker memory (MB)` is blank: the session that measured it shared a process with its subagent, so there was no process of its own to size.

To re-measure, run the full tier through the runner in the background and sample beside it with a throwaway script kept out of version control. Every 2 seconds, find each process of your user whose `/proc/<pid>/environ` holds `PYTEST_XDIST_WORKER=`. The root of each group is the one whose parent lacks the variable, and the group is that root and its descendants. Sum `Pss` from `/proc/<pid>/smaps_rollup` over each group, and over the whole tree under the `run_tests.py` process. Keep the largest of each, round both up to the next 256 MB, and write them to the places above. For `Worker memory (MB)`, take the `Pss` of the session's `claude` process, rounded the same way, when the session started after the batch did.

## Collection safety for optional apps — FLS example

`ds:testing` covers the generic technique. FLS's concrete target is `freedom_ls.course_applications`:

```python
import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```

The conftest form is one line, `collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.course_applications")`, and covers every test module under `tests/`, subdirectories included; `course_applications/tests/conftest.py` is the live example.
