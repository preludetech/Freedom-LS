# Research: tests of QA helpers and developer tooling

Topic: what these tests protect and how they could stop running by default. Facts with paths; no implementation steps. Speed notes are inferred from reading the tests (DB fixtures, subprocess use), not measured.

## 0. Key configuration facts

- `pyproject.toml`: `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`. `addopts` includes `-m 'not ci_only and not weasyprint' --cov --cov-fail-under=73 --disable-socket`. Markers: `playwright`, `ci_only`, `fls_internal`, `weasyprint`. `timeout = 300`.
- Coverage: `[tool.coverage.run] source = ["freedom_ls"]`, `omit` includes `*/tests/*`, `*/conftest.py`, `*/qa_helpers/*` (with the comment that qa_helpers is developer tooling that never runs in production and its few tests are "written where the risk is, not to move this number"). The top-level `tests/` and `claude_plugins/` are outside `source`, so they never count. `dev_tools` is NOT omitted from coverage (only `qa_helpers` is); its code (`freedom_ls/dev_tools/{guard,config}.py` and `management/commands/*`) is in the 73% denominator and its 17 tests contribute to the numerator.
- CI (`.github/workflows/tests.yml`): `lint` job runs `generate_app_map.py --check`, `lint-imports --config test_organisation/import_contracts.toml`, `check_test_mirroring.py`. `unit-tests` runs `uv run pytest -m "not playwright"` (this `-m` overrides the addopts `-m`, so CI runs `ci_only` and `weasyprint` tests too, with coverage). `playwright-tests` runs `uv run pytest -m playwright --no-cov`. There is no separate tooling job.
- `.claude/settings.json` `_comment_qa_commands`: the `danger_` commands in `freedom_ls.dev_tools` "refuse to run unless DEBUG or DEV_TOOLS_ENABLED, so they only ever touch the per-branch dev database". The gate is `freedom_ls/dev_tools/guard.py` (`settings.DEBUG or config.DEV_TOOLS_ENABLED`; default `False` in `freedom_ls/dev_tools/config.py`; `config/settings_dev.py:68` sets True). `.claude/settings.json` also notes scripts in `.claude/ds/scripts/` and `.claude/fls-dev/scripts/` run prompt-free and should be reviewed "as security-sensitive".
- `config/settings_dev.py:61-62` installs `freedom_ls.qa_helpers` and `freedom_ls.dev_tools`; `config/urls.py:99` mounts `qa/` (`qa_helpers.urls`, toast preview views).

## 1. What each module protects

Classification key: **RISK** = guards a real risk; **WORKFLOW** = tests tooling behaviour that matters to the dev workflow; **JUNK** = candidate junk / low value.

### `freedom_ls/dev_tools/tests/` (DB tests; `django_db`, `call_command`; 17 tests)

| File | Tests | Protects | Class |
|---|---|---|---|
| `test_guard.py` (5 fns, 1 parametrised) | Gate raises when DEBUG False and `DEV_TOOLS_ENABLED` unset; passes otherwise; djclick commands and `create_demo_data` refuse when gate closed | The only thing that stops `danger_*` commands wiping a production DB. Directly the safety control the settings.json comment relies on. | RISK |
| `test_danger_clear_all_course_progress.py` (3) | `--yes` empties five progress tables, leaves content; declining prompt deletes nothing; confirm deletes | Destructive command scoping and the confirmation prompt | RISK |
| `test_danger_content_delete.py` (4) | Delete succeeds with progress rows / question answers present; deleting a topic with progress is blocked (protected FK); articles removed | Destructive delete across protected FKs; fails loudly if a new FK is added without the command knowing | RISK |
| `test_danger_commands_with_applications.py` (2) | Both danger commands take the course application with the form sitting | Same command family; regression for an FK added later. Imports `course_applications` factories/models (listed in `test_organisation/import_baseline.txt` lines 51-53 and `import_contracts.toml:170-171`) | RISK (narrow) |
| `test_create_demo_data.py` (3) | `--yes` creates demo sites; declining prompt creates none; confirming creates | Prompt behaviour of a seeding command (non-destructive on its own) | WORKFLOW, borderline junk (seeding only) |

### `freedom_ls/qa_helpers/tests/` (DB tests; 19 tests; `fls_internal` on 3 of 5 files)

| File | Tests | Protects | Class |
|---|---|---|---|
| `test_qa_create_report_fixtures.py` (6; file-level `fls_internal`) | A reset in one organisation leaves another organisation's learners; reset deletes its own; email namespacing per organisation; long/non-ASCII slug prefixes; one prefix never a prefix of another | Mis-scoped delete in a QA reset command ("silently empties somebody's dataset" per the coverage comment). The first two tests and the prefix-collision test are the real risk; the slug/email-prefix tests are edge cases of the scoping mechanism | RISK (first two plus prefix collision); rest WORKFLOW |
| `test_qa_create_application_review_accounts.py` (2) | Purge takes the sitting and its stored file; reviewer is granted view permission on applications | Destructive purge completeness; permission seed correctness | first RISK; second JUNK-ish (asserts seed content) |
| `test_qa_create_organisations.py` (4; `fls_internal`) | Seeded slugs reverse an educator-interface URL; non-Latin / empty-slugify / explicit slug derivation | Slug helper behaviour of a seeder | JUNK (tests the fixture builder) |
| `test_qa_create_report_brand_organisations.py` (4; `fls_internal`) | Logo "exists/missing" reporting under pathless vs local storage | Output reporting of a fixture builder | JUNK |
| `test_qa_create_report_cohort.py` (3) | Seeded percentages climb the ladder, match completed cells, fully complete record stamped complete | That a QA seed produces self-consistent data | JUNK (tests the QA scaffold; no deletes) |

About 56 `qa_*` commands exist in `freedom_ls/qa_helpers/management/commands/`; five have tests. `learner_progress/tests/test_factories.py` and `form_engine/tests/test_form_progress_score_quiz.py` only mention qa_helpers in comments/docstrings (they test real code with a qa-shaped fixture); `content_engine/tests/test_content_tags.py` matched "danger" as a label type, unrelated. No other `freedom_ls/*/tests/` module calls a seeding/clearing command.

### Top-level `tests/` (dev scripts and repo tooling)

Most are pure-Python or subprocess tests that build throwaway git repos or stub binaries under `tmp_path`; none needs the DB except `test_playwright_fixtures.py`. Helpers: `tests/conftest.py`, `tests/_script_trees.py`, `tests/stub_tools.py`.

| File (tests) | Script / thing tested | Can it damage real data or git history? | Speed (inferred) | Class |
|---|---|---|---|---|
| `test_dev_db_scripts.py` (12) | `claude_plugins/fls-dev/scripts/dev_db_delete.sh` and `dev_db_init.sh` with stubbed `psql` (drops with force, owner reassign, never grants to `pguser`, stamps branch DB, failing psql stops before any drop); also imports `dev_db.server` | Scripts DROP DATABASE and are prompt-free in `.claude/settings.json`; the tests use stubs and never touch a real DB | subprocess per case, fast | RISK (destructive, prompt-free scripts) |
| `test_land_on_main.py` (15) | `claude_plugins/sdd/scripts/land_on_main.sh` (sync/land verbs; blocks on dirty main, merge in progress, divergence; fast-forwards origin and main worktree; push rejection) against real temp git repos in `Layout` | Script pushes to origin and moves main; tests use temp repos, never the real repo | many `git` subprocesses, moderate | RISK (history-touching) |
| `test_rebase_lost_change_check.py` (11) | Rebase lost-change detector (lost vs needs-review: renames, renumbered migrations, binary) | Guards against silently losing work in a rebase; temp git repos | git subprocesses, moderate | RISK |
| `test_rebuild_after_rebase.py` (4) | `claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` plus generated wrapper `.claude/fls-dev/scripts/rebuild_after_rebase.sh`; stubs `uv`/`npm`/`psql` | Order and halt-on-failure of sync, npm, tailwind; stubbed | fast | WORKFLOW |
| `test_upstream_change_scan.py` (12) | `claude_plugins/sdd/scripts/upstream_change_scan.sh` signals (overlap, shared base migration, skill change, truncation) | Read-only git analysis | git subprocesses | WORKFLOW |
| `test_reap_playwright_mcp.py` (6) | `claude_plugins/django-stack/scripts/reap_playwright_mcp.sh` and wrapper `.claude/ds/scripts/reap_playwright_mcp.sh`; `ps`/`kill` stubbed | Script kills processes; tests never signal | fast | WORKFLOW (mild RISK: kills processes) |
| `test_stale_dbs.py` (12) | Stale per-branch database classification (worktree gone/prunable/branch switched; keep other repos' DBs; parse worktree list/stamp) | Decides which DBs get dropped; pure functions | very fast, no subprocess | RISK (decides what gets deleted) |
| `test_diagnose.py` (11) | Dev environment diagnose script: log-signature matching, recent log names, summary formatting, exit codes | Read-only | very fast | WORKFLOW, low value (log-line classification, date wrapping) |
| `test_check_test_mirroring.py` (26) | `claude_plugins/django-stack/scripts/check_test_mirroring.py` via subprocess on throwaway projects; includes `test_check_passes_on_live_tree` | Lint tool, read-only. CI `lint` already runs it on the live tree | 26 subprocess spawns | WORKFLOW (live-tree case duplicates CI) |
| `test_generate_app_map.py` (46) | `claude_plugins/django-stack/scripts/generate_app_map.py` and import-contract generation; includes `test_lint_imports_passes_on_live_tree` and `test_check_from_repo_root_exits_0`, which duplicate CI `lint` steps | Read-only | likely the slowest file in `tests/` (46 tests, subprocesses, some run `lint-imports`) | WORKFLOW; live-tree cases duplicate CI |
| `test_security_patterns.py` (1 parametrised, 10 cases) | Scans all `freedom_ls/**/*.py` (skipping only `migrations`, despite the docstring saying tests are excluded) for a list of forbidden substrings: raw-SQL calls, SQL expression wrappers, CSRF exemption, dynamic-code builtins, unsafe deserialisation, request-dict unpacking | Read-only | file scan ten times | Product-code guard living in `tests/`; protects the CLAUDE.md "ORM only" rule. Brittle: plain substring match, so a pattern also matches any identifier ending in the same text. RISK / brittle |
| `test_settings_dev.py` (7) | `config/settings_dev.py` test DB name, `template0` clone, non-superuser role, `application_name` building | Asserts dev settings values | fast | WORKFLOW; value-asserting (the "hardcoded config" pattern) |
| `test_conftest.py` (3) | Root `conftest.py` xdist worker-count cap | Test infrastructure testing itself | fast | JUNK / low value |
| `test_playwright_fixtures.py` (1, `django_db(transaction=True)`) | Connection closed after the playwright loop | Guards a flaky-teardown fixture in test infra | DB | WORKFLOW (test infra) |
| `test_entrypoints.py` (3) | `config.wsgi`/`config.asgi` import and give callable; missing `DJANGO_SETTINGS_MODULE` names the env var | Production entrypoints (product config) | fast | Real code, not tooling |
| `test_design_screenshots.py` (4) | `claude_plugins/sdd/scripts/design_screenshots.py` argument validation errors and copy preparation | tmp_path only | fast | WORKFLOW (SDD tooling) |
| `tests/playwright/test_design_screenshots.py` (3, `playwright`) | Same script launching a real browser: artboards written, stale removed, canvas with no artboards exits 1, whole-page screenshots | Browser launch (CI `playwright-tests` job picks it up with `-m playwright`) | slow (browser); serves an SDD design tool, not the product | WORKFLOW; slow and not product |

### `claude_plugins/fls-content/validate/tests/test_validator.py` (63 test functions; heavy subprocess use)

Runs the content validator (`claude_plugins/fls-content/validate/validate.py`) against fixture content (ruff per-file ignore adds `S404`, `S603`, so it spawns subprocesses). It is a plugin that content authors use, so it is a content-authoring tool rather than dev scaffolding. `claude_plugins/fls-content` is in `testpaths`; mypy's exclusion carves out `claude_plugins/fls-content/validate`. Class: WORKFLOW (tests a shipped tool); large and subprocess-heavy.

## 2. How downstream projects consume FLS tests

- `pyproject.toml` `[tool.setuptools.packages.find]`: `include = ["freedom_ls*"]`, `exclude = ["media*", "config*", "static*", "dev_db*", "gitignore*", "node_modules*", "demo_content*"]`. No `MANIFEST.in` exists. Consequences:
  - Top-level `tests/` is not under `freedom_ls*`, so it does not ship. `dev_db/`, `config/`, `demo_content/` are excluded explicitly. `claude_plugins/` does not match `freedom_ls*` either.
  - `freedom_ls.qa_helpers` and `freedom_ls.dev_tools` match `freedom_ls*` and are NOT excluded, so they ship as packages, including their `tests/` subpackages (as does every other app's `tests/`; there is no `*.tests*` exclusion). A downstream only activates them by adding them to `INSTALLED_APPS`; FLS's own `config/settings_dev.py` does that, and `config/` is excluded from the package.
- Downstream consumption of tests happens via markers, not packaging: `claude_plugins/fls-dev/skills/testing/SKILL.md` (lines ~132-142), `claude_plugins/fls-dev/resources/testing.md` (lines 35-49), `claude_plugins/fls-dev/resources/playwright-testing.md`, `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md:20` and `claude_plugins/fls-dev/commands/concrete/update_fls.md` (lines 148, 165, 212, 235) say a concrete downstream runs `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` as its "portable contract test set". `claude_plugins/django-stack/resources/testing.md:444` says tests depending on repo-only, non-distributed data get a project marker.
- A downstream pytest run over an installed `freedom_ls` would collect `dev_tools` and `qa_helpers` tests if those apps are installed; only 3 of 5 qa_helpers files carry `fls_internal`. The dev_tools tests and two qa_helpers files (`test_qa_create_application_review_accounts.py`, `test_qa_create_report_cohort.py`) are unmarked, i.e. part of the portable set.
- No `upgrade_notes` or `docs/` entry says qa_helpers or dev_tools are or are not shipped. The "excluded from the packaged distribution" wording appears only for `demo_content/`.

## 3. Options for "not running them by default"

Common facts: qa_helpers tests and the top-level `tests/` do not move the coverage number (qa_helpers code is omitted; `tests/` is outside `source`). dev_tools is the exception (see section 0). `check_test_mirroring.py` and the import contracts only look at `freedom_ls` apps (`test_check_test_mirroring.py::test_test_file_outside_any_app_is_ignored`), so top-level `tests/` has no baseline entries.

**(a) Delete them.**
- Coverage: qa_helpers tests: no change. dev_tools tests: lowers coverage of `freedom_ls/dev_tools/*` (small module, in the denominator); effect on the 73% gate not measured. `tests/` and `claude_plugins`: no change.
- `test_organisation`: deleting qa_helpers/dev_tools test files makes their lines in `mirroring_baseline.txt` (lines 120-124, 287-292) stale, which `check_test_mirroring.py` fails on (`test_baseline_line_whose_file_is_gone_fails_as_stale`). Deleting `test_danger_commands_with_applications.py` makes `import_baseline.txt:51-53` and `import_contracts.toml:170-171` stale (baseline line matching nothing fails in `generate_app_map`). An app with no test modules gets no contract (`test_app_with_no_test_modules_gets_no_contract`), so the `dev_tools` and `qa_helpers` blocks (`import_contracts.toml:162`, `:409`) would drop out on regeneration.
- CI: `unit-tests` shorter; `lint` unchanged. Deleting `tests/test_check_test_mirroring.py` / `test_generate_app_map.py` removes the only tests of those lint tools, though CI `lint` still runs them on the live tree.
- Workflow commands: deleting `tests/test_land_on_main.py`, `test_rebase_lost_change_check.py`, `test_dev_db_scripts.py` removes the only regression protection for scripts that push to origin, detect lost changes after rebase, and drop databases (prompt-free per `.claude/settings.json`).

**(b) New marker, deselected in `addopts`, separate CI step.** Style: `ci_only` is the existing deselect-by-default marker; the addopts `-m 'not ci_only and not weasyprint'` would gain another `and not <marker>` (name not decided here).
- Coverage: no change for `tests/`/qa_helpers; if dev_tools tests are marked they drop out of the default run and lower the dev_tools contribution unless CI's step also measures it.
- CI: `unit-tests` runs `-m "not playwright"`, which overrides the addopts `-m`, so a new marker would still run in the existing job unless that command changes. A new job or step is needed to run them separately; `playwright-tests` (`-m playwright --no-cov`) is a template.
- `test_organisation`: baselines unaffected (files remain).
- Workflow commands: scripts stay tested but only when selected; no automatic signal on changes to `land_on_main.sh` etc. Marker can be applied file-level via `pytestmark` (precedent: `fls_internal`).
- Downstream: the exact `-m` string appears in at least six places (see section 2), so adding the marker to the portable-set filter touches all of them.

**(c) Drop `tests` (and tooling dirs) from `testpaths`, run explicitly.**
- Removing `tests` and `claude_plugins/fls-content` removes the 16 top-level modules and the validator tests from default runs; `uv run pytest tests` still works. CI `playwright-tests` runs `pytest -m playwright` using testpaths, so it would stop collecting `tests/playwright/test_design_screenshots.py` unless CI names the path.
- `freedom_ls/qa_helpers` and `dev_tools` live inside `freedom_ls`, so this option cannot exclude them (it would need `--ignore` or `norecursedirs`).
- Coverage: no change (none of these are in `source`). CI: `unit-tests` loses them silently unless a step is added. `test_security_patterns.py` and `test_entrypoints.py` are product guards in `tests/` and would also stop running.
- `test_organisation`: no effect.

**(d) Keep only the destructive-command tests.**
- Keep (per section 1): `dev_tools/tests/test_guard.py`, `test_danger_clear_all_course_progress.py`, `test_danger_content_delete.py`, `test_danger_commands_with_applications.py`; in qa_helpers, the cross-organisation reset tests in `test_qa_create_report_fixtures.py` and the purge test in `test_qa_create_application_review_accounts.py`. Candidates to drop: `test_create_demo_data.py`, `test_qa_create_organisations.py`, `test_qa_create_report_brand_organisations.py`, `test_qa_create_report_cohort.py`.
- Matches the existing policy in the `pyproject.toml` coverage comment.
- `test_organisation`: removed files' lines in `mirroring_baseline.txt` (`test_create_demo_data`, `test_qa_create_organisations`, `..._report_brand_organisations`, `..._report_cohort`) become stale; `import_baseline` unaffected; the qa_helpers contract block stays while any qa_helpers test remains.
- For `tests/`, the analogue is keep `test_dev_db_scripts.py`, `test_stale_dbs.py`, `test_land_on_main.py`, `test_rebase_lost_change_check.py` (destructive or history-touching) and treat `test_conftest.py`, `test_diagnose.py`, `test_settings_dev.py` as junk candidates.
- Coverage: qa_helpers none; dev_tools none (destructive tests are the ones providing the dev_tools coverage).

## 4. Precedent for "only real code"

- `pyproject.toml` `[tool.coverage.run]` omit comment (lines 108-114): "qa_helpers is developer tooling: management commands that build fixtures in a dev database for manual QA, plus the toast preview views. None of it runs in production, so counting it measures how much QA scaffolding exists rather than how well the product is covered. A few of the commands do carry tests -- the destructive ones, where a mis-scoped delete silently empties somebody's dataset -- but those are written where the risk is, not to move this number." This is the only explicit statement, and it is a precedent for the user's policy: tooling is not "real code", with destructive-command tests as the exception.
- `pyproject.toml` ruff and mypy: `spec_dd/` is "not shipped code" (lines 171-174, 291-293); `freedom_ls/contrib/conformance/**` is "shipped as production code but pytest-style test functions" (line 215); `[tool.setuptools.packages.find]` is the only packaging definition of what ships.
- `.claude/settings.json` `_comment_qa_commands` classes `danger_` commands as dev-database-only.
- `claude_plugins/fls-dev/agents/qa-data-helper.md` lines 14-33: new QA scripts/management commands go in `qa_helpers/management/commands/`; nothing requires or forbids tests.
- No `docs/` or skill file defines "product code" versus tooling. The `fls-dev:testing` skill (`SKILL.md`, `resources/testing.md`) covers only the `fls_internal`/`playwright`/`ci_only`/`weasyprint` taxonomy and does not mention qa_helpers, dev_tools or `tests/`. `docs/app_structure.md` lists `qa_helpers` and `dev_tools` as ordinary apps with runtime deps (lines 26, 40, 88-94, 142-157, 252, 266).

## 5. Other observations

- `tests/test_security_patterns.py`: docstring says test files are excluded but `_collect_python_files` only skips `migrations`, so tests and the qa/dev tooling are scanned too.
- `test_generate_app_map.py` (`test_lint_imports_passes_on_live_tree`, `test_check_from_repo_root_exits_0`) and `test_check_test_mirroring.py::test_check_passes_on_live_tree` duplicate CI `lint` job steps.
- `fls_internal` on 3 of 5 qa_helpers files shows prior intent that these do not run downstream, but the other two and all dev_tools tests would run in the portable set.

status: ok
