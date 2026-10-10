# Research: test suite inventory and organisation

Scope: facts from the code at `/home/sheena/workspace/lms/freedom-ls-worktrees/testing-cleanup-junk`. Line counts are `^` match counts (all lines) from ripgrep and are approximate. Source-line counts exclude `tests/` and `migrations/`.

## 1. How the suite is organised today

### Conftest, fixture and factory layering

- `conftest.py` (repo root) does `from freedom_ls.conftest import *` and defines `pytest_xdist_auto_num_workers`. Nothing else.
- `freedom_ls/conftest.py` (about 320 lines) is the real shared layer.
  - Autouse: `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides`, `_clear_course_access_backend_cache`.
  - Opt-in: `pathless_logo_storage`, `site`, `make_temp_file`, `mock_site_context`, `logged_in_client`, `staff_client`, `course_with_topic`, `article_with_image`, `course_with_scored_quiz`, `sit_quiz`, `site_aware_request`, `live_server_site`.
  - Also a plain function `reverse_url`, which other apps import by hand.
- `freedom_ls/tests/` is a non-test package of shared helpers: `playwright_fixtures.py`, `storages.py`, `images.py`, `app_guards.py`.
  - `playwright_fixtures.py` holds `playwright` (session), autouse `reset_local_storage`, `logged_in_user`, `logged_in_page`, `_login_via_ui` and `close_db_connections_before_playwright_stops`.
- `tests/conftest.py` is 9 lines, for the dev-script tests.
- Factories live in each app's `factories.py` (e.g. `freedom_ls/accounts/factories.py`, `content_engine/factories.py`). Several apps import other apps' factories from tests (see the import baseline below).
- Per-app conftests, by role:
  - Fixture-only and small: `accounts` (`mock_legal_blobs`, `legal_repo_mock`), `educator_interface` (`panel_request`), `comms` (`_enable_notifications`), `referral_tracking` (`_clear_cache`), `content_engine` (`loaded_demo_content`), `blog` (`blog_url_prefix`).
  - Plain helper functions imported by hand (the SKILL's "pattern to avoid"):
    - `learner_interface/tests/conftest.py`: `section_by_slug`, `rendered_section`, `course_with_form`, `course_with_single_question_form`, `register_user_for_course`, `course_progress_record`, `form_attempt`, `topic_completion`, `learner_with_two_grants`, `collection_item_for`. It is imported by about 25 test files via `from .conftest import ...`, and also by `learner_interface/tests/playwright/form_ui_tests.py` via `from ..conftest import ...`.
    - `reports/tests/conftest.py`: `collection_item_for`, `cohort_progress_record`, `individual_progress_record`, `topic_progress`, `form_progress`, `requires_tailwind_bundle`. Imported by `test_gather.py`, `test_gather_indexes.py`, `test_pdf_integration.py` and `test_render.py`.
    - `course_applications/tests/conftest.py`: `gated_course_with_form`, imported by `test_views.py` and `test_admin.py`.
    - `deployment/tests/conftest.py`: `set_env`, `EXPECTED_ALIASES`, `LEGACY_SHARED_BUCKET_ENV`, imported by `test_storage.py`, `test_storage_settings.py` and `test_checks.py`.
    - `mail/tests/conftest.py`: `make_message`, `body_parts`, `LONG_URL`. The SKILL names this one as deliberate.
    - `panel_framework/tests/conftest.py`: `StubModel`, `StubChild`, `_make_stub*` and `make_staff_user` (imported by about 20 test files and by `view_helpers.py`). The SKILL names this as known debt.
- Duplicated helper: `collection_item_for(course, child)` is defined in both `learner_interface/tests/conftest.py` (line 208) and `reports/tests/conftest.py` (line 32).
- Near-duplicate course/progress builders: `course_progress_record` in `learner_interface` against `cohort_progress_record` and `individual_progress_record` in `reports`.
- `educator_interface/tests/playwright/conftest.py` defines `educator_user` and `educator_logged_in_page` on top of `freedom_ls/tests/playwright_fixtures.py`. `playwright/helpers.py` adds `interface_url`.
- Non-conftest helper modules inside tests dirs:
  - `accounts/tests/_auth_page_helpers.py`, `_completion_view_fixtures.py`, `_registration_form_fixtures.py`, `_git_helpers.py`
  - `panel_framework/tests/stub_panels.py` (413 lines), `view_helpers.py`, `cotton_helpers.py`, `urls.py`, `root_urls.py`, `playwright/assertions.py`
  - `reports/tests/gather_input_builders.py` (226), `report_data_builders.py` (196)
  - `educator_interface/tests/interface_walk.py` (171)
  - `base/tests/error_pages_urls.py`, `content_engine/tests/no_blog_urls.py`, `learner_interface/tests/no_sitemap_urls.py` (URLconf stubs)
  - `panel_framework/tests/templates/**` and `template_overrides/**` (HTML)
- Naming collision with pytest's collection globs: `python_files = ["tests.py", "test_*.py", "*_tests.py"]`. `learner_interface/tests/playwright/form_ui_tests.py` (659 lines, 7 `mark.playwright`) matches `*_tests.py`, so it is a collected test module that is also imported-style helper content (it defines `navigate_to_form`, `start_form`, `answer_multiple_choice_question`, ...).

### What test_organisation enforces

Config lives in `pyproject.toml` `[tool.test_organisation]` (`user_model_app = freedom_ls.accounts`). Files in `test_organisation/`:

| File | Lines | What it holds |
|---|---|---|
| `mirroring_baseline.txt` | 321 (about 292 non-comment entries) | Test files that do not mirror a source module. Delete-only; a stale line fails the check. |
| `mirroring_exemptions.txt` | 7 (comments only) | **Empty.** No permanent exemptions are declared, so every non-mirroring file is carried as debt in the baseline. |
| `import_baseline.txt` | 152 | "importer -> imported" dependency-direction violations by tests (and a few non-test modules such as `freedom_ls.comms.factories -> freedom_ls.content_engine.factories`). |
| `import_contracts.toml` | 477 | import-linter contracts, generated by `claude_plugins/django-stack/scripts/generate_app_map.py`. |
| `declared_edges.toml` | 9 | One edge only: `base -> learner_management` (context processor string reference). |

- Enforcement: `tests/test_check_test_mirroring.py` (456 lines), `tests/test_generate_app_map.py` (1044 lines), CI `lint` job (`generate_app_map.py --check`, `lint-imports --config test_organisation/import_contracts.toml`, `check_test_mirroring.py`), and pre-commit hooks `app-map-fresh`, `lint-imports`, `test-mirroring` per the FLS testing SKILL.
- Mirroring baseline by app (non-comment entries, approximate): learner_interface 50, content_engine 36, panel_framework 28, accounts 20, base 18, educator_interface 15, form_engine 15, learner_management 12, learner_progress 10, icons 8, comms 7, webhooks 3, and about 1 to 6 each in blog, course_access, deployment, dev_tools, qa_helpers, referral_tracking, reports, site_aware_models, others. Roughly 60 percent of the 504 files sit in the baseline. The `mirroring_baseline.txt` header says lines are only ever deleted.
- Import baseline largest clusters: `educator_interface.tests.playwright.*` -> `accounts.models` and `role_based_permissions.utils` (dozens of lines), `comms.tests.*` -> `content_engine.factories`/`learner_management.factories`/`organisations.factories`, `accounts.tests.test_deferred_login` -> six other apps.

### Documented structure vs. code

Documented (`claude_plugins/fls-dev/skills/testing/SKILL.md`, `claude_plugins/django-stack/skills/testing/SKILL.md`):

- Mirror `<app>/<module>.py` -> `<app>/tests/test_<module>.py`, subpackages included.
- Tests import only apps their app depends on.
- `conftest.py` holds fixtures only; hand-imported helpers go in a plain module.
- Use factory_boy always, never `.objects.create()`; no loops or conditionals in test bodies; one behaviour per test; AAA; don't mock owned code; don't assert on CSS or config literals.
- Prefer `guardian.assign_perm` over `assign_object_role` in tests of apps outside `role_based_permissions`.
- The SKILL states "No FLS app mirrors a subpackage yet" and lists `panel_framework/tests/conftest.py` stub models as known deferred cleanup.

Departures observed:

- Hand-imported helpers in conftest: `learner_interface`, `reports`, `course_applications`, `deployment` and `panel_framework` (the SKILL names only `learner_interface` and `panel_framework`). `deployment`, `reports` and `course_applications` are not named.
- Dependency direction: 152 import-baseline lines.
- Mirroring: about 292 baseline lines, with an empty exemptions file. The SKILL's own advice for cross-cutting tests (group into a subpackage and add an exemption) has not been applied once, including for `content_engine/tests/test_demo_content_*.py` and `form_engine/tests/test_import_independence.py` that the SKILL names.
- `.objects.create()`: not measured in this unit.
- `panel_framework/tests/test_conftest.py` (17 lines) and `tests/test_conftest.py` (60 lines) are tests of conftest fixtures themselves.

## 2. Where the bulk is

### Biggest test files (lines, approximate)

| Lines | File | Content |
|---|---|---|
| 1823 | `learner_interface/tests/test_form_runner_views.py` | 59 test functions; form runner views |
| 1359 | `reports/tests/test_partials.py` | 68 tests; report partial rendering |
| 1330 | `reports/tests/test_gather.py` | 54 tests |
| 1306 | `claude_plugins/fls-content/validate/tests/test_validator.py` | content validator (2 `fls_internal` tests) |
| 1247 | `reports/tests/test_gather_helpers.py` | 111 tests |
| 1077 | `markdown_rendering/tests/test_markdown_utils.py` | |
| 1044 | `tests/test_generate_app_map.py` | dev-tooling tests |
| 1022 | `reports/tests/test_gather_indexes.py` | 54 tests |
| 1145 | `course_applications/tests/test_views.py` | |
| 963 | `accounts/tests/test_email_templates.py` | |
| 924 | `content_engine/tests/test_content_save_course.py` | |
| 891 | `panel_framework/tests/test_panel_actions.py` | |
| 864 | `reports/tests/test_pdf_integration.py` | 25 tests; `weasyprint` |
| 806 | `deployment/tests/test_housekeeping.py` | |
| 733 | `learner_interface/tests/test_course_access_integration.py` | |
| 660/654 | `learner_interface/tests/test_sequential_item_unlock.py`, `test_resume_and_redirect.py` | |
| 659 | `learner_interface/tests/playwright/form_ui_tests.py` | helper-style playwright module |
| 609 | `role_based_permissions/tests/test_utils.py` | |
| 594 | `educator_interface/tests/test_permission_matrix.py` | |
| 585 | `panel_framework/tests/test_data_table_panel.py` | |
| 562/556 | `learner_interface/tests/test_read_path_record_scoping.py`, `content_engine/tests/test_content_save_save_with_uuid.py` | |
| 543 | `content_engine/tests/test_image_cache.py` | |
| 539 | `accounts/tests/test_email_utils.py` | |
| 538 | `accounts/tests/test_deferred_login.py` | |
| 522 | `learner_interface/tests/test_player_progress_scoping.py` | |
| 506 | `educator_interface/tests/test_organisation_isolation.py` | |
| 503 | `learner_interface/tests/test_seo_discoverability.py` | |
| 496 | `learner_interface/tests/playwright/test_course_toc.py` | 7 playwright tests |

`reports/tests` alone is 8534 lines in 16 files, with 454 test functions, for 2948 source lines (about 2.9 test lines per source line).

### Test lines against source lines (tests dir total, including conftests and helpers)

| App | Test lines | Source lines | Ratio |
|---|---|---|---|
| learner_interface | 16888 (67 files) | 3484 (13 files) | about 4.8 |
| panel_framework | 9833 (75 incl. html) | 3377 | about 2.9 |
| reports | 8534 | 2948 | about 2.9 |
| content_engine | 8732 | 4987 | about 1.8 |
| accounts | 6346 (34 files) | 2903 | about 2.2 |
| educator_interface | 5423 (31 files) | 1021 (views.py 866, quick_views.py 80 only) | about 5.3 |

The `educator_interface` source count only covers top-level `.py` modules; panels and configs may live in other apps. It is a lower bound on source, so the ratio is an upper bound.

- `learner_interface/views.py` is 1794 lines and `utils.py` 1041 lines, and the app's tests are about 4.8 times that. The 25 or so `from .conftest import ...` consumers share one helper set.
- 257 `@pytest.mark.parametrize` decorators across 125 files; highest per file counts are `accounts/tests/test_email_templates.py` (10), `panel_framework/tests/playwright` (not parametrised, but 15 tests in `test_modal_form_htmx.py`, 12 in `test_data_table_panel_htmx.py`, 10 in `test_quick_view_htmx.py`), `deployment/tests/test_storage.py` (7), `base/tests/test_analytics_events.py` (5). The "giant parametrised matrix" files by parametrize count are not extreme; the matrix-like files are `educator_interface/tests/test_permission_matrix.py` (594 lines) and `test_organisation_isolation.py` (506 lines), driven by `interface_walk.py`.
- Playwright: 149 `mark.playwright` hits in 52 files (the 226-test figure includes parametrised expansions). Playwright files per app: panel_framework 21 files, educator_interface 10, learner_interface 14 (incl. `form_ui_tests.py`), referral_tracking 2, comms 2, and one each in base, blog, course_applications, form_engine, plus `tests/playwright/test_design_screenshots.py`. Many are single-concern layout or width tests (`test_stat_tile_progress_width.py`, `test_progress_bar_fill.py`, `test_table_sheet_no_js.py`, `test_form_option_layout.py`), each with its own browser and live-server setup. Educator playwright files all use `pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]`. Not every playwright file in `panel_framework` and `learner_interface` uses that `pytestmark` form; they use per-test decorators.
- Tiny files: `learner_interface/tests/test_dashboard_section_slugs.py` (8 lines, one assertion comparing two enums), `base/tests/test_config.py` (10 lines, asserts `config.VISITOR_COUNTRY_HEADER is None`, a config-default assertion), `panel_framework/tests/test_conftest.py`, `educator_interface/tests/test_system_checks.py` (16), `base/tests/test_dev_tooling_disabled_in_tests.py` (30), `base/tests/test_premailer_templatetag.py` (28).

## 3. Organisation problems

### Tests that do not mirror a module

About 292 files (see section 1). Examples: `learner_interface/tests/test_dashboard_*.py` (7 files for one `dashboard_sections.py` and `views.py`); `learner_progress/tests/test_course_progress_*.py` (6 files for one module); `panel_framework/tests/test_component_*.py` (10 files, one per Cotton component, which have no Python module); `content_engine/tests/test_content_save_*.py` (6 files for `management/commands/content_save.py`, 1143 source lines); `icons/tests/test_*_semantic_name.py` (4 files).

### Cross-app tests (misplaced)

- `learner_interface/tests/test_course_access_integration.py` (733 lines) tests `course_access` behaviour through learner views.
- `learner_interface/tests/test_course_completion_webhook_events.py`, `test_course_completion_notifications.py`: webhook and notification behaviour.
- `accounts/tests/test_account_webhook_events.py`, `test_user_registration_webhook_integration.py`: webhook behaviour; `learner_management/tests/test_registration_webhook_events.py` likewise.
- `accounts/tests/test_deferred_login.py` (538 lines) imports `content_engine`, `course_applications`, `course_interest`, `learner_management` (6 import-baseline lines).
- `educator_interface/tests/test_course_visibility_and_interest.py`, `test_permission_matrix.py`, `test_organisation_isolation.py`: cross-app.
- `learner_interface/tests/test_seo_discoverability.py` (503 lines) and `blog/tests/test_seo_discoverability.py`: same name, same concern in two apps.
- `learner_interface/tests/test_self_registration_learner.py`, `test_player_organisation.py`: `accounts`/`organisations` concerns.
- `learner_interface/tests/test_demo_content_course_card.py` is `fls_internal`, in the wrong app's tests tree relative to the `content_engine/tests/test_demo_content_*.py` convention.
- Same-named files in different apps: `test_deletion_semantics.py` (form_engine, learner_management), `test_document_title.py` (educator_interface, panel_framework), `test_seo_discoverability.py`, `test_checks.py` (10+ apps), `test_organisation_switcher.py` (educator_interface plus its playwright dir), `test_denied_experience.py` (educator_interface plus its playwright dir). This can be a pytest rootdir/`__init__` hazard only where `__init__.py` is missing; `content_engine/tests/__init__.py` exists, so not checked app by app.

### Naming inconsistencies

- Suffix style `*_tests.py` (`form_ui_tests.py`) next to `test_*.py`.
- `tests.py` allowed by config but unused here.
- Helper modules with leading underscore (`accounts/tests/_auth_page_helpers.py`) against bare names (`panel_framework/tests/view_helpers.py`, `reports/tests/gather_input_builders.py`).
- Test class style mixed with functions: `base/tests/test_config.py` uses `class TestVisitorCountryHeaderDefault`; most files use bare functions. SKILL requires `test_<subject>_<condition>_<expected>`.

### Markers

Counts (static, `pytest.mark.<x>` hits):

| Marker | Where |
|---|---|
| `fls_internal` | `content_engine/tests/test_demo_content_*.py` (6 files, file-level), `blog/tests/test_demo_articles.py`, `learner_interface/tests/test_demo_content_course_card.py`, `contrib/conformance/tests/` (3 files, file-level), `qa_helpers/tests/` (3 files, file-level), `claude_plugins/fls-content/validate/tests/test_validator.py` (2 tests) |
| `ci_only` | `accounts/tests/test_login_rate_limit.py` (1), `test_signup_rate_limit.py` (2); real-time windows |
| `weasyprint` | `reports/tests/test_pdf_integration.py` (file-level, plus `requires_tailwind_bundle`), `reports/tests/test_render.py` (one test, line 266) |
| `playwright` | per-file and per-test, 52 files |

Coherence of the split:

- `pyproject.toml` `addopts` excludes `ci_only and weasyprint` by default; CI overrides with `-m "not playwright"` (unit job) or `-m playwright` (browser job), which re-includes `ci_only` and `weasyprint` in the unit job.
- `fls_internal` is never excluded by FLS itself; only a downstream command (`update_fls.md`) excludes it.
- `contrib/conformance` tests are `fls_internal` by marker, yet the SKILL calls them "both collected tests and importable probes". They exist to be shipped and imported by downstream (the code is excluded from `ruff` test rules under "Conformance suite" in `pyproject.toml` line 215).
- `qa_helpers/tests/` (5 files, 465 lines): three are `fls_internal`; two (`test_qa_create_application_review_accounts.py`, `test_qa_create_report_cohort.py`) are unmarked. `pyproject.toml` omits `*/qa_helpers/*` from coverage with a comment saying only the destructive commands should carry tests. All five sit in the mirroring baseline.
- `freedom_ls/dev_tools/tests/` (5 files, 266 lines) tests destructive danger commands.
- `tests/` (top-level, about 4400 lines): dev-script tests (`test_land_on_main.py`, `test_rebase_lost_change_check.py`, `test_stale_dbs.py`, `test_diagnose.py`, `test_upstream_change_scan.py`, `test_reap_playwright_mcp.py`, `test_design_screenshots.py`, `test_dev_db_scripts.py`, `test_entrypoints.py`) and the test-organisation tooling tests. They are run by default (`testpaths` includes `tests` and `claude_plugins/fls-content`) and are not marked `fls_internal`, though they cannot apply to a downstream (and `setuptools.packages.find` includes only `freedom_ls*`, so `tests/` never ships).

## 4. What a cleanup must not break

- **Distribution packaging**: `pyproject.toml` `[tool.setuptools.packages.find]` has `include = ["freedom_ls*"]` and excludes `media*`, `config*`, `static*`, `dev_db*`, `gitignore*`, `node_modules*`, `demo_content*`. It does not exclude `tests`, so `freedom_ls/*/tests/**` ship inside the package. Top-level `tests/` and `claude_plugins/` do not. `demo_content/` is excluded from the distribution, which is the stated rationale for `fls_internal` (`claude_plugins/fls-dev/resources/testing.md` line 68: a test reading a `demo_content/` file excluded from the packaged distribution gets file-level `fls_internal`).
- **Downstream contract**: a concrete project runs `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` (SKILL; `claude_plugins/fls-dev/commands/concrete/update_fls.md` lines 148, 165, 212, 235 use it as a test gate; also `claude_plugins/fls-dev/resources/playwright-testing.md`). Unmarked tests are the portable set, so deleting, moving or re-marking a test changes what downstream runs. Moving helper modules (`freedom_ls/tests/*`, per-app `tests/conftest.py`) can break downstream fixture use: `freedom_ls/tests/app_guards.py` and `playwright_fixtures.py` are imported as `freedom_ls.tests...`. `course_applications/tests/conftest.py` and `test_collection_safety.py` guard optional-app collection (`collect_ignore_glob`); merges must preserve that for downstream projects that do not install `course_applications` or similar. `site_aware_models` and `role_based_permissions` tests borrow downstream models.
- **Collection safety**: `freedom_ls/tests/app_guards.py` `app_not_installed(...)`.
- **Coverage gate**: `addopts` has `--cov --cov-branch --cov-fail-under=73`. Coverage source is `freedom_ls`; omitted `*/migrations/*`, `*/tests/*`, `*/conftest.py`, `manage.py`, `*/qa_helpers/*`. The playwright CI job runs with `--no-cov`, so playwright tests contribute nothing to the 73 percent gate; the gate is computed only from the `-m "not playwright"` unit job (which includes `ci_only`, `weasyprint` and `fls_internal` tests). Removing tests that carry unique coverage (notably `weasyprint`/`reports` `render.py`, `content_save.py`, `learner_interface/views.py`) lowers the number. Local `uv run pytest` without those markers also applies the same threshold.
- **CI jobs** (`.github/workflows/tests.yml`): `lint` (ruff, ruff format, `generate_app_map.py --check`, `lint-imports`, `check_test_mirroring.py`), `type-check` (`mypy .`, includes tests; `pyproject.toml` has a `[[tool.mypy.overrides]]` for `*.tests.*`), `unit-tests` (`timeout-minutes: 10`, Postgres 17, `pytest -m "not playwright"`, runs serially, no `-n auto`), `playwright-tests` (`timeout-minutes: 15`, `pytest -m playwright --no-cov`, uploads traces from `test-results/`). The 10-minute unit-job timeout and the 15-minute browser-job timeout are limits the cleanup must stay under; pytest `timeout = 300` per test in config.
- **Baselines are delete-only and stale-checked**: removing or renaming a test file listed in `mirroring_baseline.txt` or `import_baseline.txt` requires deleting its lines in the same change, or `check_test_mirroring.py` / `lint-imports` fails. Adding a new non-mirroring file fails (lines are never added). Moving a file into a mirroring subpackage must pass the mirroring check or be added to `mirroring_exemptions.txt` (empty today).
- **Tests of the tooling**: `tests/test_check_test_mirroring.py`, `tests/test_generate_app_map.py`, `tests/test_playwright_fixtures.py`, `tests/test_conftest.py` assert on the tooling and the shared fixtures; changing `freedom_ls/tests/playwright_fixtures.py` or the root conftest layering interacts with them.
- **Randomised order and sockets**: `pytest-randomly` is installed (no `-p no:randomly`), `--disable-socket --allow-hosts=127.0.0.1,::1` in `addopts`, `--strict-markers` (any new marker must be declared). `panel_framework/tests/conftest.py` session-scoped `_panel_test_tables` is autouse and interacts with `transaction=True` playwright tests (it re-creates permissions per test).
- **Skills that reference the suite** (to keep consistent if anything moves): `claude_plugins/fls-dev/skills/testing/SKILL.md`, `claude_plugins/django-stack/skills/testing/SKILL.md`, `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md`, `claude_plugins/fls-dev/resources/testing.md`, `claude_plugins/fls-dev/resources/playwright-testing.md`, `claude_plugins/django-stack/resources/testing.md`, `claude_plugins/fls-dev/commands/concrete/update_fls.md`. The testing SKILL names specific paths (`panel_framework/tests/stub_panels.py`, `reports/tests/gather_input_builders.py`, `content_engine`'s `test_demo_content_*.py`).

## Notes on confidence

- Test function counts per file were measured only for `reports`, `learner_interface/test_form_runner_views.py` and by grep counts where stated; the rest are line counts.
- Per-app mirroring baseline counts were tallied from reading the file and are approximate.
- Whether `educator_interface` panels live elsewhere (making its source count low) was not verified.

status: ok
