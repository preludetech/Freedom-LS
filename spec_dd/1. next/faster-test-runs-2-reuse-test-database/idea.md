# A pytest run reuses the test database

Spec 2 of 7 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** about 1 minute off a full run, and about 1 minute off every other pytest run, including each single-test run. Measured: startup drops from 62s to 4s.

## What

A pytest run no longer builds the test database from scratch when the schema has not changed.
A single-test run starts in seconds, and a parallel run stops paying the setup once per worker.
When migrations change, the next run rebuilds the database without anyone remembering a flag.
Test databases that no worktree uses any more are removed.

## Why

Every pytest invocation spends about a minute applying 167 migrations before the first test runs.
An SDD run starts pytest many times: once per red and green step, once per batch, once per rebase.
Each xdist worker pays the minute too. With no migrations to apply, the same setup takes about 4s.

## What is settled

- The database is kept between runs and rebuilt when its schema is out of date. A run never passes
  or fails because of a stale schema.
- The rebuild is automatic for the cases an SDD run produces: a new or changed migration on the
  branch, and migrations a rebase brings in.
- The schema is still built by applying migrations, so tests keep exercising them. Building the
  schema straight from the models is not adopted: 10 migrations run Python, and only about 45 tests
  have been tried that way.
- Anything added to the generic `ds` or `sdd` plugins stays generic. Project values reach them
  through `.claude/ds/config.md`, `.claude/sdd/config.md` or `[tool.*]` in `pyproject.toml`.
- Removing a worktree removes its test databases, including the per-worker ones.

## Open until the spec

- How a run detects an out-of-date schema: from the diff the test selector already reads, from a
  fingerprint of the migration files, or both.
- Whether CI reuses a database or always builds one.
- How the 31 test databases already on the dev Postgres are cleaned up.

## Out of scope

- Squashing migrations.
- Changing how the development database is created.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Test database setup".
- `claude_plugins/django-stack/resources/test_tiers.md`, the worktree teardown script named in
  `.claude/sdd/config.md`.
- <https://pytest-django.readthedocs.io/en/stable/database.html>
