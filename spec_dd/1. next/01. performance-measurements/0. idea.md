# Performance Measurements

## Goal

Generate a performance report for the FLS application that shows where the biggest bottlenecks are. The report should be automated — no manual fiddling with tools required. A developer runs a command and gets a clear picture of which endpoints are slow, which have too many queries, and which have N+1 problems.

## What the report should show

For each endpoint/view:
1. **Response time** — How long the request took
2. **Database query count** — How many DB queries were executed
3. **Duplicate queries** — Identical queries fired multiple times (N+1 signal)
4. **Slow queries** — Any individual query taking too long

Results should be sorted/flagged so the worst offenders are obvious.

## Performance targets (based on research)

These are the benchmarks we're measuring against:

| Metric | Good | Warning | Bad |
|--------|------|---------|-----|
| Server response time | < 200ms | 200-500ms | > 500ms |
| DB queries (simple view) | 1-5 | 5-15 | > 15 |
| DB queries (complex view) | 5-15 | 15-30 | > 30 |
| HTMX partial response | < 200ms | 200-500ms | > 500ms |
| Individual query time | < 10ms | 10-50ms | > 50ms |
| Duplicate queries | 0 | 1-2 | > 2 |

## Approach

Build a management command or test suite that:
1. Hits all (or key) endpoints in the application with a test client
2. Captures response time, query count, duplicate queries, and slow queries for each
3. Outputs a report sorted by worst performers

This needs test data in the database to be meaningful — endpoints should be hit with realistic data volumes.

Django's test client combined with `django.test.utils.CaptureQueriesContext` (or `connection.queries` with `DEBUG=True`) can capture all SQL queries per request without any extra dependencies.

## Environment notes

- This runs in a dev environment: DB, server, and browser all on the same machine
- Network latency is not measurable in this setup — we're measuring server-side performance only
- Production profiling is out of scope for now

## Test organisation

- Profiling tests must be explicitly marked (e.g. with a pytest marker like `@pytest.mark.profiling`) so they are **not** run as part of the normal test suite
- There should be a simple command to run only profiling tests (e.g. `uv run pytest -m profiling`)
- Profiling tests should be easy to find in the codebase — keep them in a dedicated location or use a naming convention that makes them obvious
- Each profiling test should be straightforward to update when endpoints or data requirements change

## What this is NOT

- Not adopting django-auto-prefetch (we want to measure, not auto-fix)
- Not adding production monitoring
- Not building always-on middleware

## Research

See the research files in this directory for detailed analysis of tools, targets, and best practices.
