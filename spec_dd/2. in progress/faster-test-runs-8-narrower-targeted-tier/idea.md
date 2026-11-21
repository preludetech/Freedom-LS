# A batch's targeted run covers only what its change can affect

Spec 8 of 10 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** 58% of batches stop running most or all of the suite. Each of those runs takes 4 workers for 20 minutes or more today; a run of one to five apps takes a few minutes, a guess.

## What

The targeted tier picks the tests a change can affect. A batch that edits one file in a widely
imported app, or a file the selector has no rule for, no longer runs most of the suite.

## Why

Of the last 119 batches, 34 ran the full suite and 35 more ran 28 to 38 of the 42 app test
directories. Two selector rules cause it. A path no rule knows escalates to `full`, and so does any
`conftest.py`, `urls.py` or `factories.py`. A change to any file in an app selects the whole tests
directory of every app that imports it, so one line in `panel_framework` selects 36 apps.
`implement_plan` already ends with a full run, so each of these wide runs is repeated work.

## What is settled

- A path the project can map to tests is mapped. `demo_content/` gets a rule and stops escalating.
- A change in a widely imported app does not select every importing app's whole tests directory on
  every batch.
- `implement_plan`'s final full run stays, and is where the wide check happens.
- The selector stays in the generic `ds` plugin. Project paths and app names reach it through
  `[tool.test_tiers]` in `pyproject.toml`.
- No rule is dropped without naming the run that still covers the tests it selected.
- How the selector treats paths main brought in does not change.

## Open until the spec

- How importer fan-out is narrowed: a limit on import depth, a per-app setting, or selection by the
  modules that import the changed one.
- Which escalation globs still mean `full`, and which select something smaller.
- Whether a batch's review fix and design fix runs select from the fix alone.

## Out of scope

- Coverage-based selection such as pytest-testmon.
- The number of runs going at once; `faster-test-runs-9-machine-wide-test-run-limit` owns that.
- What happens after a failure; `faster-test-runs-10-rerun-only-failures-in-a-batch` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_batch_test_load.md`, "What a batch's targeted run
  selects".
- `claude_plugins/django-stack/scripts/select_tests.py`, `[tool.test_tiers]` in `pyproject.toml`,
  `docs/app_structure.md`.
