# Flaky tests

You are fixing a test that passed on at least one run and failed on another. Find the cause in the
code or the test, and fix it there. Never skip, delete, mark or retry-wrap the test.

Run the test on its own as the tier definition's single test run
(`claude_plugins/django-stack/resources/test_tiers.md`, "A single test run"). Read the failure
output first: it usually names which of the causes below applies. The facts about fixtures,
markers and the browser tests are in `skills/testing/SKILL.md`, `resources/testing.md` and
`resources/playwright-testing.md`; this guide points at them.

## Shared database state and transaction leakage

Recognise it: the test fails only after another test has run, or sees rows it did not create, or
counts that are too high.

Fix: the test creates every row it asserts on, and asserts on those rows rather than on a total.
Site-aware models take `mock_site_context` (see `skills/testing/SKILL.md`). A module-scoped or
session-scoped fixture that writes rows is the usual leak: make it function-scoped or make it clean
up after itself.

## `transaction=True` browser tests

Recognise it: a Playwright test passes alone and fails after another browser test, or finds a login
or row from a previous test.

Fix: these tests flush the database instead of rolling back, and each logs in through the UI
(`skills/playwright-tests/SKILL.md` states why). A row the test needs must be created inside the
test or its fixtures, never left over from another test or a data migration the flush removed.

## Playwright timing

Recognise it: an assertion right after a click fails with the old text, the old row count or a
hidden element, and passes when the machine is slower or faster.

Fix: assert through `expect(locator)` matchers, which wait, instead of reading a value once. Wait on
the visible result of the HTMX swap or the Alpine state change, not on the click returning. Where
the page offers no visible result, wait on the response the click triggers.

## Factory randomness

Recognise it: the failure message shows a generated name, email or slug, and the failure appears one
run in many. Typical forms: a unique field collides with another generated value, or an assertion
matches a substring of a random value.

Fix: pass the field the test cares about explicitly. Pin a value the assertion depends on. Give a
unique field a sequence, not a random draw.

## Bare sleeps

Recognise it: `time.sleep`, `wait_for_timeout` or a fixed delay before an assertion.

Fix: replace it with a wait on the condition the sleep stood in for: an `expect` matcher, a
`wait_for_url`, or a response wait. A fixed delay passes on a fast machine and fails on a loaded one.

## Test order

Recognise it: the test passes alone and fails in the full run, or fails only in some runs.
`pytest-randomly` shuffles test order and prints the seed it used at the top of the run.

Fix: reproduce first. Run the failing test together with the tests that ran before it, passing the
seed the failing run printed to the tier definition's single test run. When the failure repeats,
bisect the preceding tests for the one that leaves state behind (a module-level cache, a
settings override, a thread-local site context, a changed environment variable) and make that test
restore it.
