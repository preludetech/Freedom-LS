# Test suite cleanup

## What we are doing

Cut the test suite down to tests that guard product behaviour, put each test where the documented
structure says it goes, turn the Playwright tests into a small number of flow tests, take tests of
developer tooling out of the default run, and fix the skills, agents and commands that produced the
junk so it does not grow back.

## Why

The suite has 504 test files and about 6,700 tests. Run serially on a developer machine, with
coverage off, it takes 16.5 minutes for the unit tests and another 7.5 minutes for the 226
Playwright tests. CI gives the unit job 10 minutes, and that job runs with coverage on. Every
`uv run pytest` during `/sdd:implement_plan`, every `qa-bugfixer` run and every pre-PR check pays
that, and locally every run also pays for coverage, which typically doubles or triples it.

The size is not mostly dead weight. `research_junk_and_brittle_tests.md` found no `xfail`, no
unconditional skips and no "flaky" comments. The waste is concentrated in a few families, and the
structure is what has drifted. About 292 of the 504 files do not mirror a source module and are
carried as debt in `test_organisation/mirroring_baseline.txt`, while the exemptions file the testing
skill says to use for cross-cutting tests is empty. Every Playwright test logs in through the UI,
builds its own data and flushes the whole database afterwards, so 226 tests means 226 logins and
226 flushes. Tests of QA seeders and git scripts run alongside product tests and nothing in the
configuration says they are a different kind of test.

The time is spread, not concentrated. `research_test_suite_speed.md` shows the unit suite averages
0.15 seconds a test and the hundred slowest entries are a fifth of the run, so deleting a thousand
junk tests saves about a tenth of it. Deleting is for signal, not speed. The unit suite's time goes
to a function-scoped demo-content fixture that re-imports the whole `demo_content/` tree for each
of 34 tests, to coverage, and to running serially. The Playwright suite's time is the fixed
per-test cost of login and flush, half to two thirds of its run.

## What is settled

### Which tests go

`research_junk_and_brittle_tests.md` holds the rubric, R1 to R13, and the keep floor, K1 to K4,
grounded in the project's own testing skills. The families it found, with grep counts and example
paths, are the targets:

- Asserts on Tailwind or CSS utility classes, where the class is not the contract. An `aria-*`,
  `role`, `href`, `hx-*` or `data-*` attribute is a contract; `bg-primary/5` is not.
- Tests that read a shipped CSS or JS file and assert that a string is in it, such as
  `base/tests/test_theme_tokens.py`. The computed WCAG contrast test in that file stays.
- Asserts on long user-facing copy where the copy is not the feature. Error pages, legal text and
  email subjects are the feature; a button label on a course application page is not.
- Per-instance copy-paste of one generic check: the three tracking-pixel apps, the per-name icon
  tests, the mirrored deadline `__str__` pairs. One shared or parametrised test replaces each family.
- Render-only admin tests such as `test_it_renders_with_rows_present`. Admin permission, validation
  and read-only tests are the keep floor and stay.
- Config echoes, except the three AXES setting asserts in `accounts/tests/test_utils.py`, which are
  the only guard on a security setting and stay until a system check replaces them.
- Exact query-count asserts reviewed case by case; an N+1 guard asserts an upper bound.
- Repo-lint tests stay: `icons/tests/test_no_font_awesome.py`, the `safe` filter and raw-colour
  checks in `panel_framework/tests/test_templates.py`, and `tests/test_security_patterns.py`. They
  are product guards, and converting them to lint rules is not part of this work.

Anything that meets the keep floor stays: site and organisation isolation, role and permission
denial, scoring and progress, signals and webhooks, deadlines, destructive management commands,
regressions with a stated reason. A test that is the only guard on a security property is not
removed on rubric grounds.

### Where tests live

The cleanup merges tests into the module that mirrors their source module and moves tests that
exercise another app's behaviour into that app. The matching lines come out of
`mirroring_baseline.txt` and `import_baseline.txt` in the same change, because both are delete-only
and a stale line fails the CI lint job. Cross-cutting tests that cannot mirror a module are grouped
into a subpackage and declared in `mirroring_exemptions.txt`, which is what the testing skill
already says and nobody has done. The subpackages are `demo_content/` for tests that read the
shipped demo tree, `components/` for tests of Cotton components, which have no Python module, and
`invariants/` for repo-lint and cross-app invariant tests. `learner_interface` also gets a
`tests/views/` subpackage with one file per page, because its single `views.py` would otherwise
draw several thousand lines of tests into one file. The helper functions that the per-app
`conftest.py` files in `learner_interface`, `reports`, `course_applications`, `deployment` and
`panel_framework` expose for hand-import move to a plain `helpers.py` beside the tests, and
`panel_framework`'s stub models to `stub_models.py`. The shared builders live in the lowest app
that owns what they build: `collection_item_for` in `content_engine/tests/helpers.py`,
`register_user_for_course` in `learner_management/tests/helpers.py` and `course_progress_record`
in `learner_progress/tests/helpers.py`. The duplicated builders, `collection_item_for` in two apps
and the three course-progress-record builders, collapse to one each.
`research_test_suite_inventory.md` lists the files, the per-app baseline counts and the
test-to-source ratios.

### Playwright flow tests

A flow test is one Playwright test that walks a user journey through a page or a few pages, logs in
once, builds its data once, and asserts many things along the way. Each flow is one file named
`test_<journey>_flow.py` in the app's `tests/playwright/`. The three QA viewports and the overflow
assertion the layout checks share live in `freedom_ls/tests/playwright_helpers.py` as
`QA_VIEWPORTS` and `assert_no_horizontal_overflow`. The current suite is the
opposite: 189 test functions in 52 files, most asserting one value each after a full login and
flush. `research_playwright_consolidation.md` groups them into about ten candidate flows and names
which tests each replaces: the panel_framework create-modal lifecycle, the data table, quick views,
educator cohort management, a learner completing a form, course browsing, notifications, and a
per-page mobile-layout sweep at the three QA viewports.

What is settled about the shape:

- Login stays per test and through the UI. The fixtures in `freedom_ls/tests/playwright_fixtures.py`
  explain why a session-scoped `storage_state` cannot survive the per-test flush, so the only way to
  amortise login is fewer tests. The base `ds:playwright-tests` skill says the opposite and is wrong
  for this repo.
- Layout checks, roughly 55 of the current tests asserting overflow, bounding boxes or corner
  radius, fold into the flow for their page, with the three viewports looped inside one test rather
  than parametrised into three logins.
- Assertions a `django.test.Client` response can make move to ordinary tests: server-rendered text,
  aria attributes, pagination links, the content of a notification panel for a given user. The
  browser is for Alpine and HTMX swaps, focus and `<dialog>` behaviour, history, `beforeunload`,
  clipboard, JS-off and geometry.
- Tests that need their own browser context, with JS disabled or clipboard permissions, stay
  separate.
- The trade-off is accepted: a flow stops at its first failing step and hides later ones until it is
  fixed. Tracing on failure is already on and localises the step.
- The Playwright CI job also runs with `pytest-xdist`. The root `conftest.py` caps `-n auto` at four
  workers, so flow granularity should leave several flows per worker.

### Developer-tooling tests leave the default run

Tests of the QA seeders in `freedom_ls/qa_helpers/tests/`, the `danger_` commands in
`freedom_ls/dev_tools/tests/`, the git and database scripts under the top-level `tests/` directory,
the design-screenshot tool, and the fls-content validator in
`claude_plugins/fls-content/validate/tests/` get a `dev_tooling` marker in the style of `ci_only`,
are deselected in `addopts`, and run in their own CI step. They are not deleted. `test_guard.py` is the only thing
that stops a `danger_` command wiping a production database, and the tests of `dev_db_delete.sh`,
`land_on_main.sh` and the rebase lost-change check guard scripts that drop databases and move
`main`. The seed-shape tests that only prove a QA fixture builder produced consistent data are junk
under the rubric and go. `research_qa_helpers_and_tooling_tests.md` classifies every file.

Two files in `tests/` are product guards, not tooling, and stay in the default run:
`test_security_patterns.py`, which enforces the ORM-only rule, and `test_entrypoints.py`, which
imports the WSGI and ASGI entrypoints.

Three consequences follow:

- CI's `-m "not playwright"` overrides the `addopts` marker expression, so the CI command changes
  too.
- The downstream filter string `-m "not playwright and not fls_internal and not ci_only and not
  weasyprint"` is repeated in at least six skill and command files and gains the new marker.
- `dev_tools` is not omitted from coverage today, so its tests leaving the default run moves the
  number.

### Coverage

Coverage leaves the default local run. The unit CI job passes it explicitly and enforces the gate;
anyone can opt in locally with `--cov`.

The gate drops to whatever the cleaned suite measures. Coverage earned by markup asserts and
render-only admin tests was never protection. The number comes from the unit job alone, because the
Playwright job runs with `--no-cov`, so moving Playwright assertions into client tests raises it and
deleting admin and Cotton component tests lowers it.

### Slow setup in the unit suite

The `loaded_demo_content` fixture in `content_engine/tests/conftest.py` imports the demo content
tree per test. The demo-content tests in `blog`, `content_engine` and `learner_interface` each
assert one fact about that import, and together they are about half of the slow time in the unit
suite. They become one import per module with the facts asserted against it: `loaded_demo_content`
becomes a module-scoped fixture in `freedom_ls/tests/demo_content_fixtures.py`, and the ambient-site
patching that `mock_site_context` does becomes a reusable `site_context` context manager in
`freedom_ls/tests/site_context.py`. The image-processing
tests in `content_engine` are the next largest block and are real work; they stay.

### Skills, agents and commands

`research_testing_skills_audit.md` audits every testing skill, resource, agent and command with
quoted lines. The fixes are settled:

- `ds:playwright-tests` and its resource: drop the session `storage_state` advice and the
  `tests/playwright/` location, remove the "planned for phase 2" tracing note and the "(currently
  available)" markers, fix the login example's URL names, and replace the CSS-class locator examples
  that contradict the skill's own locator priority.
- `ds:testing` and its resource: remove "Cover these for each feature", the blanket branch-coverage
  rule, the docstring-on-every-test rule and the `required_field=None` IntegrityError example, which
  push toward tests the rubric deletes. Scope "one behaviour per test, no multi-act tests" to
  non-browser tests. Add the rubric as a short "do not write" block. Stop the 258-line skill
  duplicating its 652-line resource.
- `fls-dev:testing`: remove the "later spec" comment and the changelog of named tests, which go stale
  the moment the cleanup renames them. State the developer-tooling marker and that `tests/` and
  `claude_plugins/fls-content` are in `testpaths`. Say the marker taxonomy once instead of four
  times.
- `fls-dev:playwright-tests` becomes the real FLS Playwright skill. It documents the fixtures
  `logged_in_page`, `live_server_site` and `mock_site_context`, why every browser test is
  `transaction=True`, that a Playwright test is a flow test, where layout checks go, and the CI
  split. Its description names that branch so it triggers when someone writes a browser test.
- `fls-dev:qa-bugfixer`: a browser-only bug extends the existing flow test for that page rather than
  adding a file, and a design miss does not become a geometry assertion. The three copies of the
  "the suite can take more than 10 minutes, run it in the background" sentence in `ds:testing`,
  `qa-bugfixer` and `sdd:implement_plan` say what is true after the cleanup.
- `fls-dev:do_qa` Step 13: the parenthetical that presents a Playwright test as cheap to add goes.
- `fls-dev:qa-data-helper`: the description examples call it "qa-data-factory"; fix the name. State
  that its commands carry no tests unless they delete data.
- `frontend_check` and `design_check` stay as they are. They judge pages visually and overlap the
  pytest layout tests only in intent.

## Constraints

- `freedom_ls/*/tests/` ships in the wheel and unmarked tests are the portable set a downstream
  project runs. Deleting or re-marking a test changes that contract, and moving a helper module
  changes import paths downstream code may use, such as `freedom_ls.tests.app_guards` and
  `freedom_ls.tests.playwright_fixtures`. The optional-app collection guards in
  `course_applications/tests/` survive any merge.
- `contrib/conformance/tests/` are shipped probes, not junk, despite being marked `fls_internal`.
- CI job budgets: 10 minutes for the unit job, 15 for Playwright. Per-test timeout is 300 seconds.
- `pytest-randomly` stays on, so flow tests are still order-independent by construction.

## Research files

- `research_test_suite_inventory.md`: conftest and factory layering, the baselines, the biggest
  files, test-to-source ratios, misplaced and same-named files, marker coherence, what must not
  break.
- `research_junk_and_brittle_tests.md`: the rubric, grep-level counts per criterion with example
  tests, the keep floor, removal risks.
- `research_playwright_consolidation.md`: every Playwright file with what it exercises, the
  candidate flows, where setup time goes, what belongs in client tests, the web sources on flow
  versus isolated tests.
- `research_qa_helpers_and_tooling_tests.md`: every tooling test file classified as risk guard,
  workflow or junk; packaging and the downstream filter; the four options for the default run.
- `research_testing_skills_audit.md`: per skill, agent and command, what is stale, missing,
  junk-encouraging or contradictory.
- `research_test_suite_speed.md`: the measured durations for both suites, which files and fixtures
  hold the slow time, the per-test fixed cost of Playwright, and a ranking of the six levers by what
  the measurements support.
