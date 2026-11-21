# Research: codebase (faster-test-runs-1-fast-password-hasher)

Paths relative to the worktree root. Searches were greps over `*.py`, `*.md`, `*.toml`, `*.sh`, `*.yml`.

## Settings and which module pytest uses

- `config/settings_base.py:247-252`: `PASSWORD_HASHERS = [Argon2PasswordHasher, PBKDF2PasswordHasher, PBKDF2SHA1PasswordHasher, BCryptSHA256PasswordHasher]`. It is the only definition of `PASSWORD_HASHERS` in the repo. `config/settings_dev.py` and `config/settings_prod.py` both do `from .settings_base import *` and never override it.
- `pyproject.toml:85`: `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE = "config.settings_dev"`. `.github/workflows/tests.yml:42` also sets `config.settings_dev`. `manage.py:10` defaults to `config.settings_dev`. `config/wsgi.py` and `config/asgi.py` deliberately leave it undefaulted (`tests/test_entrypoints.py` guards that).
- There is no `settings_test` module. `config/` holds only `settings_base.py`, `settings_dev.py` and `settings_prod.py`.
- `config/settings_dev.py:35`: `TESTING = "test" in sys.argv or "PYTEST_VERSION" in os.environ`. It already gates dev-only apps (`:37`, `:144`) and `testing=TESTING` (`:121`). This is the existing in-settings "under pytest" switch. It only affects FLS's own settings, not a concrete project's.
- `config/settings_dev.py:26`: `AUTH_PASSWORD_VALIDATORS = []` in dev. `settings_base.py:254+` has the real validators (min length 10).
- `argon2-cffi>=25.1.0` is a runtime dependency (`pyproject.toml:25`).
- Other settings modules used by tests:
  - `freedom_ls/panel_framework/tests/standalone_settings.py` (standalone panel-framework run, no FLS conftest or settings). `freedom_ls/panel_framework/tests/test_standalone_fixtures.py:7-30` asserts that run loads no `freedom_ls.conftest` and no other FLS module. A hasher fixture in `freedom_ls/conftest.py` cannot reach that run, and a settings change in `config/` does not either.
  - `settings_no_ca` and `settings_ca_appconfig`, set via `monkeypatch.setenv` in `freedom_ls/course_applications/tests/invariants/test_collection_safety.py:32,70`. They run subprocesses, so a conftest fixture does not reach them.

## Conftest wiring and the pattern to follow

- A root `conftest.py` exists at the repo root. It is 23 lines: `from freedom_ls.conftest import *  # noqa: F403` (line 12), then `del playwright` (line 17), then defines `pytest_xdist_auto_num_workers` (line 20, capped at 4). Its docstring says it "re-exports all fixtures from Freedom-LS conftest". A concrete project's conftest does the same star-import. `freedom_ls/conftest.py` is a normal module, so the star-import brings every fixture, autouse ones included.
- `freedom_ls/conftest.py` autouse fixtures that patch `settings`, all function-scoped via the pytest-django `settings` fixture:
  - `_disable_force_site_name(settings)` at `:45-48` sets `settings.FORCE_SITE_NAME = None`.
  - `_isolate_media_root(settings, tmp_path)` at `:64-74` sets `settings.MEDIA_ROOT`.
  - `_disable_preview_overrides(settings)` at `:109-120` sets `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` and `OVERRIDE_COURSE_ACCESS_TO_FREE` to `False`. Its docstring explains that settings_dev turns them on, so the suite would otherwise inherit them. This is the closest precedent: a conftest autouse override of a dev-settings value so concrete projects inherit it.
  - Non-autouse: `mock_legal_blobs` (`:325`) and `database_task_backend(settings)` (`:393-400`).
  - Other autouse fixtures that do not touch `settings`: `_clear_django_cache`, `_clear_course_access_backend_cache`, `_clear_rule_kind_cache`, `_clear_messaging_policy_cache`, `_clear_deadline_policy_cache`.
- Docs that name this wiring:
  - `claude_plugins/fls-dev/skills/testing/SKILL.md:63` lists the autouse fixtures in `freedom_ls/conftest.py`: `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides`, `_clear_course_access_backend_cache`. A new autouse fixture would extend this line.
  - `claude_plugins/django-stack/resources/testing.md:102`: the project-root `conftest.py` holds project-wide autouse fixtures.
  - `claude_plugins/fls-dev/commands/update_concrete_projects.md:228,236` reads each concrete project's `conftest.py`, and flags "a `conftest.py` fixture whose comment cites an FLS defect".
  - `claude_plugins/fls-dev/resources/concrete_spec_integration.md:94` has a generated file importing `freedom_ls.contrib.conformance`. A project's own `conftest.py` is where project decisions go.
  - I found no doc that spells out "concrete projects star-import `freedom_ls/conftest.py`" beyond the root `conftest.py` itself and the idea text.
- `tests/conftest.py` also exists, as do about 25 per-app conftests. The per-app ones are not relevant to hasher placement.
- Plugin constraint (CLAUDE.md): `claude_plugins/django-stack`, `sdd` and `productivity` stay generic. Any doc update about this fixture belongs in `claude_plugins/fls-dev`, e.g. `skills/testing/SKILL.md`.

## Tests and code that touch hashers or hash formats

No test asserts a hasher name, a hash prefix or a hash format. Greps for `argon`, `pbkdf2`, `md5$`, `identify_hasher`, `get_hasher`, `must_update`, `PASSWORD_HASHERS` and `hashers` over all `*.py` found nothing in tests.

Tests and code that touch passwords:
- `freedom_ls/accounts/tests/panels/personal_details/test_actions.py:588,622,643,665` use `set_password` and `check_password` round-trips (old and new password). These are hasher-agnostic.
- `freedom_ls/accounts/tests/management/commands/test_setup_initial_prod_data.py:73-80` asserts the stored hash is byte-identical on a second run. It compares the hash with itself and does not inspect the format. Lines 65-91 check the printed generated password.
- `freedom_ls/accounts/tests/test_resources.py:94` asserts `user.password not in body`. This is format-agnostic.
- `freedom_ls/course_applications/tests/test_views.py:3645-3650` asserts the password string is unchanged. It is format-agnostic.
- `has_usable_password` and `set_unusable_password` appear in `course_applications/tests/test_claims.py` (720, 776, 802, 824, 894), `test_views.py` (2972, 3531), `accounts/tests/test_account_setup.py:42,189-196`, `test_allauth_pages.py:74`, `educator_interface` tests and `learner_management/tests/test_queries.py:1716`. The unusable marker is `!`-prefixed and independent of the hasher list. `freedom_ls/accounts/account_setup.py:12` imports `UNUSABLE_PASSWORD_PREFIX` for this.
- `freedom_ls/course_applications/tests/test_receivers.py:710` calls `user.set_password("a-new-password")`.
- Production code:
  - `freedom_ls/accounts/models.py:39-62` has `create_user`/`create_superuser` calling `set_password`.
  - `freedom_ls/accounts/management/commands/setup_initial_prod_data.py:71,104` calls `set_password`, on the create branch only.
  - `freedom_ls/api/models.py:77` notes API keys deliberately avoid a password hasher.
  - `freedom_ls/dev_tools/management/commands/create_demo_data.py:144,196` and about 40 `qa_helpers` commands call `set_password`, and `qa_create_bulk_learners.py:22,69` calls `make_password` once. These are dev tooling and run under the dev settings. They are not run in the default pytest selection (marker `dev_tooling` is deselected by default, `pyproject.toml:92`), unless a test of them runs under `-m dev_tooling`.
- Nothing calls `must_update`, a `setter` callback or upgrade-on-login directly. Django's built-in upgrade path is automatic on `check_password`. With a single-entry hasher list, a hash made by the same hasher is never re-hashed.
- Docs describe Argon2 as the production hasher: `docs/product/authentication.md:8,42` and `docs/product/security-and-data-handling.md:9,60,137`. They state the production behaviour, which stays unchanged.
- The only prefix-aware code is `UNUSABLE_PASSWORD_PREFIX` use in `account_setup.py`, which is independent of the hasher.
- So there is no existing test that would break or change meaning under MD5. The idea's "a test about the production hasher opts back in" has no existing user.
- If the fast list were only `[MD5PasswordHasher]`, any stored Argon2 hash could not be verified. No test or migration seeds a pre-hashed Argon2 string, per the greps above.

## UserFactory, factories and fixtures that create users

- `freedom_ls/accounts/factories.py:39-46`: the `password` post_generation hook calls `self.set_password(extracted or self.email)`, then saves `update_fields=["password"]` when `create` is true. Every `UserFactory()` call hashes once, plus a second save. `LegalConsentFactory` (`:87`) and `EmailAddressFactory` (`:104`) reach it through a SubFactory.
- Other hashing in tests and helpers:
  - `freedom_ls/panel_framework/tests/helpers.py:49-52` uses `create_user`.
  - `freedom_ls/panel_framework/tests/test_reference.py:191` uses `create_user`.
  - `freedom_ls/panel_framework/tests/standalone_app/models.py:15-19` is a stub `create_user` with `set_password`.
  - `accounts/tests/test_models.py:142,146` calls `set_password("testpass")`.
- `UserFactory(...password=...)` explicit-password uses appear in 15 test files (42 hits). `accounts/tests/test_views.py` has 7, `course_applications/tests/test_claims.py` 13, `learner_interface/tests/views/test_course_player.py` 8, the rest are Playwright tests or helpers. These are login-by-password flows. Hasher-agnostic, as long as the hasher in force is the same at set and at check time.
- Fixtures in `freedom_ls/conftest.py` that create users: `logged_in_client` (`:258`) and `staff_client` (`:270`). Both are function-scoped.
- Session- and module-scoped fixtures found (`scope="session"|"module"` in `conftest.py` and `test_*.py`):
  - `freedom_ls/panel_framework/tests/conftest.py:54` `_panel_test_tables` (session, autouse): creates stub tables, no users.
  - `freedom_ls/panel_framework/tests/playwright/conftest.py:18` `_reference_css_is_built` (session): no users.
  - `claude_plugins/fls-content/validate/tests/test_validator.py:52` (session): no users.
  - `freedom_ls/base/tests/invariants/test_panel_framework_tailwind.py:56` (module): no users.
  - `freedom_ls/reports/tests/test_render.py:2197,2203,2208` (module): PDF bytes, no users.
  - `tests/test_run_tests.py:1306-1341` (module): spawn real pytest subprocesses.
  - None create users, so a function-scoped `settings` fixture reaches every user-creating fixture.
  - The comment at `pyproject.toml:89-91` mentions a module-scoped demo-content import fixture ("the demo-content import") run once per module. It is not in `scope=` greps, so it may be defined differently, e.g. under `content_engine/tests/demo_content/conftest.py`, `blog/tests/demo_content/conftest.py` or `learner_interface/tests/demo_content/conftest.py`. Not opened. Worth a look at spec time: do these create users?
- Migrations: only `freedom_ls/accounts/migrations/0001_initial.py:23` mentions `password` (the model field). No migration calls `make_password`, `create_user` or `set_password`. The 10 `RunPython` migrations do not hash passwords (greps found none). Test database setup does not hash anything before fixtures run.

## Playwright and live server

- `freedom_ls/tests/playwright_fixtures.py:145-164` `_login_via_ui` drives the allauth login form, filling email and password. `logged_in_user` (`:171-189`) calls `UserFactory(password=_LOGGED_IN_PASSWORD)` with `"testpass"` (`:168`), and `logged_in_page` (`:192-201`) logs in through the form. `educator_interface/tests/playwright/conftest.py` has the educator equivalent (2 `UserFactory` password uses). The login POST is hashed and checked by the live server.
- pytest-django's `live_server` runs the server in a thread in the same process. A function-scoped `settings` fixture mutates `django.conf.settings`, so the live-server thread sees it. The hasher list is read through `settings.PASSWORD_HASHERS` and cached (`get_hashers` is `functools.cache`). pytest-django's `settings` fixture sends `setting_changed`, and Django's `django.test.signals` handler clears that cache for `PASSWORD_HASHERS`. So changing it mid-session reaches both threads. This is from Django's behaviour and not verified in this repo.
- The set and check must use the same hasher during a test. A fixture applies it before the test body and the fixtures that build users, so this holds.

## Test-tier runner

- `.claude/ds/scripts/run_tests.sh` (and `select_tests.sh`) have no hit for `DJANGO_SETTINGS`, `settings`, `export` or `--ds`. They set no settings-relevant env. Settings come only from `pyproject.toml:85`.
- `pyproject.toml:87`: `env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]` (pytest-env). It is the only env mechanism for tests, and it cannot carry a list-valued hasher setting.
- `pyproject.toml:92` addopts: `--strict-markers -m 'not ci_only and not weasyprint and not dev_tooling' ... --dist loadfile`. The marker taxonomy is at `:93-100`.
- A concrete project uses its own settings module and `pyproject.toml`. Whatever the switch is, it must not rely on FLS's `config.settings_dev` or on FLS's `[tool.pytest.ini_options]`. The autouse conftest fixture is the only piece such a project gets for free through its star-import.

## Options the code allows (facts only)

- A fixture in `freedom_ls/conftest.py` using the `settings` fixture and `settings.PASSWORD_HASHERS = [...]`: reaches FLS tests and concrete projects through the star-import. It does not reach the standalone panel-framework run or the subprocess runs.
- A settings-level change would use `TESTING` in `config/settings_dev.py`, and would not reach concrete projects' own settings.
- To opt back in, a test can override `settings.PASSWORD_HASHERS` itself, since the fixture is function-scoped and tests run after it.

## Measured baseline

From `spec_dd/1. next/faster-test-runs/research_test_timings.md:22-31` (swap done through an autouse fixture, every test passing):
- `freedom_ls/course_access`, 230 tests: Argon2 62.3s, MD5 19.8s.
- `educator_interface/tests/invariants/test_permission_matrix.py::test_can_matches_the_matrix`, 20 cases: Argon2 66.8s, MD5 13.3s.

status: ok
