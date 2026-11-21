# Fewer, faster Playwright tests

Spec 4 of 7 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** 2 to 3 minutes off a full run. A guess until the audit is done.

## What

The Playwright tests take much less time while covering the same behaviour. A test that needs a
signed-in user gets one without driving the login form. Tests that load the same page with the same
data to check different things become one flow. The sign-in form keeps its own tests.

## Why

The suite has 220 Playwright tests at about 7s each, roughly 25 minutes of CPU, and each one holds a
browser and a live server while it runs. Every signed-in test fills in the login form first.
Several files check one page at several viewports as separate tests, each repeating the same setup.

## What is settled

- The spec starts with an audit of all 220 tests: for each, what it checks, what setup it shares
  with its neighbours, and whether it merges, stays or goes. No such audit exists yet.
- No checked behaviour is dropped without the audit naming it and the owner approving it.
- Signing in through the form is tested where sign-in is the subject, and nowhere else.
- The `ds:playwright-tests` and `fls-dev:playwright-tests` skills are updated so new tests follow
  the same rules.
- The spec measures the Playwright run before and after.

## Open until the spec

- How a signed-in session reaches the browser, given every browser test is `transaction=True` and
  the database is flushed after each one.
- Which viewport and layout checks can move out of the browser altogether.

## Out of scope

- Non-browser tests.
- The QA runs that use the Playwright MCP.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Playwright".
- `freedom_ls/tests/playwright_fixtures.py`, whose docstring explains the current login trade-off.
- <https://playwright.dev/python/docs/auth>
