# Run the test suite less often in the SDD workflow

## Problem

The SDD workflow runs the full pytest suite far more often than it learns anything from it. One
spec that walks all 14 stages of `todo.md` can trigger 40 full-length passes when main moves
before every `(cmd)` step, and never fewer than 8 even when main stands still. The suite is 6,704
tests, 226 of them Playwright browser tests, and every one of those passes carries branch coverage
tracing, a per-file coverage table and the 73% threshold. Each pass takes more than ten minutes.

`research_current_test_runs.md` inventories the twelve sites that run pytest and the formula behind
those counts. The cost concentrates in four places:

- **The pre-step rebase.** Every `(cmd)` step rebases onto main first, and when main moved at all
  the rebase command runs `pytest -x -q` to green and then the whole suite again. A green `-x` run
  has already executed every test, so that is two full passes per step. Nothing looks at what main
  changed: a docs-only commit on main costs the same as a model change. Seven of the steps happen
  before any implementation exists, when the branch holds nothing but `spec_dd/` files.
- **Implementation.** Every batch ends with a full run, and the final verification runs it again on
  an unchanged tree.
- **QA.** Every QA bug fixed by the bug fixer agent ends with a full run, up to three per QA pass.
- **PR review.** Each round of review fixes runs the whole suite with `-x`, right after a pre-step
  rebase that just ran it twice.

Two defects ride along with the frequency. The coverage threshold lives in `addopts`, so any run
smaller than the whole suite fails it: the bug fixer's single-test RED and GREEN runs exit non-zero
today even when the test passes, and so does `pytest --co`. And no command passes `-n`, although
the project caps `-n auto` at four workers in the root `conftest.py` and the testing skill already
recommends it.

CI already runs the complete suite on every push and PR, split into a non-Playwright job with the
coverage gate and a separate Playwright job, plus lint, mypy, import contracts and test mirroring.
Pre-commit runs lint and types but never pytest. The local runs therefore do not have to be the only
proof that the suite is green; they have to give fast feedback on the change just made.

## What we are doing

Replace "run the full suite" with three named tiers, each defined once and referenced by every
command, so a command names a tier rather than copying pytest flags.

- **none.** No pytest. The change cannot alter a test result: `spec_dd/` and `docs/` files,
  `.claude/` configuration, plugin markdown.
- **targeted.** The tests that mirror the changed files, plus the tests of the apps that import
  the changed app, plus any new or edited test files. Parallel with `-n auto`, no coverage, no
  Playwright unless the diff touches templates, static files, JavaScript or views, in which case the
  touched app's `tests/playwright/` directory is included. The selection comes from the project's
  own mirroring rule (`check_test_mirroring.py`) and app dependency map (`docs/app_structure.md`),
  so it is deterministic and the command can print why each file was chosen.
- **full.** The whole suite, parallel with `-n auto`, with coverage and the 73% threshold, with
  Playwright, in the background. This is the gate, and it keeps the project's current meaning of
  "all tests pass".

A targeted run escalates to full when the diff touches anything with fan-out the mirror map cannot
see: migrations, `config/`, root or app `conftest.py`, factories and fixtures, `urls.py`,
middleware, signals, `apps.py`, the site-aware and content base apps, `pyproject.toml` or
`uv.lock`. The escalation list is an explicit glob list in the tier definition, not a judgment call. A
model follows a list; it does not reliably follow "use judgment".

### Where each tier runs

| Site | Today | After |
| --- | --- | --- |
| Pre-step rebase, main unchanged | nothing (already stops early) | nothing |
| Pre-step rebase, main moved, branch has no code yet | two full passes | none |
| Pre-step rebase, main moved, branch has code | two full passes | targeted on the files main changed, plus the branch's own tests; full only on escalation |
| Implementation, each batch | full | targeted on the batch's diff |
| Implementation, final verification | full | **full** |
| QA bug fixer, RED and GREEN | single test with coverage (exits non-zero) | single test, no coverage |
| QA bug fixer, after the fix | full per bug | targeted per bug; one **full** after the last fix of the QA pass |
| Address PR review | full with `-x` | targeted on the review fixes; CI re-runs the PR |
| Finish worktree, the rebase before landing | two full passes | one **full** |
| `/ds:commit` | full | targeted, with `/sdd:commit_quickly` unchanged as the no-test path |

The three full runs that remain, after the last batch, after the last QA fix and before landing, are
the fixed milestones. CI on the PR is the backstop for anything a targeted run missed.

### Why not a coverage-driven selector

`research_test_selection_tools.md` compares the options. pytest-testmon is the only tool that
selects by real execution dependencies, but it disables its own data collection whenever coverage is
on, does not track templates or static files, has unverified behaviour with xdist, pytest-randomly
and pytest-django on this stack, and starts cold in every worktree. pytest-picked only re-runs test
files that were themselves edited. The mirror map is less precise than testmon on Python changes,
but it reuses tooling the project already enforces, explains its choices, and the escalation list
covers the inputs no selector sees. testmon can be trialled later as a refinement of the targeted
tier without changing the tiers themselves.

## Settled

- The guaranteed full run stays local, at the three milestones above. CI is the backstop, not the
  gate.
- The four-worker cap on `-n auto` stays. The dev Postgres is shared across worktrees.
- A rebase that brought in nothing the branch's code can interact with runs no tests. CI already
  proved main.
- A failing targeted run is fixed with the pytest cache's `--lf` loop, then the tier re-runs whole.
- `research_tiered_gating.md` holds the practice this follows: affected-test selection locally, the
  complete run as a CI or milestone gate, and a failsafe list of inputs that mean "everything".

## Out of scope

- Making individual tests faster. `research_suite_timing.md` records the measured timings and the
  slowest tests, for a later effort.
- The rebuild the rebase command runs before its tests (dependency sync, npm install, Tailwind
  build, database init) fires on every rebase too. It is the same shape of problem and the same
  `rebase_main.md` step, but it is not a test run and this idea leaves it alone.
- Changing what CI runs.

## Named during planning

Concepts the plan needed that the sections above did not name:

- **importers.** The apps with a runtime or test-only dep on the changed app in the app
  dependency map (`docs/app_structure.md`), read as direct deps, not the transitive closure.
- **app test directory.** `<app>/tests`. The selection unit: a changed file selects its owning
  app's test directory, which holds the mirror, plus each importer's test directory. The mirror
  file runs inside it.
- **unmapped path.** A changed path that is neither `none`-tier, nor a test file, nor on the
  escalation list, nor inside an app, nor repository tooling. It escalates to `full`, as does a
  missing app dependency map.
- **repository tooling.** `claude_plugins/*/scripts/`, `claude_plugins/*/templates/`,
  `.claude/*/scripts/` and helpers under the top-level `tests/`: their tests are the top-level
  `tests/` directory. `claude_plugins/fls-content/` maps to its own tests and to
  `content_engine`'s validator tests.
- **touched app.** An app whose templates, static files, JavaScript or views the diff changed,
  or whose `tests/playwright/` holds a changed test file. Only a touched app's
  `tests/playwright/` runs in a targeted run; every other selected app's is ignored by directory.
- **deleted test file.** Selects nothing. A changed or added test file selects itself.
- **the branch's diff and main's diff.** A rebase's two selection inputs: `origin/main..HEAD` and
  `<old base>..origin/main`. The branch's own changed test files join the second selection but
  never raise its tier.
- **single test run.** The TDD RED and GREEN run of one test, `-x --no-cov`. It sits outside the
  tiers.
- **full run after the last QA fix.** When it fails, the fixes stay committed; the QA report gets
  an `UNRESOLVED` row naming the failing tests and the todo gets a human item to fix them.
