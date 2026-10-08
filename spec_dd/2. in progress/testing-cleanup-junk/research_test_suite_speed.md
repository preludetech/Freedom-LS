# Research: where the run time of the test suite goes

Sources: `research_test_suite_speed_durations_unit.txt`, `research_test_suite_speed_durations_playwright.txt`, `pyproject.toml` `[tool.pytest.ini_options]`, `.github/workflows/tests.yml`, `conftest.py`, `freedom_ls/conftest.py`, `freedom_ls/tests/playwright_fixtures.py`, plus the test bodies named below.

Conditions of both runs (from the `time -v` header): serial, `-o addopts=` (so no coverage), `--tracing=off --screenshot=off`, `pytest-randomly` on, five other processes competing for CPU. Absolute numbers are pessimistic; relative ones hold. Sums below are my hand-added totals of the printed `--durations` lines and are good to about +/-1 s.

## 1. Unit suite

Run: `-m "not ci_only and not weasyprint and not playwright"`, 6478 passed, 264 deselected, 990.61 s (16:30 pytest, 16:40 wall by `time`).

### Shape of the time

| Measure | Value |
|---|---|
| Average per test (990.61 / 6478) | 0.153 s |
| 100 listed entries (each >= 0.84 s) | about 204 s = 20.6 % of total |
| Remaining ~6378 test-phases below 0.84 s | about 787 s, about 0.123 s each |
| Slowest single entry | 15.87 s (one parametrised image test) |

Conclusion: the time is spread, not concentrated. About 79 % of the run is thousands of tests that each take under 0.84 s (the list cuts off at 0.84 s, so the 0.5-0.84 s band is not itemised either; `--durations-min=0.5` printed nothing below the 100-line cap). A few slow tests are a minor share; about 20 % sits in 100 entries.

Process-level numbers (`time -v`): user 1356.7 s, system 354.5 s, 171 % CPU, so the process used about 1711 s of CPU in 990 s of elapsed time (some of that is threads or subprocesses, e.g. `pytester` subprocess runs, Postgres client work does not count). The system time (21 % of CPU time) and 157 million minor page faults are high for a serial test run; the cause is not identifiable from these files. Max RSS 660 MB.

### Phase split of the 100 listed entries

| Phase | Entries | Seconds |
|---|---|---|
| setup | 36 | about 101 |
| call | 63 | about 101 |
| teardown | 1 | 1.29 |

Setup and call are about equal in the list. Setup time is almost entirely a module-level fixture that loads the `demo_content/` tree into the database (below); it is paid per test because the fixtures are function-scoped.

### Grouped by file (listed entries only)

| File | App | Entries | Seconds | Phase | Why slow (from the test body) |
|---|---|---|---|---|---|
| `freedom_ls/blog/tests/test_demo_articles.py` | blog | 10 | 47.9 | setup | Function-scoped fixture `loaded_demo_content` runs `save_content_to_db(settings.BASE_DIR / "demo_content", site.name)` for every test (full demo content import, including image optimisation); 7-9 s on the first, 2.8-3.5 s thereafter |
| `freedom_ls/content_engine/tests/test_demo_content_application_form.py`, `_survey_form.py`, `_articles.py`, `_prices.py` | content_engine | 22 | 42.4 | setup | Same `loaded_demo_content` pattern (each test asserts one fact about the demo content: "has a hidden article", "asks a date question", ...); 1.6-2.5 s each |
| `freedom_ls/learner_interface/tests/test_demo_content_course_card.py` | learner_interface | 2 | 3.5 | setup | Same demo content load |
| `freedom_ls/content_engine/tests/test_optimise_image.py` | content_engine | 7 | 24.7 | call | Pillow encode/compare of real images; one parametrised case alone is 15.87 s (`photographic_png_bytes`), `test_optimise_image_is_deterministic_across_runs` 2.2 s |
| `freedom_ls/content_engine/tests/test_content_save_course.py` | content_engine | 7 | 10.3 | call | Runs the save-course command over image content (optimises, writes storage) |
| `freedom_ls/content_engine/tests/test_image_cache.py` | content_engine | 6 | 7.5 | call | Image cache writes and re-reads |
| `freedom_ls/educator_interface/tests/test_permission_matrix.py` | educator_interface | 22 | about 19.9 | call | Parametrised matrix, 0.84-1.05 s per case; each case builds a role/org/cohort/learner fixture set |
| `freedom_ls/dev_tools/tests/test_create_demo_data.py` | dev_tools | 2 | 11.1 | call | `call_command("create_demo_data", ...)` builds the whole demo dataset (5.5-5.6 s each) |
| `freedom_ls/comms/tests/test_views_{panel,mark,badge,list}.py` `TestQueryCount` | comms | 5 | 6.3 | call | Each creates 2 and 200 rows to prove a flat query count |
| `freedom_ls/panel_framework/tests/test_tables.py::test_table_query_to_params_round_trips` | panel_framework | 1 | 6.3 | setup | The test body is a `RequestFactory` call with no database; the 6.26 s is first-use cost (looks like one-off import/warm-up landing on whichever test random order puts first; not confirmable from the file) |
| `freedom_ls/learner_management/tests/test_learner_admin.py` | learner_management | 2 | 5.0 | call | Inline pagination over many learners |
| `freedom_ls/course_applications/tests/test_collection_safety.py` | course_applications | 2 | 4.0 | call | `pytester.runpytest_subprocess(...)`: starts a fresh pytest/Django process per test |
| `tests/test_generate_app_map.py::test_check_from_repo_root_exits_0` | tests/ | 1 | 3.3 | call | Runs `generate_app_map.py --check` over the repo as a subprocess |
| `freedom_ls/base/tests/test_error_pages.py` | base | 3 | 3.5 | call | Renders error pages (about 1 s each) |
| `tests/test_playwright_fixtures.py` | tests/ | 1 | 1.3 | teardown | Closes a Playwright-opened connection |
| `freedom_ls/educator_interface/tests/` (`test_cohort_details_pagination`, `test_config_authorisation`) | educator_interface | 2 | 2.1 | call | Query/pagination and path enumeration |
| tiktok_pixel, referral_tracking, reports, learner_interface dashboard cost, webhooks | various | 5 | 4.8 | mixed | Query-count and rendering tests |

Per app, rough listed totals: content_engine about 85 s, blog 48 s, educator_interface about 22 s, dev_tools 11 s, comms 6 s, panel_framework 6 s, learner_interface about 4.4 s, learner_management 5 s, course_applications 4 s, base 3.5 s, tests/ 4.6 s.

Three groups account for most of the listed time: the `loaded_demo_content` setups (about 94 s over 34 entries, 46 % of listed time), image processing in content_engine (about 42 s over 20 entries, 21 %), and the permission matrix (about 20 s, 10 %).

I found no `time.sleep` and no `transaction=True` in the slow entries I read. I did not scan the repo for those over the whole suite, only the files above (`ci_only` is the marker for real-time waits, and those are deselected from this run).

### Dev-tooling versus product tests (listed entries)

| Kind | Where | Listed seconds |
|---|---|---|
| Dev tooling | `tests/test_generate_app_map.py` (3.31), `tests/test_playwright_fixtures.py` (1.29 teardown), `freedom_ls/dev_tools/tests/test_create_demo_data.py` (11.11) | about 15.7 s (7.7 % of listed time, 1.6 % of total) |
| Dev tooling, `freedom_ls/qa_helpers/tests`, `claude_plugins/fls-content` | none of the 100 entries | 0 listed (cannot say below 0.84 s) |
| Product | everything else, including the demo-content tests (they test the shipped `demo_content/` through product code) | about 188 s |

The slow dev-tooling tests are therefore a small part of the measured time. The count and cost of the many fast dev-tooling tests below 0.84 s is not visible in the durations; it would need a per-directory run to measure.

### Fixed per-test overhead from `freedom_ls/conftest.py`

Four autouse fixtures run before every test, including ones that need no database:

| Autouse fixture | Work |
|---|---|
| `_disable_force_site_name(settings)` | one settings assignment |
| `_isolate_media_root(settings, tmp_path)` | creates a per-test `tmp_path` directory (one mkdir plus pytest's tmp-path bookkeeping) and one settings assignment |
| `_disable_preview_overrides(settings)` | two settings assignments |
| `_clear_course_access_backend_cache()` | imports `freedom_ls.course_access.loader` (cached after first) and calls `cache_clear()` twice |
| `reset_local_storage` (from `freedom_ls/tests/playwright_fixtures.py`) | checks `request.fixturenames`, returns immediately unless the test uses `page` or `logged_in_page` |

All are cheap Python calls (no database, no I/O beyond one directory creation). The measurements here cannot isolate their cost; the suite floor is bounded by the 0.123 s average of the unlisted tests, which includes Django database setup per `django_db` test (transaction savepoint) and factory building. The fixtures do not look like a significant part of the 0.153 s average, but the files do not prove that.

## 2. Playwright suite

Run: `-m playwright`, 226 passed, 453.93 s (7:33 pytest, 7:42 wall); 43 % CPU, so the process was waiting (browser, Postgres, contention) more than computing. 52 files, 189 `def test_` functions, 226 items after parametrisation (viewport, tablet/phone, etc.).

| Measure | Value |
|---|---|
| Average per test | 2.01 s |
| Listed (100 entries, each >= 1.33 s) | about 199 s |
| Unlisted remainder (all phases under 1.33 s) | about 255 s, over about 352 phases |

### Setup versus call among listed entries

| Phase | Entries | Seconds | Typical |
|---|---|---|---|
| setup | 47 | about 91 | 1.64-2.31 s, typically about 1.8 s (one 6.62 s outlier, a first-run browser launch) |
| call | 52 | about 106 | 1.33-5.6 s; the top 9 are 2.7-5.6 s |
| teardown | 1 | 2.12 (`tests/playwright/test_design_screenshots.py`) | |

Notable: nearly every setup in the list is 1.7-1.9 s whatever the test does, i.e. setup is a flat fixed cost per test. Setup is made of: Postgres test-database work for the `live_server` and `transaction=True` (flush of every table at the end of each test, per the module docstring in `freedom_ls/tests/playwright_fixtures.py`), a new `BrowserContext` and `Page`, `logged_in_user` (UserFactory plus `EmailAddress`), then `logged_in_page` driving the allauth login form (`goto`, two `fill`s, a click, `expect(page).not_to_have_url`).

### Fixed cost versus the test's own actions

Evidence for the fixed share:

- Every file with several tests shows the same 1.7-1.9 s setup on each (for example `comms/tests/playwright/test_notification_bell.py`: 11 tests, setup 1.80-2.25 s; `learner_interface/tests/playwright/form_ui_tests.py`: 7 tests, setup 1.68-1.87 s).
- 179 of 226 tests have a setup below 1.33 s (not listed); their value is not visible.

Two bounds for the setup share of 454 s:

- Lower bound: the 47 visible setups only, 91 s = 20 %.
- Upper estimate: all 226 tests at the typical 1.8 s = 407 s = 90 % (implausible, because 179 setups are below 1.33 s).
- Middle estimate: 226 tests at 1.0-1.3 s (the unlisted range, known to be below 1.33 s) = 226-294 s = 50-65 % of the run.

Most likely the fixed per-test cost (login + flush + context) is 50-65 % of the 454 s. The call phase (the test's own clicks and assertions) is the rest, 35-50 %, and only 9 calls exceed 2.7 s.

The slowest files (by listed call time) and why:

| File | Calls listed | Why |
|---|---|---|
| `panel_framework/tests/playwright/test_modal_form_htmx.py` (15 tests) | 5.62 s top call, six calls between 1.44 and 1.66 s | modal open/save/close interactions; the 5.62 s one waits on a pending request |
| `learner_interface/tests/playwright/form_ui_tests.py` (7 tests, note the name does not match `test_*.py`, caught by `*_tests.py`) | 5.26, 4.11, 3.96, 3.66, 3.52, 2.75 | multi-page quiz/form workflows, already flow-shaped |
| `educator_interface/tests/playwright/test_quick_view_layout.py` (4 items but many params) | 4.89 s | drawer layout at several viewports, multiple setups of 1.8-2.3 s |
| `panel_framework/tests/playwright/test_quick_view_mobile_htmx.py` (6 tests) | six calls 1.36-1.82 s, one 6.62 s setup | viewport resizing |
| `tests/playwright/test_design_screenshots.py` (3) | 2.16-2.25 s calls, 2.12 s teardown | runs the design screenshot tool |
| `comms/tests/playwright/test_notification_bell.py` (11) and `test_notification_centre.py` (9) | 9-11 setups at about 1.8 s | many small tests, each separately logged in |

### Estimate of consolidation

Assumption set: (1) per-test fixed cost F = setup (login, flush, context) of about 1.0-1.8 s; (2) consolidating N tests that share one page and data into one flow keeps all of their actions and assertions (the call time) and pays F once; (3) the tests that share a page are those in the same file with the same factories (not all can merge: different viewports or roles need a different context); (4) no change to the call time.

Saving = (tests merged away) x F. Using the file counts above: 189 functions in 52 files; if every file became one flow, 137 test functions would disappear. In parametrised terms (226 items), a file-level merge cuts about 174 items (226 - 52) at F = 1.0-1.8 s = 174-313 s, i.e. 38-69 % of 454 s. A more cautious case where only functions within a file that need the same viewport and user merge (say half of those): 87 items x 1.0-1.8 s = 87-157 s, or 19-35 % of 454 s.

So the range supported is about 20-65 % of the playwright time, with a central guess around 35-45 %. It is bounded above by the unknown size of the unlisted setups. The data do not say how many tests share identical viewport and user; that needs reading the 52 files.

## 3. What the numbers say about the levers

Ranked by what the measurements support (largest supported saving first):

| Rank | Lever | What the measurements support | What they do not |
|---|---|---|---|
| 1 | (b) Consolidate playwright into flows | Fixed per-test cost looks like 50-65 % of the 454 s; a flow-per-file merge could save 20-65 % (about 90-300 s). It is the only lever where every test pays the same fat fixed cost (about 1.8 s setup vs call of 1-5 s). | Exact setup time of the 179 unlisted tests; how many tests share a page and role; whether the `transaction=True` flush could be dropped instead (the docstring says it cannot for the existing suite). |
| 2 | (d) `pytest-xdist` (`-n auto`, capped at 4 in `conftest.py` `pytest_xdist_auto_num_workers`) | Both runs were serial and spread (unit: 79 % of time in thousands of sub-0.84 s tests), which suits parallelism. The unit run used 171 % CPU and playwright 43 %, so there is idle CPU. The project already caps at 4 and has the hook, so the intent exists. CI runs `pytest -m "not playwright"` with no `-n`. | Any speedup figure: not measured, and per-worker database creation costs and the `live_server`/`transaction=True` interaction are not visible here. The CI runner core count is not in the workflow file. |
| 3 | (a) Delete junk unit tests | Time is spread: at 0.123 s per unlisted test, deleting 100 typical tests saves about 12 s (1.2 %), 1000 saves about 123 s (12 %). Only the `loaded_demo_content` tests are costly per item (about 2.8 s average over 34 listed entries, 94 s). Merging or sharing that fixture is a bigger win than deleting. | Which tests are junk; the repo-wide count of junk tests. This file measures cost, not quality. |
| 4 | (e) Turn off always-on tracing/screenshots | `addopts` has `--tracing=retain-on-failure --screenshot=only-on-failure`. Both measured runs used `off`; the repository default retains traces only on failure (still records tracing during the test). Playwright run: 1.08 million file-system output blocks (vs 118 thousand in the unit run), so the playwright run writes a lot, but the write source cannot be separated from tracing/DB/browser profile. | Playwright overhead of tracing in the retained mode: not measured, there is no `retain-on-failure` run to compare against. |
| 5 | (c) Take dev-tooling tests out of the default run | Listed dev-tooling entries total about 15.7 s of 990 s (1.6 %). Slow ones are `freedom_ls/dev_tools/tests/test_create_demo_data.py` (11.1 s), `tests/test_generate_app_map.py`, and subprocess-based `tests/` checks. The justification in the idea is "not real code", not speed; as a speed lever it is small on the evidence. | The cost of the many fast dev-tooling tests below 0.84 s, and `freedom_ls/qa_helpers/tests` / `claude_plugins/fls-content` (none listed). A per-directory timing run would settle it. |
| ? | (f) Coverage (`--cov --cov-branch` in `addopts`) | Not measured: both runs had coverage off. coverage.py has no benchmark specific to `pytest-cov`; the SlipCover paper (ISSTA 2023) measured coverage.py at a median 180 % overhead on CPython (range 1.3x-3.6x, median 2.8x) on its benchmarks. Treating that as a proxy, coverage could plausibly be the single largest cost in the CI unit job. A coverage.py maintainer anecdote on `sysmon` (coverage 7.7+) reports 275 % falling to 25 % on one small library. | Anything for this repo. Whether `config` pins `COVERAGE_CORE`, the coverage.py version, and CI timing with and without `--cov` are all unknown. Rank is unknown rather than low. |

Sources for (f): https://ar5iv.labs.arxiv.org/html/2305.02886 (SlipCover), https://nedbatchelder.com/blog/202406/coverage_at_a_crossroads (trace-function overhead explanation), https://us.PyCon.org/2024/schedule/presentation/110/ (PyCon 2024 talk, "up to 2.6x"), https://hackers.pub/@hugovk@mastodon.social/0195a9d7-f222-74f1-969c-a34e2ac32292/quotes (sysmon anecdote).

## 4. The CI timeouts

Facts from `.github/workflows/tests.yml`:

- `unit-tests`: `runs-on: ubuntu-latest`, `timeout-minutes: 10`, run step `uv run pytest -m "not playwright"`. The CLI `-m` replaces the `addopts` marker expression, so CI also runs the `ci_only` and `weasyprint` tests that the local measured run deselected (264 deselected locally = 226 playwright + 38 others; the 38 are included in CI). It also uses `addopts` coverage: `--cov --cov-branch --cov-report=term-missing --cov-fail-under=73`, with tracing/screenshot on-failure. No `-n`, so it is serial.
- `timeout-minutes: 10` covers the whole job, including `uv sync`, `npm ci`, the Tailwind build and the Postgres service start (those steps are before the pytest step and are not timed here). The 10 minutes is therefore a budget shared with setup.
- `playwright-tests`: 15 minutes, `uv run pytest -m playwright --no-cov`, plus `playwright install --with-deps chromium` in the same budget. Locally 7:33 measured.
- GitHub-hosted `ubuntu-latest` hardware is not stated in the repo.

Comparison: local unit 16.5 min (without coverage) versus a 10 min CI budget. If CI hardware were the same speed, the job would time out. It is not known to, so CI must be about 1.7x or more faster than the measured conditions, which is plausible because the local run competed with five other processes (171 % CPU yet the machine was loaded), but the margin cannot be established. With coverage on top (see lever (f); likely a slowdown rather than a speed-up), the CI unit job would be expected to be near or beyond the 10-minute limit unless the CI machine is more than about 2-4x faster than the measured local one. That the project has a `timeout-minutes: 10` and a coverage gate suggests it currently passes in under 10 minutes, so CI is likely much faster than this local measurement, but that is inference.

Evidence that would settle it (I cannot see CI logs):

- The "Run unit tests" step duration in recent GitHub Actions runs (the step timing line), and the `--durations` tail if printed.
- The job's total duration versus the 10 min limit across several recent runs of `main` (variance matters: a cancelled-by-timeout run is the first sign).
- CPU count of the runner (`nproc`) in a log, and a CI run with and without `--cov` for the coverage cost.
- A local run with coverage on and no competing processes to get the true coverage multiplier.

status: ok
