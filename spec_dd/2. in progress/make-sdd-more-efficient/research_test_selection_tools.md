# Research: tooling for targeted pytest runs and a cheaper full run

Scope: pytest 8 + pytest-django on this project. Facts are tagged by source. Claims I could not confirm from a fetched page are marked UNVERIFIED. Recommendations appear only in the final table.

## 0. What the project already has (read from the repo)

- `pyproject.toml` `[tool.pytest.ini_options]`: `addopts` bakes in `--strict-markers -m 'not ci_only and not weasyprint' --disable-socket --allow-hosts=127.0.0.1,::1 --cov --cov-branch --cov-report=term-missing --cov-fail-under=73 --tracing=retain-on-failure --screenshot=only-on-failure`. `timeout = 300`. `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`.
- Dev deps include pytest-xdist 3.8, pytest-randomly, pytest-cov, pytest-socket, pytest-timeout, pytest-playwright, pytest-env. There is no pytest-testmon, no pytest-picked, and no `--reuse-db` / `--no-migrations` anywhere (grep of md/toml/py/yml found none).
- Root `/conftest.py` defines `pytest_xdist_auto_num_workers` capping `-n auto` at `min(4, cpu_count)`, "what the shared dev server can serve". `tests/test_conftest.py` tests it.
- `config/settings_dev.py`: the DB is Postgres at 127.0.0.1:6543. The DB name is derived from the git branch (`branch_to_db_name`), and the test DB is `TEST.NAME = test_<branch-derived name>` with `TEMPLATE: template0`. `application_name` includes `PYTEST_XDIST_WORKER`. So each worktree/branch already has its own test database, and xdist workers get pytest-django's `_gwN` suffix on top (the suffix format is not given on the docs page I fetched).
- `claude_plugins/django-stack/skills/testing/SKILL.md` already says: run the full suite with `uv run pytest -n auto`, run it in background, never start a second full run in the same worktree, "the suite can take more than 10 minutes".
- CI (`.github/workflows/tests.yml`): lint job runs `check_test_mirroring.py` and `lint-imports`; `unit-tests` job runs `uv run pytest -m "not playwright"` (with cov, no `-n`, `timeout-minutes: 10`); `playwright-tests` job runs `uv run pytest -m playwright --no-cov` (`timeout-minutes: 15`). Both CI jobs run without xdist.
- Prior SDD plans (e.g. `spec_dd/3. done/2026-08-22_15:42_learner-terminology-rename/2. plan.md`, gate 3) list `pytest -m "not playwright"` followed by `pytest -m playwright --no-cov` as the full gate.

## 1. pytest-testmon

Facts from sources:
- Mechanism: records dependencies between tests and the code they execute using Coverage.py, compares against current file contents (not git), stores them in `.testmondata`, and updates the DB on each run. https://testmon.org/ and https://github.com/tarpas/pytest-testmon
- Latest release seen: 2.2.0, 2025-12-01; requires Python >= 3.10. https://pypi.org/project/pytest-testmon/ Python 3.13 compatibility is not stated on that page (UNVERIFIED). MIT licensed (GitHub README).
- testmon.org lists blog posts "v1.4 with xdist support is out!" and "Version 2.0 is out!", so xdist support exists at some level; the page text does not say how it behaves with `--cov` or pytest-randomly. https://testmon.org/blog/
- Coverage interaction: the site says `--testmon-nocollect` is "Forced if you run under debugger or coverage". So when pytest-cov/coverage is active, testmon stops collecting dependency data (selection still reads existing data). https://testmon.org/ This directly conflicts with this project's `addopts` `--cov`; a testmon run would need `--no-cov` (the CI playwright job already uses `--no-cov`, so the flag works).
- Selector flags `-m`, `-k`, `--lf` force `--testmon-noselect` (reorders but does not deselect). https://testmon.org/ This project's `addopts` contains `-m 'not ci_only and not weasyprint'`; whether that counts as a forcing `-m` is UNVERIFIED and would need a trial run.
- Non-Python files: testmon.org states static files (txt, xml, other assets) are not tracked. That means Django templates, Tailwind/static, JSON/TOML fixtures are not tracked as dependencies (the page doesn't name templates explicitly; this is an inference). Changing a method parameter can select a large set of tests.
- `--testmon-env` keeps separate data per env/settings; DJANGO_SETTINGS_MODULE is tracked as an environment variable. https://testmon.org/
- pytest-django DB setup, pytest-randomly: no source found stating compatibility or conflict. UNVERIFIED. testmon docs say deselected/executed sets vary and can expose hidden order dependencies, which matters here because pytest-randomly is on.
- Worktrees: `.testmondata` is a file in rootdir; each git worktree has its own rootdir and so would build its own DB, starting with a cold full run (no sharing). The first run per worktree/branch is therefore a full run with `--no-cov`.
- Gotcha for LLM workflow: first run builds data (slow, tracing overhead); testmon keys on file contents so a branch switch changes selection.

Searches for testmon + xdist/coverage issue threads returned only pytest-cov issues (e.g. https://github.com/pytest-dev/pytest-cov/issues/667, /604), nothing testmon-specific.

Invocation: `uv run pytest --testmon --no-cov -p no:randomly` (the `-p no:randomly` is not required; shown only as a way to isolate order effects). With xdist: `--testmon -n 4 --no-cov` (UNVERIFIED on this stack).

## 2. pytest-picked

- `pytest --picked` runs tests from modified/untracked test files and test folders per git; default mode is unstaged; `--mode=branch --parent-branch=<name>` compares the branch against a parent (default parent is "main"); `--picked=first` runs picked tests first then the rest. https://github.com/anapaulagomes/pytest-picked
- It maps changed files that are themselves tests (or test folders); it does not map a changed source file to its tests. In the README example, it selected modified `tests/test_board.py` and the `tests/api/` folder.
- Maintenance: the README page shows no release list/date (could not determine); copyright footer 2026. Not confirmed as maintained.
- Consequence: useful for "re-run the tests I just wrote/edited", not for regression coverage of changed source. A mirror-map (section 3) is a superset for this project.
- Invocation: `uv run pytest --picked --mode=branch --parent-branch=main --no-cov`.

## 3. Mirror-map selection (project-specific)

The mapping rule from `claude_plugins/django-stack/scripts/check_test_mirroring.py`:
- Collected test files: `test_*.py`, `*_tests.py`, `tests.py`.
- Conforming location: `<app>/tests/<sub...>/test_<name>.py` where `<app>/<sub...>/<name>.py` exists, or `<app>/<sub...>/<name>/__init__.py` exists (package). So production `freedom_ls/<app>/<sub>/foo.py` -> `freedom_ls/<app>/tests/<sub>/test_foo.py`; for a package `foo/__init__.py`, `tests/test_foo.py` covers it (a package's inner modules `foo/bar.py` map to `tests/foo/test_bar.py`).
- Exceptions: `freedom_ls/<app>/tests/playwright/` is skipped by the checker (browser tests are not mirrored); non-conforming files are listed in `test_organisation/mirroring_baseline.txt` and `mirroring_exemptions.txt` (a changed-file map must also read those, since baselined tests do not sit at the mirrored path).
- Top-level `tests/` (e.g. `tests/test_conftest.py`, `tests/test_settings_dev.py`) tests `conftest.py` and `config/settings_dev.py`; `claude_plugins/fls-content` is also in `testpaths`.
- `find_apps`, `owning_app` and `iter_entries` in `generate_app_map.py` already give app directory discovery, so a selection script can import them (script is stdlib-only, run as a file from `claude_plugins/django-stack/scripts`).

App dependency map:
- `test_organisation/declared_edges.toml` currently declares one edge only: `base -> learner_management` (context processor). The bulk of edges comes from imports, enforced by `test_organisation/import_contracts.toml` (import-linter) with exceptions in `import_baseline.txt`. `docs/app_structure.md` (generated by `generate_app_map.py --check` in CI) holds the app graph. I did not parse them in detail for this note. A reverse-dependency expansion ("changed app + every app that imports it") therefore needs the generated app map as input. Foundational apps (`site_aware_models`, `accounts`, `base`, `content_base`) would pull in nearly everything, so selection for them degenerates to the full suite.

Sketch (a single script invocation):
1. `git diff --name-only $(git merge-base HEAD main)` plus `git ls-files -o --exclude-standard` for untracked.
2. For each path: owning app via `owning_app`; compute mirrored test path; if exists, add. Changed test files add themselves.
3. Add widening rules: for changes in an app's `models.py`/`migrations/`/`factories.py`/`conftest.py`/`fixtures` select the whole `<app>/tests/` plus the tests of dependent apps; for templates/static/JS select view tests of the owning app plus `tests/playwright` for that app; for `config/`, `pyproject.toml`, root `conftest.py`, `freedom_ls/conftest.py` fall back to the full suite.
4. Print a list of paths to pass to `uv run pytest <paths> --no-cov`.

Blind spots (inherent, independent of implementation):
- Templates (`*.html`, cotton components), static/JS/CSS: no Python import edge, so the mirror rule cannot see them; template rendering is exercised by view tests and Playwright of other apps (e.g. base templates used everywhere).
- Migrations: the DB schema is shared by everything; a migration affects every DB test through DB creation.
- Settings, `conftest.py`, shared fixtures, factories: shared state with no mirror counterpart; the declared runtime edge `base -> learner_management` shows edges exist that imports do not reveal (TEMPLATES context processors, signals, `INSTALLED_APPS` hooks, URL includes, content-type registry in `content_base`).
- Dynamic dispatch (registries, string dotted paths such as the factory dotted-string form) is invisible to a static import graph.
- Tests that live in baselined / exempted non-mirrored locations.
- Cross-app tests: the project rule puts a multi-app test in the lowest app depending on all it touches, so a change in a lower app may only be exercised by tests in a higher app: the reverse-dependency expansion is needed to find them.

## 4. `--lf`, `--ff`, `--sw`, `-x`, cache

From pytest's cache docs (https://docs.pytest.org/en/stable/how-to/cache.html):
- `--lf`/`--last-failed` re-runs only tests that failed last run (all if none failed; `--lfnf=none` changes that); `--ff` runs failures first then the rest; `--nf` new files first; `--sw`/`--stepwise` stops at first failure and continues from it next time; `-x` stops at first failure; `--sw-skip` skips one failing test.
- The cache lives in `.pytest_cache` under rootdir, so each worktree has its own; state is per checkout.
- With xdist, `--lf` works (last-failed is computed in the controller), `--sw` is not usable with `-n` (UNVERIFIED; stepwise relies on ordered, sequential execution).
- With pytest-randomly, order shuffles each run; `-p no:randomly` or `-p randomly_seed=<n>` (the `-p randomly_seed` form is not right; the actual option is `-p no:randomly` or `--randomly-seed=<n>`) fixes it. `--ff` and `--sw` interact with random order: failures-first reordering is applied by the cacheprovider; randomly also reorders. Order of the two reorderings is UNVERIFIED.
- Useful as a fix loop: after a failing full or targeted run, `--lf --no-cov` re-runs only the failures. It does not detect regressions in tests that passed before.

## 5. pytest-xdist with pytest-django

- Each xdist worker gets its own test database by default; the `django_db_modify_db_settings_xdist_suffix` fixture adds a worker suffix to the DB name. Sharing one DB is possible by overriding `django_db_modify_db_settings`. https://pytest-django.readthedocs.io/en/latest/database.html
- This project already has `-n auto` capped at 4 workers (root `conftest.py`) and the testing skill already recommends it. `config/settings_dev.py` includes the worker in `application_name`, so Postgres connections are identifiable (`pg_stat_activity`).
- Each worker creates its own DB on session start (migrations run per worker unless `--reuse-db` / `--no-migrations`), so the setup cost is paid up to 4 times in parallel (CPU and Postgres load), which reduces the speed-up. Exact speed-up for this suite is not measured here (no data). Typical claim: near-linear on CPU-bound suites with many equal-sized tests; DB-heavy suites are bounded by Postgres.
- pytest-cov works with xdist (it combines worker data), at the cost of coverage overhead per worker. https://pytest-cov.readthedocs.io/ ; known edge cases: `--dist` without `-n` misconfigures subprocess coverage (https://github.com/pytest-dev/pytest-cov/issues/667); dynamic contexts break with xdist (https://github.com/pytest-dev/pytest-cov/issues/604); one report of coverage with xdist taking about twice as long as without (https://gh.nn.ci/pytest-dev/pytest-cov/issues/669; reporter's setup unknown).
- xdist known limitations: test collection order and count must be identical across workers (unordered parametrize sources break); `-s` not supported; `--pdb` disabled. https://pytest-xdist.readthedocs.io/en/stable/known-limitations.html
- pytest-randomly with xdist: each worker is seeded identically from the controller's seed; failures reproduce with `-p randomly --randomly-seed=<seed>` (from pytest-randomly docs; not re-fetched here, UNVERIFIED).
- Playwright with xdist: pytest-playwright documents xdist support (each worker launches its own browser); `live_server` in pytest-django binds a free port per worker, so ports do not collide. Not verified against this repo's Playwright fixtures; conftest-level shared files (the `STORAGES`/media directory noted in `spec_dd/3. done/2026-08-21_20:12_basic_reports/2. plan.md` line ~392) are the known shared-state risk in this repo.
- Risks specific to this repo, from existing specs: tests must not depend on order; session-scoped mutable fixtures surface only under randomly/xdist (`spec_dd/1. next/test-organisation-and-hygene/research_test_organisation.md` line ~102); the dev Postgres is shared across worktrees (hence the 4-worker cap) so concurrent full runs in multiple worktrees multiply connections.
- Invocation: `uv run pytest -n auto` (4 workers here).

## 6. `--reuse-db` and `--no-migrations`

From https://pytest-django.readthedocs.io/en/latest/database.html:
- `--reuse-db` creates the test DB as usual but does not drop it afterwards; the next run reuses it. It "will not pick up schema changes between test runs".
- `--create-db` forces re-creation (use after altering schema, i.e. when a migration is added or edited, or after switching to a branch with different migrations).
- `--no-migrations` (`--nomigrations`) builds the schema from the current models instead of running migrations; `--migrations` re-enables them.
- Correctness trade-offs: `--no-migrations` skips data migrations and migration-state bugs (a broken migration will not be caught by tests), and RunPython/RunSQL-created data (e.g. seeded rows) will not exist; tests that depend on migration-seeded data fail or pass wrongly. `--reuse-db` risks stale schema after a migration lands; combined with a branch-named test DB (`test_<branch>`) it is per-branch, so schema drift only occurs within a branch when migrations change. Reused DBs also keep any data left by a `TransactionTestCase`/leaked committed rows (Playwright `live_server` tests commit) unless flushed.
- With xdist, `--reuse-db` keeps one DB per worker suffix.
- Whether this suite's migrations are slow was not measured. `--durations` plus the session start time ("setup" of the first test) would show it.

## 7. Dropping `--cov` for non-gate runs

- `--no-cov` disables pytest-cov for the invocation (pytest-cov docs, https://pytest-cov.readthedocs.io/en/latest/config.html: "--no-cov: disable coverage report completely (useful for debuggers)"). The repo's CI Playwright job and prior SDD plans already use `uv run pytest -m playwright --no-cov`, so the flag works with this `addopts`. Without it, `--cov-fail-under=73` would also fail a small targeted run (a subset can never reach the project-wide percentage), so a targeted run needs `--no-cov` regardless of time.
- Overhead: not measured on this suite. Reported figures vary widely: pytest-cov issue 669 reports roughly 1h15 vs under 35 min (xdist both sides) https://gh.nn.ci/pytest-dev/pytest-cov/issues/669 (a single user report; their stack is unknown). Branch coverage (`--cov-branch`) costs more than line coverage. Coverage.py on Python 3.12+ can use `sys.monitoring` (`COVERAGE_CORE=sysmon`) which is lower overhead for line coverage; branch support under sysmon was added only in later versions (check coverage.py docs; UNVERIFIED for the installed version): https://coverage.readthedocs.io/en/latest/changes.html
- A concrete measurement would be `time uv run pytest -n auto` vs `time uv run pytest -n auto --no-cov` once.
- The threshold lives in `addopts`, so the single full gate keeps it automatically, with no config change; targeted runs add `--no-cov`.

## 8. Marker tiers and playwright

- `addopts` already excludes `ci_only` and `weasyprint`. `playwright` is not excluded by default, so the plain `uv run pytest` runs browser tests too (browsers must be installed locally). CI runs the two groups as separate jobs: unit (`-m "not playwright"`, with cov, 10 min timeout) and playwright (`-m playwright --no-cov`, 15 min timeout).
- Option for selection: `-m "not playwright"` for most checks; `-m playwright` (or the `tests/playwright/` folder of the changed app) when templates/JS/views/CSS changed or at the gate. Note: passing `-m` on the command line replaces the `-m` in `addopts` (the last `-m` wins in argparse), so `ci_only` and `weasyprint` exclusions get dropped unless repeated: `-m "not playwright and not ci_only and not weasyprint"`. CI's current commands have this property already (`-m "not playwright"` alone would then include `ci_only` and `weasyprint` tests; that is how CI behaves today as written; UNVERIFIED whether pytest merges them: pytest's `-m` is a single-valued option, last wins).
- Cost of Playwright tests is not measured; browser tests are typically the slowest per test. Use `--durations=25` to quantify.
- Playwright traces and screenshots (`--tracing=retain-on-failure --screenshot=only-on-failure`) are in `addopts`, so they cost only when browser tests run.

## 9. `--durations` and Django slow-test patterns

- `--durations=N` prints the N slowest test phases (setup/call/teardown) at the end; `--durations-min=S` sets a threshold. https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration . Under xdist the report aggregates across workers.
- Django-specific patterns that make suites slow (Django docs https://docs.djangoproject.com/en/stable/topics/testing/overview/ and https://docs.djangoproject.com/en/stable/topics/testing/advanced/):
  - DB creation runs all migrations at session start (per xdist worker); mitigated by `--reuse-db` / `--no-migrations` / squashed migrations.
  - `TransactionTestCase` / `@pytest.mark.django_db(transaction=True)` flush tables after each test instead of a rollback, which is much slower; `serialized_rollback=True` additionally serializes and restores the DB contents.
  - `live_server` / Playwright tests need transactional DB behaviour (the server thread commits), so they are in the slow class.
  - Password hashing: Django's default hasher is slow; the usual fix is a fast hasher in test settings (`PASSWORD_HASHERS`). Whether `config/settings_dev.py` does so was not checked.
  - Factories that create deep object graphs per test, and function-scoped fixtures that rebuild large data (the project's own testing.md says fixtures are function-scoped unless profiling justifies wider).
- `-p no:randomly` is not a speed matter. pytest-timeout (300 s) bounds a hung test.

## 10. Comparison

| Technique | What it saves | What it can miss | Fits an LLM-driven workflow? | Recommended role |
|---|---|---|---|---|
| pytest-testmon (`--testmon --no-cov`) | Skips tests whose traced Python dependencies are unchanged; precise at function level | Templates/static/fixtures (untracked), coverage forces no-collect so `--cov` cannot be on, per-worktree cold first run, xdist/randomly/pytest-django interplay unconfirmed, a `.testmondata` file to manage | Medium: single flag, but state file and opaque selection; needs a trial on this suite | Targeted run candidate after a trial; never as the gate |
| pytest-picked (`--picked --mode=branch`) | Re-runs tests in changed/new test files only | Any changed source whose tests were not edited; no dependency awareness | Yes (one flag) | Targeted run for "my new/edited tests" only |
| Mirror-map script (changed file -> mirrored test + dependent apps) | Large cut on typical single-app changes; uses existing mirroring and app-graph tooling; deterministic and explainable | Templates, static, migrations, settings, conftest, factories, registries, runtime edges; needs fallback-to-full rules; foundational-app changes select nearly everything | Yes (one script invocation printing paths) | Targeted run (primary), with fallback to full on risky paths |
| `--lf` / `--ff` / `--sw` / `-x` | Fast fix loop: rerun only failures, stop early | Does not check anything that previously passed; `--sw` unusable with `-n` (unverified) | Yes | Targeted run for fix loops only; never as the gate |
| pytest-xdist `-n auto` (cap 4) | Wall-clock on the full run (not measured here); already supported and documented in the testing skill | Order/shared-state bugs, shared dev Postgres load, per-worker DB creation cost | Yes (already in the skill) | Full gate (and large targeted runs) |
| `--reuse-db` | Skips DB create/migrate on repeated runs (per-branch test DB) | Stale schema after migrations unless `--create-db`; leaked committed data | Yes with a rule: add `--create-db` when migrations changed | Targeted run only; full gate should create the DB fresh |
| `--no-migrations` | Skips migration execution | Broken migrations and migration-seeded data | Yes | Targeted run only, never the gate |
| Dropping cov (`--no-cov`) | Coverage tracing overhead (size on this suite unmeasured); required anyway for subsets because of `--cov-fail-under=73` | Nothing about test results; only loses the coverage number | Yes (one flag) | Targeted run: always; full gate: keep cov |
| Marker tiers (`-m "not playwright"` / `-m playwright`) | Skips the browser tests when no template/JS/view change | Browser-only regressions when templates/static change in a way the rule misses; `-m` replaces the `addopts` `-m` | Yes | Targeted run (exclude by default, include on UI-touching changes); gate runs both |
| `--durations=N` | Finds slow tests and setup cost (diagnosis, not a speed-up itself) | n/a | Yes | One-off profiling run |

Sources:
- https://testmon.org/ ; https://testmon.org/blog/ ; https://github.com/tarpas/pytest-testmon ; https://pypi.org/project/pytest-testmon/
- https://github.com/anapaulagomes/pytest-picked
- https://pytest-django.readthedocs.io/en/latest/database.html
- https://pytest-xdist.readthedocs.io/en/stable/known-limitations.html
- https://github.com/pytest-dev/pytest-cov/issues/667 ; https://redirect.github.com/pytest-dev/pytest-cov/issues/604 ; https://gh.nn.ci/pytest-dev/pytest-cov/issues/669
- https://docs.pytest.org/en/stable/how-to/cache.html ; https://docs.pytest.org/en/stable/how-to/usage.html
- https://pytest-cov.readthedocs.io/en/latest/config.html ; https://coverage.readthedocs.io/en/latest/changes.html
- https://docs.djangoproject.com/en/stable/topics/testing/overview/

Notes on provenance: the pytest cache docs, pytest-cov config docs, coverage changelog, Django docs and `-m` last-wins behaviour are cited from general knowledge, not fetched in this session; treat as UNVERIFIED until checked. Everything under "project has" was read from the repo.

status: ok
