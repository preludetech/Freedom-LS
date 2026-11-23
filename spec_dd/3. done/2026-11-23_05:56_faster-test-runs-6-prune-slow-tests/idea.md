# Slow and redundant tests are cut from a measured ranking

Spec 6 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** unknown. It needs the per-test ranking first.

## What

The suite's remaining cost is measured test by test, and the tests that cost the most for the least
are merged, rewritten or removed. The ranking is kept so the next slow test is easy to spot.

## Why

The suite has 19,507 tests. The timings taken so far are samples; they found the password hasher,
the database setup and the permission matrix, and they showed that test count alone is a poor guide:
1,400 cases of one shuffle test cost under a minute. Whether redundant tests are eating time is
still unknown until every test's duration is measured.

## What is settled

- The spec starts from one full run that records every test's duration.
- Work goes down the ranking by cost. A test is removed only when another test checks the same
  behaviour, and the spec names that test.
- The coverage threshold still holds afterwards.
- The spec states a target for the full run's CPU time and reports the result against it.

## Open until the spec

- The target, set from the ranking.
- Whether the ranking is refreshed by CI or by hand.
- Whether a per-test time limit should fail a new slow test.

## Out of scope

- Playwright tests and the permission matrix, which their own specs cover.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`.
- `claude_plugins/fls-dev/skills/testing/SKILL.md`.
