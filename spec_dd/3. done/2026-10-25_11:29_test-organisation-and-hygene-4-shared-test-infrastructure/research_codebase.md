# Research: codebase — what spec 4 touches, reuses or conflicts with

Scope: `freedom_ls/conftest.py`, `freedom_ls/tests/`, `SiteFactory`, optional-app guards, the `student_*` dirs, spec 3's checks and baselines. Facts only, except where the data forces a placement.

## Headline corrections to the idea (read first)

1. **The `SiteFactory` edge is not in a baseline file.** `test_organisation/import_baseline.txt` has no `accounts.factories` line. Imports of `freedom_ls.accounts.factories` are *allowed* by a generated "user-model app's factories" allowance, written into `test_organisation/import_contracts.toml` (`# allowance: the user-model app's factories`; `generate_app_map.py` `allowance_lines`, lines 502-519). That file is generated ("Do not hand-edit"), so spec 4 deletes no hand-edited baseline lines for `SiteFactory`. It regenerates two files: `import_contracts.toml` and `docs/app_structure.md` (the "Test-only deps" column).
2. **Moving `SiteFactory` creates one new rule-2 violation: `blog`.** `blog` runtime deps are `base, content_engine` only (`docs/app_structure.md:259`), and the `blog` contract forbids `freedom_ls.site_aware_models`. `freedom_ls/blog/tests/test_views.py:14` imports `SiteFactory` from `accounts.factories` and nothing else from `accounts` (its only allowance line is `blog.tests.test_views -> accounts.factories`, `import_contracts.toml:49`). After the move, that allowance line goes and `blog.tests.test_views -> site_aware_models.factories` is a new forbidden import. Baselines are "lines only ever deleted, never added" (`import_baseline.txt:3-5`), so it cannot be baselined. All other importing apps already have `site_aware_models` as a runtime dep (see §2).
3. **The guard claim is wrong about four apps.** `course_access`, `dev_tools` and `learner_interface` do **not** use `collect_ignore_glob` (§3). Only `course_applications`, `hr_attributes`, `registration_rules` and `blog` (plus `blog/tests/demo_content`) do. The three named apps use module-level `pytest.skip(allow_module_level=True)` or `skipif`, for `course_applications`/`blog` guards.
4. **The three `student_*` dirs do not exist in this worktree.** `Glob freedom_ls/student*/*` returns nothing, whereas `freedom_ls/*/__pycache__/apps*.pyc` returns 34 apps. The audit's claim (§2) was true for the main checkout; here the deletion is a no-op. There is nothing tracked to delete.
5. **Playwright concentration is not "narrow".** 12 apps have `tests/playwright/` dirs (§1.4), so a "scope to Playwright-only dirs" change touches ~12 apps' dirs. Placement details below.

## 1. `freedom_ls/conftest.py` and `freedom_ls/tests/`

### 1.1 Layout

- `/conftest.py` (repo root, 18 lines): `from freedom_ls.conftest import *  # noqa: F403` plus `pytest_xdist_auto_num_workers` (caps `-n auto` at 4). So the real chain is root conftest -> `freedom_ls/conftest.py` -> wildcard of `freedom_ls/tests/playwright_fixtures.py`. A *second* wildcard layer: names reach pytest only via the root `conftest.py`'s own wildcard re-export.
- `freedom_ls/conftest.py` is 412 lines. It is *not* a package-less rootdir conftest: `pyproject.toml` `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`, so the top-level `/tests/` (plugin script tests) also sees the root conftest's fixtures and autouse fixtures.
- `freedom_ls/tests/`: `__init__.py`, `app_guards.py`, `demo_content_fixtures.py`, `images.py`, `playwright_fixtures.py`, `playwright_helpers.py`, `site_context.py`, `storages.py`.

### 1.2 Inventory of `freedom_ls/conftest.py` (line numbers)

Autouse (all apps' tests):
- `_disable_force_site_name` (38), `_isolate_media_root` (44; overridden in `demo_content_fixtures.py:80` for demo-content dirs), `_disable_preview_overrides` (68), `_clear_course_access_backend_cache` (82; imports `course_access.loader` unconditionally), `_clear_rule_kind_cache` (103; guarded by `apps.is_installed("freedom_ls.registration_rules")`), `_clear_messaging_policy_cache` (123; imports `comms.messaging_loader` unconditionally).
- From the wildcard (`playwright_fixtures`): `reset_local_storage` (autouse, session-wide but a no-op unless `page`/`logged_in_page` is in `request.fixturenames`).

Opt-in fixtures: `pathless_logo_storage` (57), `site` (153; parametrisable; overridden in `demo_content_fixtures.py:74`), `make_temp_file` (168), `mock_site_context` (187), `logged_in_client` (194, factory), `staff_client` (206), `course_with_topic` (213, factory), `article_with_image` (229), `course_with_scored_quiz` (247, factory returning `(course, form, question, right, wrong)`), `sit_quiz` (289, factory), `site_aware_request` (321), `live_server_site` (326), `mock_legal_blobs` (340), `legal_repo_mock` (391).

Plain functions: `reverse_url` (137), `_seed_default_legal_docs` (382, private).

Module-level imports: `UserFactory` from `accounts.factories` (16, a rule-2-allowed edge), `site_context`, `storages` helpers, and the wildcard at line 20. `course_with_scored_quiz` and `sit_quiz` import `form_engine`, `learner_progress.factories` and `content_engine` lazily inside the fixture bodies (not at module top), so they are not import-time dependencies.

### 1.3 Usage counts (grep occurrences, `freedom_ls/`, conftest excluded unless noted)

- `course_with_scored_quiz` + `sit_quiz`: **69 occurrences in 4 test files across 2 apps**: `learner_progress` (`test_admin.py` 4, `management/commands/test_recalculate_progress_percentages.py` 15, `test_models.py` 14) and `learner_interface` (`views/test_course_player.py` 34). The audit's "~5-6 of 29 apps" overcounts; it is two apps. Both fixtures are also defined only once, in the root conftest (2 definition hits).
- `course_with_topic`: 335 hits in 11 test files across 6 apps: `learner_interface` (`test_course_detail` 76, `test_course_listing` 101, `test_seo` 53, `test_course_access` 62, `test_course_player` 8), `course_applications` (10), `learner_management` (12), `accounts` (6), `comms` (2), `learner_progress` (2), `educator_interface` (2).
- `staff_client`: 879 hits in 20 test files across **15 apps**: `course_applications`, `form_engine`, `hr_attributes`, `site_aware_models`, `registration_rules`, `panel_framework` (a Playwright test), `educator_interface`, `organisations`, `content_base`, `course_interest`, `learner_progress`, `referral_tracking`, `content_engine`, `messaging_policy`, `accounts`, `learner_management`.
- `logged_in_client`: 1057 hits in 35 test files across 10 apps: `course_applications`, `learner_management`, `learner_interface`, `registration_rules`, `educator_interface`, `comms`, `form_engine`, `messaging_policy`, `learner_progress`, plus `google_tag`/others not in this grep. Dominant: `comms` (279 + 138 + 20), `learner_interface` (104 + 68 + 62).
- Misc root fixtures (`article_with_image`, `pathless_logo_storage`, `legal_repo_mock`, `mock_legal_blobs`, `make_temp_file`, `site_aware_request`): 243 hits in 23 files; heavy in `blog`, `content_engine`, `accounts`, `educator_interface`, `reports`.
- Importing `reverse_url` by hand from `freedom_ls.conftest`: `course_applications/tests/playwright/test_application_form_flow.py:13`, `comms/tests/playwright/test_notifications_flow.py:22`, `.../test_messaging_flow.py:25`, `blog/tests/playwright/test_article_flow.py:19`, `learner_interface/tests/playwright/helpers.py:9` and `.../test_course_browse_flow.py:23`; and `freedom_ls/tests/playwright_fixtures.py:147` does `from conftest import reverse_url` (the *repo-root* conftest, imported by bare module name, "local to avoid circular import"). `reverse_url` is a Playwright-only helper in practice, living in the root conftest.

### 1.4 Playwright: re-export and where it is used

`freedom_ls/tests/playwright_fixtures.py` defines, with no `__all__`: `playwright` (session-scoped override that closes DB connections after pytest-playwright stops, line 96), `reset_local_storage` (autouse, 103), `logged_in_user` (171), `logged_in_page` (192), plus helpers `close_db_connections_before_playwright_stops`, `_login_via_ui` (145), `_LOGGED_IN_PASSWORD` (167), `_PAGE_FIXTURE_NAMES`. Because there is no `__all__`, the wildcard also re-exports every public name it imports (`pytest`, `EmailAddress`, `Page`, `Playwright`, `expect`, `UserFactory`, `User`, `connections`, ...). Underscore names are *not* exported by the wildcard, which is why `educator_interface/tests/playwright/conftest.py:14` imports `_LOGGED_IN_PASSWORD, _login_via_ui` directly from the module.

Counts of `logged_in_page|logged_in_user|live_server_site|reset_local_storage` in tests: 34 files, concentrated in `comms` playwright (48 + 12), `course_applications` playwright (35), `learner_interface` playwright (9 + 4), `educator_interface` playwright (many), `panel_framework`, `base`, `form_engine`, `messaging_policy`, `referral_tracking`, `registration_rules` playwright. `google_tag/tests/test_context_processors.py` matches the pattern twice but has no `live_server`/`playwright`/`reverse_url` use (matched on `logged_in_user`-like text; not a Playwright test). `tests/test_playwright_fixtures.py:7` imports from `freedom_ls.tests.playwright_fixtures` directly (a root-level `/tests/` file, outside any app).

Playwright test dirs (`freedom_ls/*/tests/playwright/`, 12 apps; every test file carries `pytest.mark.playwright`, 29 files with the marker): `base`, `blog`, `comms`, `course_applications`, `educator_interface` (13 test files + `conftest.py` + `helpers.py`), `form_engine`, `learner_interface` (+ `helpers.py`), `messaging_policy`, `panel_framework` (+ `assertions.py`), `referral_tracking`, `registration_rules`. (11 listed by directory; `educator_interface`'s own `playwright/conftest.py` is the only conftest in any of them.) Each dir has an `__init__.py`. None of the other apps' Playwright dirs has a conftest. Non-`playwright/`-dir Playwright users: `freedom_ls/panel_framework/views.py`, `panel_framework/tests/stub_panels.py` and `course_applications/tests/invariants/test_collection_safety.py` mention `playwright`/`conftest`, which are mentions, not fixture consumers.

Fixture interplay: `logged_in_user` depends on `db`, `live_server_site`, `mock_site_context` (all root fixtures); `logged_in_page` on `page`, `live_server`, `logged_in_user`. `fls-dev:playwright-tests` skill (`SKILL.md:18-20`) states every browser test is `@pytest.mark.django_db(transaction=True)` (the browser's DB connection must see test data; transaction=True flushes the DB after each test, so a cached session cookie dies, so login is per-test through the UI). The module docstring (`playwright_fixtures.py:26-46`) says the same. The session-scoped `playwright` override and the autouse `reset_local_storage` are therefore the only globally-scoped parts of the re-export; `logged_in_*` are function-scoped and opt-in.

Key consequences for the "scope the wildcard" question:
- The `playwright` session-fixture override needs `pytest-playwright` to be the plugin that defines `playwright`; it only matters where a Playwright test runs.
- `reset_local_storage` is autouse and runs in every test but early-returns when no `page`/`logged_in_page` is requested.
- Moving the re-export to conftests under 11 `playwright/` dirs would need the same conftest content (or an import) in each, since pytest only applies a conftest to its own dir and below. `educator_interface/tests/playwright/conftest.py` already depends on `live_server_site` / `mock_site_context` from the *root* conftest, so those two stay root-level whichever way it goes.
- `logged_in_page` consumers outside `playwright/` dirs: none found (grep of non-`playwright/` paths shows only `freedom_ls/conftest.py`, `playwright_helpers.py`, `playwright_fixtures.py`, `panel_framework/views.py`, `stub_panels.py`, `test_collection_safety.py`).

### 1.5 `app_guards.app_not_installed` (`freedom_ls/tests/app_guards.py`)

`app_not_installed(app_label_dotted: str) -> bool` returns `not apps.is_installed(app_label_dotted)`. It takes the **dotted module path** (e.g. `"freedom_ls.course_applications"`), not an app label; `apps.is_installed` resolves both a plain path and an AppConfig-path `INSTALLED_APPS` entry. Callers must run after Django setup (pytest-django does this before conftest collection of app dirs).

### 1.6 Other `freedom_ls/tests/` modules

- `site_context.py`: `site_context` (ctx manager), `drop_ambient_request`; used by `mock_site_context` and `demo_content_fixtures.py`.
- `demo_content_fixtures.py`: module-scoped `demo_site`, `demo_media_root`, `loaded_demo_content`; function-scope `site` and autouse `_isolate_media_root` that *override* the root ones. Star-imported by `blog/tests/demo_content/conftest.py` (and learner_interface/content_engine demo_content conftests).
- `storages.py`: `PathlessFileSystemStorage`, `bind_pathless_logo_storage` (used by root `pathless_logo_storage`).
- `images.py`: PNG/JPEG/GIF byte builders (e.g. `png_bytes`, imported by `course_applications/tests/playwright/test_application_form_flow.py:16`).
- `playwright_helpers.py`: `assert_no_horizontal_overflow(page)`.

## 2. `SiteFactory`

- Defined at `freedom_ls/accounts/factories.py:12-25`: `DjangoModelFactory` for `django.contrib.sites.models.Site`, `django_get_or_create = ("name",)`, `name = Sequence("TestSite{n}")`, `domain = LazyAttribute(name.lower() + ".example.com")`. Docstring says it is not a `SiteAwareFactory`. It is the only thing in that file that imports `django.contrib.sites.models.Site` (line 6).
- Other classes in `accounts/factories.py` (`UserFactory`, `SiteSignupPolicyFactory`, `LegalConsentFactory`, `EmailAddressFactory`) do **not** reference `SiteFactory` (no `SubFactory(SiteFactory)`, no dotted-string reference anywhere). `accounts/factories.py` already imports `SiteAwareFactory` from `freedom_ls.site_aware_models.factories` (line 9).
- `freedom_ls/site_aware_models/factories.py` **already exists** (49 lines): `_get_current_site()` and `SiteAwareFactory` (abstract; `site = LazyFunction(_get_current_site)`; `_create` bypasses custom managers). It imports `django.contrib.sites.models.Site` already (line 5), and imports `freedom_ls.site_aware_models.models._thread_locals`. It has no `accounts` import, so no cycle if `SiteFactory` lands there. `site_aware_models/tests/test_factories.py` exists (tests this module; baseline line `test_factories -> accounts.models`).
- No non-test code imports `SiteFactory` (grep of `freedom_ls/` excluding `**/tests/**`: only the definition). `dev_tools`, `qa_helpers`, management commands, `demo_content/`, `config/`, `tests/` (root), `claude_plugins/`, `docs/`: no hits. Docs: `claude_plugins/fls-dev/resources/testing.md:26` says "Factory import: `from freedom_ls.accounts.factories import UserFactory`" (only `UserFactory`, not `SiteFactory`).
- Spec files mentioning `SiteFactory` (non-code): `spec_dd/1. next/` ideas for specs 5, 6, 10, 15, the roadmap, the audit.

Importers (39 test files; `from freedom_ls.accounts.factories import ... SiteFactory`). Multi-line imports marked (M):
- accounts: `tests/test_utils.py:11`, `test_allauth_account_adapter.py:19` (M), `test_account_setup.py:35`, `test_legal_docs.py:16`, `test_models.py:12` (M)
- blog: `tests/test_views.py:14` (SiteFactory only; uses at 69, 301, 613)
- comms: `tests/test_messaging.py:15`, `test_messaging_views.py:18`, `test_notify.py:16`, `test_views.py:15`
- content_engine: `tests/management/commands/test_content_save.py:21`, `tests/models/test_courses.py:18`, `tests/models/test_articles.py:16`, `tests/templatetags/test_content_tags.py:10`
- course_applications: `tests/test_receivers.py:11` (M), `test_claims.py:20`, `test_views.py:29` (M)
- course_interest: `tests/test_admin.py:22`
- educator_interface: `tests/test_actions.py:19`, `test_course_visibility_and_interest.py:15`, `invariants/test_organisation_isolation.py:30`, `invariants/test_permission_matrix.py:24`
- form_engine: `tests/test_views.py:13`
- learner_interface: `tests/views/test_course_listing.py:17` (M), `tests/templatetags/test_course_card_tags.py:14`
- learner_management: `tests/test_utils.py:20`, `test_learner_actions.py:5`, `test_queries.py:22`
- learner_progress: `tests/test_utils.py:5`
- messaging_policy: `tests/test_policy.py:22`, `test_admin.py:17`
- organisations: `tests/test_models.py:16`, `test_signals.py:7`
- registration_rules: `tests/test_evaluation.py:15`, `test_tasks.py:7`
- reports: `tests/test_gather.py:13`, `test_tasks.py:9`, `test_indexes.py:20`
- role_based_permissions: `tests/test_models.py:11`
- site_aware_models: `tests/test_slugs.py:5`, `test_models.py:14` (M)
- webhooks: `tests/test_delivery.py:11`, `test_events.py:239` and `:295` (function-local imports)

Files importing *only* `SiteFactory` from `accounts.factories` (their `accounts.factories` allowance line disappears from `import_contracts.toml` after the move): `blog/test_views`, `content_engine` (4 files), `course_interest/test_admin`, `learner_interface` `test_course_card_tags`, `learner_progress/test_utils`, `messaging_policy/test_admin`, `organisations/test_signals`, `registration_rules` (2), `webhooks` (3 modules) and `site_aware_models/test_slugs`. Many other apps already have a runtime dep on `accounts` (no allowance line existed for them).

Rule-2 effect of the new import path (`docs/app_structure.md:255-292`): all importing apps have `site_aware_models` in their runtime deps (accounts, comms, content_engine, course_applications, course_interest, educator_interface, form_engine, learner_interface, learner_management, learner_progress, messaging_policy, organisations, registration_rules, reports, role_based_permissions, webhooks; site_aware_models itself) **except `blog`**. Also, the "Test-only deps" column drops `accounts` for any app whose only `accounts` import was `SiteFactory` and which has no `accounts` runtime dep: `blog` (listed `accounts`, but gains `site_aware_models` instead, still a test-only dep), `content_engine` (audit: "accounts (SiteFactory only)"), `webhooks`. `docs/app_structure.md` and `import_contracts.toml` are both CI-checked for freshness (`generate_app_map.py --check`).

## 3. Optional-app guards

Settings: `config/settings_base.py:131-139` lists under `# COURSE ACCESS` `course_access`, `course_applications`, `course_interest`, `course_recommendations`, and `learner_interface` under `# LEARNER INTERFACE`, all as plain `"freedom_ls.<app>"` entries, unconditionally in `INSTALLED_APPS`. `hr_attributes`/`registration_rules`/`blog` are in the same list (lines 110, 123-124). `config/settings_dev.py:58-62` appends `freedom_ls.qa_helpers` and `freedom_ls.dev_tools`. A downstream project drops apps by editing its own `INSTALLED_APPS`. `app_not_installed` takes the dotted path `"freedom_ls.course_interest"` / `"freedom_ls.course_recommendations"`.

`collect_ignore_glob` conftests that exist today (exact pattern, 3-4 lines):
- `course_applications/tests/conftest.py:7-9`: `collect_ignore_glob: list[str] = []`, `if app_not_installed("freedom_ls.course_applications"): collect_ignore_glob = ["test_*.py"]`. (Same file also holds an autouse fixture at line 12 and the `gated_course_with_form` helper.)
- `hr_attributes/tests/conftest.py:5-7`, `registration_rules/tests/conftest.py:14-16`, `blog/tests/conftest.py:11-13`, `blog/tests/demo_content/conftest.py:4-6` (identical pattern).

Per-module `pytest.skip`/`skipif` guards in the other named apps (no conftest guard): `course_access/tests/test_visibility_enforcing_backend.py:21`, `test_overrides.py:26`, `test_analytics_events.py:106`; `dev_tools/tests/test_danger_commands_with_applications.py:13`; `learner_interface/tests/views/test_course_access.py:29`, `tests/demo_content/test_course_card.py:19`, `tests/playwright/test_course_browse_flow.py:430`, `tests/test_checks.py:67`; `course_applications/tests/test_receivers.py:16`, `.../playwright/test_application_form_flow.py:22`. `course_applications/tests/invariants/test_collection_safety.py` (mentioned in `test_organisation/mirroring_exemptions.txt:22`) tests the collection skip by running pytest in a subprocess against a guarded module.

`course_interest` and `course_recommendations`: **neither has `tests/conftest.py`**. Tests dirs exist with `__init__.py`: `course_interest/tests/{test_admin,test_models,test_queries,test_views}.py` and `course_recommendations/tests/{test_models,test_queries}.py`. These import `freedom_ls.course_interest.*`/`course_recommendations.*` at module top (e.g. `course_interest/tests/test_models.py:11` imports `course_interest.factories`), so collection fails if the app is absent. Notably, `course_recommendations/tests/test_*.py` import only `accounts.factories`, `content_engine.factories` and their own app (`models`/`queries`). The `course_interest/tests/test_views.py` imports `accounts.tests._auth_page_helpers._next_param` (a rule-1/2 point for spec 6, not this one). Both apps' runtime deps include `site_aware_models`, `accounts`, `content_engine`; `course_interest` also `course_access`.

Cross-app consumers of the optional apps (relevant to whether a guard alone is enough downstream): `educator_interface/tests/test_course_visibility_and_interest.py` imports `course_interest.factories` (baseline line `import_baseline.txt:45`; also `educator_interface -> course_interest` is a test-only dep); `learner_interface` has runtime deps on both `course_interest` and `course_recommendations`. Guards on `course_interest`'s own tests do not cover those.

## 4. `student_*` directories

- `freedom_ls/student_interface`, `student_management`, `student_progress`: **absent in this worktree** (`Glob freedom_ls/student*/*` returns nothing). `.gitignore` excludes `__pycache__/` and `*.py[oc]`, so they are never tracked; they exist only as stale pycache in other checkouts.
- References to `student_(interface|management|progress)` anywhere outside `spec_dd/3. done/`: only spec/research markdown (`spec_dd/2. in progress/in-app-feedback/2. plan.md`, `spec_dd/1. next/...` research files, this spec's idea). **No hits in `config/`, `pyproject.toml`, `docs/`, `.github/`, any `.py`.**
- No baseline line (`import_baseline.txt`, `mirroring_baseline.txt`, `mirroring_exemptions.txt`, `import_contracts.toml`) names a `student_*` path. The checks find apps via `apps.py` (`find_apps`), which a pycache-only dir lacks, so spec 3 never saw them. So there are **zero rule-1/rule-2 baseline entries for these dirs**; the idea's "any rule-1 entries the three deleted directories left" resolves to none.

## 5. Spec 3's enforcement checks and baselines

Config (`pyproject.toml:96-102`, `[tool.test_organisation]`): `user_model_app = "freedom_ls.accounts"`, `declared_edges = test_organisation/declared_edges.toml`, `import_contracts = test_organisation/import_contracts.toml`, `import_baseline = test_organisation/import_baseline.txt`, `mirroring_baseline = test_organisation/mirroring_baseline.txt`, `mirroring_exemptions = test_organisation/mirroring_exemptions.txt`.

Files:
- `test_organisation/import_baseline.txt` (107 lines): hand-edited, "lines are only ever deleted, never added", grouped under `# <app>` headers, format `importer -> imported`. A stale line (no longer a real violation) fails the check.
- `test_organisation/import_contracts.toml`: **generated** by `generate_app_map.py` (banner at line 1), one `forbidden` contract per app with tests; `ignore_imports` = `# allowance` lines then `# baseline` lines. CI and pre-commit fail on drift.
- `test_organisation/mirroring_baseline.txt`: hand-edited (stale lines fail). `mirroring_exemptions.txt`: reasoned permanent exemptions (e.g. `.../tests/playwright/` is *not* listed, so Playwright dirs are exempt by script logic, not by this file; `demo_content/`, `invariants/`, `components/` dirs are listed).
- `test_organisation/declared_edges.toml`: one edge, `base -> learner_management`.
- `docs/app_structure.md`: generated dependency graph; "Test-only deps" column is the rule-2 reference (`docs/app_structure.md:255-292`).

How they run (`.pre-commit-config.yaml:74-85`, `.github/workflows/tests.yml:26-28`):
- `uv run python claude_plugins/django-stack/scripts/generate_app_map.py --check` (CI line 26; pre-commit `app-map-fresh`): fails if `docs/app_structure.md` or `import_contracts.toml` would differ.
- `uv run lint-imports --config test_organisation/import_contracts.toml` (pre-commit `lint-imports`, CI 27).
- `uv run python claude_plugins/django-stack/scripts/check_test_mirroring.py` (pre-commit `test-mirroring`, CI 28). `--print`-style mode prints current violations in baseline format and writes nothing (`check_test_mirroring.py:204-209, 239`); `generate_app_map.py` without `--check` regenerates `docs/app_structure.md` and `import_contracts.toml`.
- They run outside pytest. Tests of the scripts live at `tests/test_check_test_mirroring.py` and `tests/test_generate_app_map.py` (root `/tests/`).

Lines this spec's fixes retire or change:
- `import_baseline.txt`: **none about `SiteFactory`**. None about `freedom_ls/tests` or `freedom_ls/conftest.py` (those are not an app per `find_apps`; no baseline line mentions them). None about `student_*`. The only `accounts`-adjacent baseline lines are test-module -> `accounts.models` / `accounts.factories`-unrelated entries owned by later specs (e.g. `site_aware_models.tests.test_factories -> accounts.models`, spec 5).
- `mirroring_baseline.txt`: nothing in scope (`freedom_ls/tests/*` and the root conftest are not under an app's `tests/`; `course_interest`/`course_recommendations` have no conftest, hence no new mirroring entries once one is added, and conftest files are exempt per the roadmap's assumption).
- `import_contracts.toml` (generated): allowance lines `... -> freedom_ls.accounts.factories` vanish for the SiteFactory-only importers listed in §2 (e.g. `blog.tests.test_views`, `content_engine.tests.{management.commands.test_content_save, models.test_articles, models.test_courses, templatetags.test_content_tags}`, `site_aware_models.tests.test_slugs`, `webhooks.tests.test_delivery`/`test_events`). A new violation appears for `blog` (§headline 2). `site_aware_models`' own contract: `site_aware_models.tests.test_models -> accounts.factories` stays only if the file still imports `UserFactory` (it imports a multi-line `SiteFactory` list at line 14).

## 6. pytest config

`pyproject.toml:78-94`: `DJANGO_SETTINGS_MODULE = "config.settings_dev"`, `python_files = ["tests.py", "test_*.py", "*_tests.py"]`, `env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]`, `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`, `timeout = 300`. `addopts = --strict-markers -m 'not ci_only and not weasyprint and not dev_tooling' --disable-socket --allow-hosts=127.0.0.1,::1 --tracing=retain-on-failure --screenshot=only-on-failure --dist loadfile`. Markers: `playwright`, `ci_only`, `fls_internal`, `weasyprint`, `dev_tooling` (`--strict-markers`, so a new marker needs registration). No `-p` plugin lines and no `pythonpath`/`rootdir` setting; the rootdir is the repo root (where `pyproject.toml` and the root `conftest.py` sit). `--disable-socket` + `--allow-hosts` is what lets `live_server` work. `DJANGO_ALLOW_ASYNC_UNSAFE` is for Playwright's loop. pytest runs in `prepend` import mode (new test dirs need `__init__.py`; `fls-dev:testing` says so), which is why `playwright_fixtures.py:147` can `from conftest import reverse_url` (root conftest is on `sys.path` as `conftest`).

CI split (`fls-dev:testing` SKILL.md:113): unit job `-m "not playwright and not dev_tooling" --cov`; Playwright job `-m playwright -n auto` (root conftest caps workers at 4).

## 7. Conflicts with other in-progress work

`spec_dd/2. in progress/` contains: `anon-application-improvements`, `auto-run-tailwind-watch`, `compliance-form-randomization`, `content_snapshots`, `deadlines-1-dates-and-overdue`, `educator-interface-8-bulk-operations`, `educator-interface-10-reporting-dashboards`, `educator-interface-11-audit-log`, `in-app-feedback`, `qa-boy-scout-throwaway`, `test-organisation-and-hygene-2-sdd-review-and-boy-scout` and this spec. Only ideas/plans exist (no code in this worktree). Overlaps found by grep:
- `spec 2` (sdd review + boy scout) changes `claude_plugins/sdd/`; no shared file with `freedom_ls/conftest.py`. It may move test files per its boy-scout budget, which could touch `SiteFactory` imports.
- `in-app-feedback/2. plan.md` mentions `student_*` names (text only) and is likely to add tests and perhaps a Playwright test using `logged_in_page`.
- `educator-interface-8/10/11` will add tests and fixtures under `educator_interface/tests/` and `reports/tests/`, which import `SiteFactory` today (educator_interface has 4 importers, reports 3); a rebase of their imports is the only conflict.
- Downstream test-organisation specs in `spec_dd/1. next/` that cite `SiteFactory`: 5 (`site_aware_models`, `role_based_permissions`, `organisations`, `base`), 6 (small apps, includes `course_interest`/`course_recommendations`, `webhooks`), 10 (`content_engine`), 15 (`educator_interface`). They are not started; their ideas already assume `SiteFactory` lives in `site_aware_models`. Spec 6 owns `course_interest`/`course_recommendations` but spec 4 owns the two guard conftests (roadmap row 6 lists those two apps; the guard files go in spec 4).
- Spec 13/14 (`learner_interface`) consume the `course_with_scored_quiz`/`sit_quiz` placement decision; the only consumer apps are `learner_progress` and `learner_interface`.
- `/home/.../freedom_ls/*/tests/` working-tree is clean (`git status` clean at start); no uncommitted competing edits.

## 8. Placement facts that are forced by the data

- `SiteFactory` must go to `site_aware_models/factories.py`, which already exists, already imports `Site` and has no `accounts` import (no cycle). Every importer except `blog` already depends on `site_aware_models` at runtime. `blog` is the open conflict: its test is the only rule-2 casualty.
- `course_with_scored_quiz` + `sit_quiz` have consumers in exactly two apps (`learner_progress`, `learner_interface`), with all `learner_interface` use in a single file, `views/test_course_player.py`. `learner_progress` already has `tests/helpers.py` (named in the `fls-dev:testing` skill). The fixtures need `form_engine`, `content_engine` and `learner_progress` factories; `learner_interface` depends on all three at runtime and `learner_progress` has `content_engine`/`form_engine`, so a conftest in either app is rule-2 clean. A conftest in `learner_progress/tests/` would not be visible to `learner_interface` tests (conftest scoping), so shared use needs either the root conftest (today) or a plain module imported by hand with fixtures re-declared.
- The Playwright wildcard: the module is the only provider of `playwright` (session override), `reset_local_storage`, `logged_in_user`, `logged_in_page`; consumers are in 11 playwright-dir apps. `educator_interface/tests/playwright/conftest.py` already shows the per-dir pattern (own conftest + direct import of module privates).

## Sources

All findings are from the repo files cited inline; no web sources were used.

status: ok
